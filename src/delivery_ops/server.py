from __future__ import annotations

import hmac
import json
import mimetypes
import sys
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from . import domain, store

MAX_BODY_BYTES = 1_048_576
READ_TIMEOUT_SECONDS = 5.0
API_ACTOR = "local-operator"
SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}
STATIC_ROUTES = {
    "/": "index.html",
    "/app.js": "app.js",
    "/styles.css": "styles.css",
}


class DeliveryHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        handler: type[BaseHTTPRequestHandler],
        *,
        token: str | None,
        app_store: store.DeliveryStore,
        web_root: Path,
        read_timeout: float,
    ) -> None:
        super().__init__(server_address, handler)
        self.token = token
        self.app_store = app_store
        self.web_root = web_root
        self.read_timeout = read_timeout


def read_request_body(
    stream: Any,
    content_length: int,
    max_bytes: int = MAX_BODY_BYTES,
) -> tuple[Literal["ok", "too_large", "incomplete"], bytes]:
    chunks: list[bytes] = []
    total = 0
    remaining = content_length
    while remaining > 0:
        try:
            chunk = stream.read(min(65_536, remaining))
        except TimeoutError:
            return "incomplete", b"".join(chunks)
        if not chunk:
            return "incomplete", b"".join(chunks)
        total += len(chunk)
        if total > max_bytes:
            return "too_large", b""
        chunks.append(chunk)
        remaining -= len(chunk)
    return "ok", b"".join(chunks)


