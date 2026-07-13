# project-0007 ai-delivery-canary-app Agent Rules

本项目是 AI Delivery Control Plane 的真实低风险 canary 应用，用于验证从 S0 到 S10 的商业级全链路智能化交付闭环。

## Source of Truth

- GitHub Issue / PR / Actions 是交付真源。
- `evidence/GH-<number>/manifest.json` 与 `evidence/AI-DELIVERY-CANARY/commercial-readiness.json` 是证据真源。
- 不在 `main` 直接做实现交付；使用 `ai/GH-<number>-<slug>`。
- 不自动 merge、deploy、改 secrets 或绕过分支保护。

## Validation

每次交付至少运行：

```bash
python3 -m py_compile src/aid_canary_app.py
python3 -m unittest discover -s tests -v
python3 src/aid_canary_app.py --smoke
python3 scripts/validate_evidence_manifest.py evidence/GH-<number>/manifest.json --repo-root . --strict
```