def create_server(
    *,
    host: str,
    port: int,
    token: str | None,
    data_dir: str | Path,
    web_root: str | Path,
    read_timeout: float = READ_TIMEOUT_SECONDS,
) -> DeliveryHTTPServer:
    if host != "127.0.0.1":
        raise ValueError("Delivery Operations Console must bind to 127.0.0.1")
    resolved_web_root = Path(web_root).resolve()
    app_store = store.DeliveryStore(data_dir)

    class RequestHandler(BaseHTTPRequestHandler):
        server: DeliveryHTTPServer

        def setup(self) -> None:
            super().setup()
            self.connection.settimeout(self.server.read_timeout)

        def do_GET(self) -> None:
            self._dispatch("GET")

        def do_POST(self) -> None:
            self._dispatch("POST")

        def do_PATCH(self) -> None:
            self._dispatch("PATCH")

        def do_DELETE(self) -> None:
            self._dispatch("DELETE")

        def do_PUT(self) -> None:
            self._dispatch("PUT")

        def do_OPTIONS(self) -> None:
            self._dispatch("OPTIONS")

        def do_HEAD(self) -> None:
            self._dispatch("HEAD")

        def do_TRACE(self) -> None:
            self._dispatch("TRACE")

        def do_CONNECT(self) -> None:
            self._dispatch("CONNECT")

        def log_message(self, format: str, *args: Any) -> None:
            return

        def send_response(self, code: int, message: str | None = None) -> None:
            super().send_response(code, message)
            method = getattr(self, "command", None) or "UNKNOWN"
            raw_path = getattr(self, "path", "")
            path = urlparse(raw_path).path if isinstance(raw_path, str) else ""
            print(
                json.dumps({"method": method, "path": path, "status": int(code)}, sort_keys=True),
                file=sys.stderr,
                flush=True,
            )

        def send_error(
            self,
            code: int,
            message: str | None = None,
            explain: str | None = None,
        ) -> None:
            del message, explain
            self.close_connection = True
            if getattr(self, "request_version", "HTTP/0.9") == "HTTP/0.9":
                self.request_version = "HTTP/1.0"
            try:
                status = HTTPStatus(code)
                error_code = status.name.lower()
                error_message = status.phrase.lower()
            except ValueError:
                status = HTTPStatus.INTERNAL_SERVER_ERROR
                error_code = "internal_server_error"
                error_message = "internal server error"
            raw_path = getattr(self, "path", "")
            path = urlparse(raw_path).path if isinstance(raw_path, str) else ""
            self._send_json(
                status,
                {"error": {"code": error_code, "message": error_message}},
                cache_api=path.startswith("/api/"),
            )

        def _dispatch(self, method: str) -> None:
            try:
                parsed = urlparse(self.path)
                path = parsed.path
                if path.startswith("/api/"):
                    self._handle_api(method, path)
                    return
                self._handle_static(method, path)
            except Exception:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": {"code": "internal_server_error", "message": "internal server error"}}, cache_api=self.path.startswith("/api/"))

        def _handle_api(self, method: str, path: str) -> None:
            if path == "/api/health":
                if method != "GET":
                    self._method_not_allowed({"GET"})
                    return
                self._send_json(HTTPStatus.OK, {"status": "ok", "service": "delivery-operations-console"})
                return

            if path == "/api/releases":
                if method == "GET":
                    self._send_json(HTTPStatus.OK, {"releases": self.server.app_store.list_releases()})
                    return
                if method == "POST":
                    if not self._require_auth():
                        return
                    payload = self._require_json_body()
                    if payload is None:
                        return
                    try:
                        release = self.server.app_store.create_release(payload, actor=API_ACTOR)
                    except domain.ValidationError as exc:
                        self._bad_request(str(exc))
                        return
                    self._send_json(HTTPStatus.CREATED, release)
                    return
                self._method_not_allowed({"GET", "POST"})
                return

            if path == "/api/audit":
                if method != "GET":
                    self._method_not_allowed({"GET"})
                    return
                self._send_json(HTTPStatus.OK, {"events": self.server.app_store.get_audit()})
                return

            parts = [part for part in path.split("/") if part]
            if len(parts) == 3 and parts[:2] == ["api", "releases"]:
                release_id = parts[2]
                if not self._require_path_uuid(release_id):
                    return
                if method == "GET":
                    try:
                        release = self.server.app_store.get_release(release_id)
                    except domain.ValidationError:
                        self._not_found("release not found")
                        return
                    except domain.NotFoundError:
                        self._not_found("release not found")
                        return
                    self._send_json(HTTPStatus.OK, release)
                    return
                if method == "PATCH":
                    if not self._require_auth():
                        return
                    payload = self._require_json_body()
                    if payload is None:
                        return
                    try:
                        release = self.server.app_store.update_release(release_id, payload, actor=API_ACTOR)
                    except domain.ValidationError as exc:
                        self._bad_request(str(exc))
                        return
                    except domain.ConflictError as exc:
                        self._conflict(str(exc), self.server.app_store.get_release(release_id))
                        return
                    except domain.NotFoundError:
                        self._not_found("release not found")
                        return
                    self._send_json(HTTPStatus.OK, release)
                    return
                self._method_not_allowed({"GET", "PATCH"})
                return

            if len(parts) == 4 and parts[:2] == ["api", "releases"] and parts[3] == "audit":
                if method != "GET":
                    self._method_not_allowed({"GET"})
                    return
                if not self._require_path_uuid(parts[2]):
                    return
                try:
                    events = self.server.app_store.get_release_audit(parts[2])
                except domain.ValidationError:
                    self._not_found("release not found")
                    return
                except domain.NotFoundError:
                    self._not_found("release not found")
                    return
                self._send_json(HTTPStatus.OK, {"events": events})
                return

            if len(parts) == 4 and parts[:2] == ["api", "releases"] and parts[3] in {"gates", "risks"}:
                if method != "POST":
                    self._method_not_allowed({"POST"})
                    return
                if not self._require_path_uuid(parts[2]):
                    return
                if not self._require_auth():
                    return
                payload = self._require_json_body()
                if payload is None:
                    return
                try:
                    if parts[3] == "gates":
                        entity = self.server.app_store.add_gate(parts[2], payload, actor=API_ACTOR)
                    else:
                        entity = self.server.app_store.add_risk(parts[2], payload, actor=API_ACTOR)
                except domain.ValidationError as exc:
                    self._bad_request(str(exc))
                    return
                except domain.NotFoundError:
                    self._not_found("release not found")
                    return
                self._send_json(HTTPStatus.CREATED, entity)
                return

            if len(parts) == 5 and parts[:2] == ["api", "releases"] and parts[3] in {"gates", "risks"}:
                if method != "PATCH":
                    self._method_not_allowed({"PATCH"})
                    return
                if not self._require_path_uuid(parts[2]) or not self._require_path_uuid(parts[4]):
                    return
                if not self._require_auth():
                    return
                payload = self._require_json_body()
                if payload is None:
                    return
                try:
                    if parts[3] == "gates":
                        entity = self.server.app_store.update_gate(parts[2], parts[4], payload, actor=API_ACTOR)
                    else:
                        entity = self.server.app_store.update_risk(parts[2], parts[4], payload, actor=API_ACTOR)
                except domain.ValidationError as exc:
                    self._bad_request(str(exc))
                    return
                except domain.ConflictError as exc:
                    self._conflict(str(exc), self.server.app_store.get_release(parts[2]))
                    return
                except domain.NotFoundError as exc:
                    message = str(exc)
                    if "release" in message:
                        self._not_found("release not found")
                    else:
                        self._not_found(message)
                    return
                self._send_json(HTTPStatus.OK, entity)
                return

            self._not_found("resource not found")

        def _handle_static(self, method: str, path: str) -> None:
            if method != "GET":
                self._method_not_allowed({"GET"}, cache_api=False)
                return
            if path == "/favicon.ico":
                self.send_response(HTTPStatus.NO_CONTENT)
                self._send_common_headers(content_type="image/x-icon", content_length=0, cache_api=False)
                self.end_headers()
                return
            filename = STATIC_ROUTES.get(path)
            if filename is None:
                self._not_found("resource not found", cache_api=False)
                return
            target = (self.server.web_root / filename).resolve()
            if target.parent != self.server.web_root:
                self._not_found("resource not found", cache_api=False)
                return
            if not target.exists() or not target.is_file():
                self._not_found("resource not found", cache_api=False)
                return
            content_type = mimetypes.types_map.get(target.suffix, "application/octet-stream")
            if target.suffix in {".html", ".js", ".css"}:
                content_type = {
                    ".html": "text/html",
                    ".js": "application/javascript",
                    ".css": "text/css",
                }[target.suffix]
            body = target.read_bytes()
            self.send_response(HTTPStatus.OK)
            self._send_common_headers(content_type=f"{content_type}; charset=utf-8", content_length=len(body), cache_api=False)
            self.end_headers()
            self.wfile.write(body)

        def _require_auth(self) -> bool:
            if self.server.token is None:
                self._unauthorized()
                return False
            header = self.headers.get("Authorization")
            if not isinstance(header, str) or not header.startswith("Bearer "):
                self._unauthorized()
                return False
            token = header[7:]
            if not hmac.compare_digest(token, self.server.token):
                self._unauthorized()
                return False
            return True

        def _require_path_uuid(self, value: str) -> bool:
            try:
                uuid.UUID(value)
            except (ValueError, AttributeError):
                self._not_found("resource not found")
                return False
            return True

        def _require_json_body(self) -> dict[str, Any] | None:
            content_type = self.headers.get("Content-Type")
            if not isinstance(content_type, str) or content_type.split(";", 1)[0].strip().lower() != "application/json":
                self._send_json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": {"code": "unsupported_media_type", "message": "content type must be application/json"}})
                return None
            length_header = self.headers.get("Content-Length")
            if length_header is None:
                self._bad_request("Content-Length header is required")
                return None
            try:
                content_length = int(length_header)
            except ValueError:
                self._bad_request("Content-Length must be an integer")
                return None
            if content_length < 0:
                self._bad_request("Content-Length must be non-negative")
                return None
            if content_length > MAX_BODY_BYTES:
                self._send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": {"code": "request_too_large", "message": f"request body exceeds {MAX_BODY_BYTES} bytes"}})
                return None
            body_status, raw = read_request_body(self.rfile, content_length)
            if body_status == "too_large":
                self._send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": {"code": "request_too_large", "message": f"request body exceeds {MAX_BODY_BYTES} bytes"}})
                return None
            if body_status == "incomplete":
                self._send_json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": {"code": "incomplete_body", "message": "request body shorter than Content-Length"}},
                )
                return None
            try:
                payload = json.loads(raw.decode("utf-8") or "{}")
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._bad_request("request body must be valid JSON")
                return None
            if not isinstance(payload, dict):
                self._bad_request("request body must be a JSON object")
                return None
            return payload

        def _send_json(self, status: HTTPStatus, payload: dict[str, Any], *, cache_api: bool = True) -> None:
            body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self._send_common_headers(content_type="application/json; charset=utf-8", content_length=len(body), cache_api=cache_api)
            self.end_headers()
            self.wfile.write(body)

        def _send_common_headers(self, *, content_type: str, content_length: int, cache_api: bool) -> None:
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(content_length))
            for key, value in SECURITY_HEADERS.items():
                self.send_header(key, value)
            if cache_api:
                self.send_header("Cache-Control", "no-store")

        def _bad_request(self, message: str) -> None:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": {"code": "bad_request", "message": message}})

        def _unauthorized(self) -> None:
            self._send_json(HTTPStatus.UNAUTHORIZED, {"error": {"code": "unauthorized", "message": "valid bearer token required"}})

        def _not_found(self, message: str, *, cache_api: bool = True) -> None:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": {"code": "not_found", "message": message}}, cache_api=cache_api)

        def _conflict(self, message: str, current: dict[str, Any]) -> None:
            self._send_json(
                HTTPStatus.CONFLICT,
                {"error": {"code": "conflict", "message": message}, "current": current},
            )

        def _method_not_allowed(self, allow: set[str], *, cache_api: bool = True) -> None:
            body = json.dumps(
                {"error": {"code": "method_not_allowed", "message": "method not allowed"}},
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
            self.send_response(HTTPStatus.METHOD_NOT_ALLOWED)
            self.send_header("Allow", ", ".join(sorted(allow)))
            self._send_common_headers(
                content_type="application/json; charset=utf-8",
                content_length=len(body),
                cache_api=cache_api,
            )
            self.end_headers()
            self.wfile.write(body)

    return DeliveryHTTPServer(
        (host, port),
        RequestHandler,
        token=token.strip() if isinstance(token, str) and token.strip() else None,
        app_store=app_store,
        web_root=resolved_web_root,
        read_timeout=read_timeout,
    )
