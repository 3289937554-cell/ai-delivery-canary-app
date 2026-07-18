const TOKEN_STORAGE_KEY = "delivery-ops-token";
const STORAGE = window.sessionStorage;

const releaseStatusOrder = ["planned", "validating", "blocked", "ready", "released", "rolled_back"];
const gateStatusOrder = ["pending", "passed", "failed", "waived"];
const riskStatusOrder = ["open", "mitigated", "accepted", "closed"];
const riskSeverities = ["low", "medium", "high", "critical"];

const releaseTransitions = {
  planned: ["validating"],
  validating: ["blocked", "ready"],
  blocked: ["validating"],
  ready: ["validating", "released"],
  released: ["rolled_back"],
  rolled_back: [],
};

const gateTransitions = {
  pending: ["passed", "failed", "waived"],
  passed: ["pending"],
  failed: ["pending", "passed", "waived"],
  waived: ["pending"],
};

const riskTransitions = {
  open: ["mitigated", "accepted", "closed"],
  mitigated: ["open", "accepted", "closed"],
  accepted: ["open", "closed"],
  closed: ["open"],
};

const state = {
  connected: false,
  releases: [],
  selectedReleaseId: null,
  selectedReleaseAudit: [],
  globalAudit: [],
  auditMode: "release",
  query: "",
  token: STORAGE.getItem(TOKEN_STORAGE_KEY) || "",
  pending: {
    releases: false,
    detail: false,
  },
  flash: null,
  pendingMutation: null,
};

const ui = {
  connectionIndicator: document.getElementById("connection-indicator"),
  connectionText: document.getElementById("connection-text"),
  tokenForm: document.getElementById("token-form"),
  tokenInput: document.getElementById("token-input"),
  clearToken: document.getElementById("clear-token"),
  flashBanner: document.getElementById("flash-banner"),
  liveRegion: document.getElementById("live-region"),
  releaseSearch: document.getElementById("release-search"),
  releaseList: document.getElementById("release-list"),
  releaseTable: document.getElementById("release-table"),
  releaseTableBody: document.getElementById("release-table-body"),
  releaseListState: document.getElementById("release-list-state"),
  createReleaseForm: document.getElementById("create-release-form"),
  releaseTitle: document.getElementById("release-title"),
  releaseStatusBadge: document.getElementById("release-status-badge"),
  releaseVersion: document.getElementById("release-version"),
  releaseCreated: document.getElementById("release-created"),
  releaseUpdated: document.getElementById("release-updated"),
  updateReleaseForm: document.getElementById("update-release-form"),
  gateList: document.getElementById("gate-list"),
  createGateForm: document.getElementById("create-gate-form"),
  riskList: document.getElementById("risk-list"),
  createRiskForm: document.getElementById("create-risk-form"),
  auditScope: document.getElementById("audit-scope"),
  auditList: document.getElementById("audit-list"),
};

boot();

function boot() {
  ui.tokenInput.value = state.token;
  ui.auditScope.value = state.auditMode;
  ui.tokenForm.addEventListener("submit", handleTokenSave);
  ui.clearToken.addEventListener("click", handleTokenClear);
  ui.releaseSearch.addEventListener("input", () => {
    state.query = ui.releaseSearch.value.trim().toLowerCase();
    renderReleaseList();
  });
  ui.auditScope.addEventListener("change", async () => {
    state.auditMode = ui.auditScope.value;
    await refreshAuditData({ preserveFlash: true });
    renderDetail();
  });
  ui.createReleaseForm.addEventListener("submit", handleCreateRelease);
  ui.updateReleaseForm.addEventListener("submit", handleUpdateRelease);
  ui.createGateForm.addEventListener("submit", handleCreateGate);
  ui.createRiskForm.addEventListener("submit", handleCreateRisk);
  ui.gateList.addEventListener("submit", handleGateAction);
  ui.riskList.addEventListener("submit", handleRiskAction);
  refreshAll();
}

async function refreshAll(preferredReleaseId, options = {}) {
  const preserveFlash = options.preserveFlash === true;
  state.pending.releases = true;
  state.pending.detail = true;
  renderConnection();
  renderReleaseList();
  renderDetail();
  try {
    await fetchHealth();
    const releasesResponse = await request("/api/releases");
    if (!releasesResponse.ok) {
      throw releasesResponse;
    }
    state.releases = sortReleases(releasesResponse.body.releases || []);
    state.selectedReleaseId = chooseReleaseId(preferredReleaseId);
    await refreshAuditData({ preserveFlash: true });
    if (!preserveFlash && (!state.flash || state.flash.sticky !== true)) {
      clearFlash();
    }
  } catch (error) {
    if (isNetworkError(error)) {
      state.connected = false;
      setFlash("offline", "The console is offline. Check the local server and retry.");
    } else if (error && error.body && error.body.error) {
      setFlash("error", error.body.error.message);
    } else {
      setFlash("error", "Unable to refresh the console state.");
    }
  } finally {
    state.pending.releases = false;
    state.pending.detail = false;
    renderConnection();
    renderReleaseList();
    renderDetail();
  }
}

async function refreshAuditData(options = {}) {
  const preserveFlash = options.preserveFlash === true;
  if (state.auditMode === "all") {
    const response = await request("/api/audit");
    if (!response.ok) {
      if (!preserveFlash) {
        throw response;
      }
      state.globalAudit = [];
      return;
    }
    state.globalAudit = sortAuditEvents(response.body.events || []);
    return;
  }
  if (!state.selectedReleaseId) {
    state.selectedReleaseAudit = [];
    return;
  }
  const response = await request(`/api/releases/${state.selectedReleaseId}/audit`);
  if (!response.ok) {
    if (!preserveFlash) {
      throw response;
    }
    state.selectedReleaseAudit = [];
    return;
  }
  state.selectedReleaseAudit = sortAuditEvents(response.body.events || []);
}

async function fetchHealth() {
  const response = await request("/api/health");
  state.connected = response.ok;
  renderConnection();
  return response;
}

function chooseReleaseId(preferredReleaseId) {
  if (preferredReleaseId && state.releases.some((release) => release.id === preferredReleaseId)) {
    return preferredReleaseId;
  }
  if (state.selectedReleaseId && state.releases.some((release) => release.id === state.selectedReleaseId)) {
    return state.selectedReleaseId;
  }
  return state.releases.length > 0 ? state.releases[0].id : null;
}

function renderConnection() {
  ui.connectionIndicator.classList.toggle("status-chip--offline", !state.connected);
  ui.connectionText.textContent = state.connected ? "Connected" : "Offline";
  renderFlash();
}

function renderReleaseList() {
  toggleFormDisabled(ui.createReleaseForm, state.pending.releases);
  if (state.pending.releases) {
    ui.releaseTable.hidden = true;
    ui.releaseListState.innerHTML = `
      <div class="release-card release-card--loading"></div>
      <div class="release-card release-card--loading"></div>
      <div class="release-card release-card--loading"></div>
    `;
    return;
  }

  const visibleReleases = state.releases.filter((release) => {
    if (!state.query) {
      return true;
    }
    return `${release.title} ${release.version}`.toLowerCase().includes(state.query);
  });

  if (visibleReleases.length === 0) {
    ui.releaseTable.hidden = true;
    ui.releaseListState.innerHTML = `
      <div class="empty-state">
        <h3>No releases available</h3>
        <p>Create a release or clear the search filter.</p>
      </div>
    `;
    return;
  }

  ui.releaseTable.hidden = false;
  ui.releaseListState.innerHTML = "";
  ui.releaseTableBody.innerHTML = visibleReleases
    .map((release) => {
      const selected = release.id === state.selectedReleaseId;
      const gates = release.gates || [];
      const clearedGates = gates.filter((gate) => gate.status === "passed" || gate.status === "waived").length;
      const openRisks = (release.risks || []).filter((risk) => risk.status === "open").length;
      return `
        <tr class="release-row ${selected ? "release-row--selected" : ""}">
          <td data-label="Title"><button type="button" class="release-link" data-release-id="${escapeHtml(release.id)}">${escapeHtml(release.title)}</button></td>
          <td data-label="Version">${escapeHtml(release.version)}</td>
          <td data-label="Status"><span class="status-badge status-badge--${escapeHtml(release.status)}">${escapeHtml(release.status)}</span></td>
          <td data-label="Gates">${clearedGates}/${gates.length} cleared</td>
          <td data-label="Open risks">${openRisks}</td>
        </tr>
      `;
    })
    .join("");

  ui.releaseTableBody.querySelectorAll("[data-release-id]").forEach((button) => {
    button.addEventListener("click", async () => {
      state.selectedReleaseId = button.getAttribute("data-release-id");
      await refreshAuditData({ preserveFlash: true });
      renderReleaseList();
      renderDetail();
    });
  });
}

function renderDetail() {
  const release = currentRelease();
  const disabled = !release || state.pending.detail;
  toggleFormDisabled(ui.updateReleaseForm, disabled);
  toggleFormDisabled(ui.createGateForm, disabled);
  toggleFormDisabled(ui.createRiskForm, disabled);

  if (!release) {
    ui.releaseTitle.textContent = "No release selected";
    ui.releaseStatusBadge.textContent = "planned";
    ui.releaseStatusBadge.className = "status-badge status-badge--planned";
    ui.releaseVersion.textContent = "-";
    ui.releaseCreated.textContent = "-";
    ui.releaseUpdated.textContent = "-";
    ui.gateList.innerHTML = `<div class="empty-state empty-state--inline"><p>Select a release to inspect its delivery record.</p></div>`;
    ui.riskList.innerHTML = `<div class="empty-state empty-state--inline"><p>Select a release to inspect current risks.</p></div>`;
    renderAuditList(currentAuditEvents());
    return;
  }

  ui.releaseTitle.textContent = release.title;
  ui.releaseStatusBadge.textContent = release.status;
  ui.releaseStatusBadge.className = `status-badge status-badge--${release.status}`;
  ui.releaseVersion.textContent = release.version;
  ui.releaseCreated.textContent = formatDateTime(release.created_at);
  ui.releaseUpdated.textContent = formatDateTime(release.updated_at);
  ui.updateReleaseForm.elements.title.value = release.title;
  ui.updateReleaseForm.elements.version.value = release.version;
  setSelectOptions(ui.updateReleaseForm.elements.status, allowedReleaseStatuses(release), release.status);

  renderGateList(release.gates || []);
  renderRiskList(release.risks || []);
  renderAuditList(currentAuditEvents());
}

function renderGateList(gates) {
  if (!gates.length) {
    ui.gateList.innerHTML = `<div class="empty-state empty-state--inline"><p>No gates recorded for this release.</p></div>`;
    return;
  }
  ui.gateList.innerHTML = gates
    .map((gate) => {
      const statuses = allowedGateStatuses(gate);
      return `
        <form class="gate-card" data-gate-id="${escapeHtml(gate.id)}" novalidate>
          <div class="gate-card__head">
            <div>
              <h3>${escapeHtml(gate.name)}</h3>
              <p>${gate.required ? "Required gate" : "Optional gate"}</p>
            </div>
            <span class="status-badge status-badge--${escapeHtml(gate.status)}">${escapeHtml(gate.status)}</span>
          </div>
          <div class="field-row field-row--compact">
            <div>
              <label for="gate-status-${escapeHtml(gate.id)}">Status</label>
              <select id="gate-status-${escapeHtml(gate.id)}" name="status" aria-describedby="gate-status-error-${escapeHtml(gate.id)}">
                ${statuses.map((status) => `<option value="${status}" ${status === gate.status ? "selected" : ""}>${status}</option>`).join("")}
              </select>
              <p class="field-error" id="gate-status-error-${escapeHtml(gate.id)}" data-field-error></p>
            </div>
            <div class="field-grow">
              <label for="gate-reason-${escapeHtml(gate.id)}">Waiver reason</label>
              <input id="gate-reason-${escapeHtml(gate.id)}" name="waiver_reason" type="text" maxlength="500" value="${escapeAttribute(gate.waiver_reason || "")}" aria-describedby="gate-reason-error-${escapeHtml(gate.id)}">
              <p class="field-error" id="gate-reason-error-${escapeHtml(gate.id)}" data-field-error></p>
            </div>
            <label class="checkbox checkbox--compact">
              <input name="required" type="checkbox" ${gate.required ? "checked" : ""}>
              <span>Required</span>
            </label>
          </div>
          <button type="submit" class="button button--ghost">Save gate</button>
        </form>
      `;
    })
    .join("");
}

function renderRiskList(risks) {
  if (!risks.length) {
    ui.riskList.innerHTML = `<div class="empty-state empty-state--inline"><p>No risks recorded for this release.</p></div>`;
    return;
  }
  ui.riskList.innerHTML = risks
    .map((risk) => {
      const statuses = allowedRiskStatuses(risk);
      return `
        <form class="risk-card risk-card--${escapeHtml(risk.severity)}" data-risk-id="${escapeHtml(risk.id)}" novalidate>
          <div class="risk-card__head">
            <div>
              <h3>${escapeHtml(risk.description)}</h3>
              <p>${escapeHtml(risk.severity)} severity</p>
            </div>
            <span class="status-badge status-badge--${escapeHtml(risk.status)}">${escapeHtml(risk.status)}</span>
          </div>
          <div class="field-row field-row--compact">
            <div>
              <label for="risk-status-${escapeHtml(risk.id)}">Status</label>
              <select id="risk-status-${escapeHtml(risk.id)}" name="status" aria-describedby="risk-status-error-${escapeHtml(risk.id)}">
                ${statuses.map((status) => `<option value="${status}" ${status === risk.status ? "selected" : ""}>${status}</option>`).join("")}
              </select>
              <p class="field-error" id="risk-status-error-${escapeHtml(risk.id)}" data-field-error></p>
            </div>
            <div>
              <label for="risk-severity-${escapeHtml(risk.id)}">Severity</label>
              <select id="risk-severity-${escapeHtml(risk.id)}" name="severity">
                ${riskSeverities.map((severity) => `<option value="${severity}" ${severity === risk.severity ? "selected" : ""}>${severity}</option>`).join("")}
              </select>
            </div>
            <label class="checkbox checkbox--compact">
              <input name="blocking" type="checkbox" ${risk.blocking ? "checked" : ""}>
              <span>Blocking</span>
            </label>
          </div>
          <div class="field-row field-row--compact">
            <div class="field-grow">
              <label for="risk-reason-${escapeHtml(risk.id)}">Acceptance reason</label>
              <input id="risk-reason-${escapeHtml(risk.id)}" name="acceptance_reason" type="text" maxlength="500" value="${escapeAttribute(risk.acceptance_reason || "")}" aria-describedby="risk-reason-error-${escapeHtml(risk.id)}">
              <p class="field-error" id="risk-reason-error-${escapeHtml(risk.id)}" data-field-error></p>
            </div>
          </div>
          <button type="submit" class="button button--ghost">Save risk</button>
        </form>
      `;
    })
    .join("");
}

function renderAuditList(events) {
  if (!events.length) {
    ui.auditList.innerHTML = `<div class="empty-state empty-state--inline"><p>No audit events recorded for this scope.</p></div>`;
    return;
  }
  ui.auditList.innerHTML = events
    .map((event) => {
      return `
        <article class="timeline-item">
          <span class="timeline-item__dot" aria-hidden="true"></span>
          <div>
            <h3>${escapeHtml(describeAuditEvent(event))}</h3>
            <p>${escapeHtml(event.actor)} · ${formatDateTime(event.created_at)}</p>
          </div>
        </article>
      `;
    })
    .join("");
}

async function handleTokenSave(event) {
  event.preventDefault();
  state.token = ui.tokenInput.value.trim();
  STORAGE.setItem(TOKEN_STORAGE_KEY, state.token);
  announce("Token saved.");
  if (state.pendingMutation) {
    await retryPendingMutation();
    return;
  }
  setFlash("success", "Token saved for authenticated changes.", { sticky: true });
}

function handleTokenClear() {
  state.token = "";
  ui.tokenInput.value = "";
  STORAGE.removeItem(TOKEN_STORAGE_KEY);
  announce("Token cleared.");
  setFlash("success", "Token cleared.", { sticky: true });
  ui.tokenInput.focus();
}

async function handleCreateRelease(event) {
  event.preventDefault();
  if (!validateForm(event.currentTarget)) {
    return;
  }
  const form = event.currentTarget;
  const payload = {
    title: form.elements.title.value.trim(),
    version: form.elements.version.value.trim(),
  };
  await submitMutation({
    path: "/api/releases",
    method: "POST",
    payload,
    successMessage: "Release created.",
    onSuccess: async (body) => {
      form.reset();
      await refreshAll(body.id, { preserveFlash: true });
    },
    form,
    focusField: form.elements.title,
  });
}

async function handleUpdateRelease(event) {
  event.preventDefault();
  const release = currentRelease();
  if (!release) {
    setFlash("validation", "Select a release before updating it.");
    return;
  }
  if (!validateForm(event.currentTarget)) {
    return;
  }
  const form = event.currentTarget;
  const payload = {
    title: form.elements.title.value.trim(),
    version: form.elements.version.value.trim(),
    status: form.elements.status.value,
  };
  await submitMutation({
    path: `/api/releases/${release.id}`,
    method: "PATCH",
    payload,
    successMessage: "Release saved.",
    onSuccess: async () => {
      await refreshAll(release.id, { preserveFlash: true });
    },
    form,
    focusField: form.elements.title,
  });
}

async function handleCreateGate(event) {
  event.preventDefault();
  const release = currentRelease();
  if (!release) {
    setFlash("validation", "Select a release before adding a gate.");
    return;
  }
  const form = event.currentTarget;
  if (!validateForm(form)) {
    return;
  }
  const payload = {
    name: form.elements.name.value.trim(),
    required: form.elements.required.checked,
  };
  await submitMutation({
    path: `/api/releases/${release.id}/gates`,
    method: "POST",
    payload,
    successMessage: "Gate saved.",
    onSuccess: async () => {
      form.reset();
      form.elements.required.checked = true;
      await refreshAll(release.id, { preserveFlash: true });
    },
    form,
    focusField: form.elements.name,
  });
}

async function handleCreateRisk(event) {
  event.preventDefault();
  const release = currentRelease();
  if (!release) {
    setFlash("validation", "Select a release before adding a risk.");
    return;
  }
  const form = event.currentTarget;
  if (!validateForm(form)) {
    return;
  }
  const payload = {
    description: form.elements.description.value.trim(),
    severity: form.elements.severity.value,
    blocking: form.elements.blocking.checked,
  };
  await submitMutation({
    path: `/api/releases/${release.id}/risks`,
    method: "POST",
    payload,
    successMessage: "Risk saved.",
    onSuccess: async () => {
      form.reset();
      await refreshAll(release.id, { preserveFlash: true });
    },
    form,
    focusField: form.elements.description,
  });
}

async function handleGateAction(event) {
  event.preventDefault();
  const release = currentRelease();
  if (!release) {
    return;
  }
  const form = event.target;
  if (!(form instanceof HTMLFormElement)) {
    return;
  }
  const gateId = form.getAttribute("data-gate-id");
  if (!gateId) {
    return;
  }
  clearFieldErrors(form);
  const reasonField = form.elements.waiver_reason;
  const status = form.elements.status.value;
  if (status === "waived" && !reasonField.value.trim()) {
    setFlash("validation", "A waiver reason is required when a gate is waived.");
    setFieldError(reasonField, "A waiver reason is required when a gate is waived.");
    focusFirstInvalidField(form);
    return;
  }
  const payload = {
    status,
    required: form.elements.required.checked,
  };
  if (reasonField.value.trim()) {
    payload.waiver_reason = reasonField.value.trim();
  } else if (status !== "waived") {
    payload.waiver_reason = null;
  }
  await submitMutation({
    path: `/api/releases/${release.id}/gates/${gateId}`,
    method: "PATCH",
    payload,
    successMessage: "Gate updated.",
    onSuccess: async () => {
      await refreshAll(release.id, { preserveFlash: true });
    },
    form,
    focusField: form.elements.status,
  });
}

async function handleRiskAction(event) {
  event.preventDefault();
  const release = currentRelease();
  if (!release) {
    return;
  }
  const form = event.target;
  if (!(form instanceof HTMLFormElement)) {
    return;
  }
  const riskId = form.getAttribute("data-risk-id");
  if (!riskId) {
    return;
  }
  clearFieldErrors(form);
  const reasonField = form.elements.acceptance_reason;
  const status = form.elements.status.value;
  if (status === "accepted" && !reasonField.value.trim()) {
    setFlash("validation", "An acceptance reason is required when a risk is accepted.");
    setFieldError(reasonField, "An acceptance reason is required when a risk is accepted.");
    focusFirstInvalidField(form);
    return;
  }
  const payload = {
    status,
    severity: form.elements.severity.value,
    blocking: form.elements.blocking.checked,
  };
  if (reasonField.value.trim()) {
    payload.acceptance_reason = reasonField.value.trim();
  } else if (status !== "accepted") {
    payload.acceptance_reason = null;
  }
  await submitMutation({
    path: `/api/releases/${release.id}/risks/${riskId}`,
    method: "PATCH",
    payload,
    successMessage: "Risk updated.",
    onSuccess: async () => {
      await refreshAll(release.id, { preserveFlash: true });
    },
    form,
    focusField: form.elements.status,
  });
}

async function submitMutation(mutation) {
  if (!state.token) {
    state.pendingMutation = mutation;
    setFlash("unauthorized", "Token required for changes.");
    ui.tokenInput.focus();
    return;
  }
  try {
    const response = await request(mutation.path, {
      method: mutation.method,
      headers: authHeaders(),
      body: JSON.stringify(mutation.payload),
    });
    if (!response.ok) {
      await handleMutationError(response, mutation);
      return;
    }
    state.pendingMutation = null;
    setFlash("success", mutation.successMessage, { sticky: true });
    announce(mutation.successMessage);
    await mutation.onSuccess(response.body);
  } catch (error) {
    if (isNetworkError(error)) {
      state.connected = false;
      renderConnection();
      setFlash("offline", "The console is offline. Check the local server and retry.");
      return;
    }
    setFlash("error", "Unable to apply the requested change.");
  }
}

async function retryPendingMutation() {
  if (!state.pendingMutation) {
    return;
  }
  const mutation = state.pendingMutation;
  state.pendingMutation = null;
  await submitMutation(mutation);
}

async function handleMutationError(response, mutation) {
  const message = response.body && response.body.error ? response.body.error.message : "Unable to apply the requested change.";
  if (response.status === 401) {
    state.pendingMutation = mutation;
    setFlash("unauthorized", message);
    ui.tokenInput.focus();
    return;
  }
  if (response.status === 409) {
    const current = response.body && response.body.current ? response.body.current : null;
    const conflictMessage = current ? `${message} ${summarizeCurrentState(current)}` : message;
    setFlash("conflict", conflictMessage);
    if (current && current.id) {
      await refreshAll(current.id, { preserveFlash: true });
    }
    setMutationFieldError(mutation, message);
    return;
  }
  if (response.status === 400 || response.status === 415 || response.status === 413) {
    setFlash("validation", message);
    setMutationFieldError(mutation, message);
    return;
  }
  setFlash("error", message);
}

function setFlash(kind, message, options = {}) {
  state.flash = {
    kind,
    message,
    sticky: options.sticky === true,
  };
  renderFlash();
}

function renderFlash() {
  if (!state.flash) {
    ui.flashBanner.textContent = "";
    ui.flashBanner.className = "flash flash--hidden";
    return;
  }
  ui.flashBanner.textContent = state.flash.message;
  ui.flashBanner.className = `flash flash--${state.flash.kind}`;
}

function clearFlash() {
  state.flash = null;
  renderFlash();
}

function announce(message) {
  ui.liveRegion.textContent = "";
  window.setTimeout(() => {
    ui.liveRegion.textContent = message;
  }, 30);
}

function validateForm(form) {
  clearFieldErrors(form);
  if (form.checkValidity()) {
    return true;
  }
  form.querySelectorAll(":invalid").forEach((field) => {
    setFieldError(field, field.validationMessage);
  });
  focusFirstInvalidField(form);
  return false;
}

function clearFieldErrors(form) {
  form.querySelectorAll("[aria-invalid='true']").forEach((field) => {
    field.removeAttribute("aria-invalid");
  });
  form.querySelectorAll("[data-field-error]").forEach((error) => {
    error.textContent = "";
  });
}

function setFieldError(field, message) {
  if (!field) {
    return;
  }
  field.setAttribute("aria-invalid", "true");
  const describedBy = (field.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean);
  const error = describedBy
    .map((id) => document.getElementById(id))
    .find((element) => element && element.hasAttribute("data-field-error"));
  if (error) {
    error.textContent = message;
  }
}

function focusFirstInvalidField(form) {
  const invalidField = form.querySelector("[aria-invalid='true'], :invalid");
  if (invalidField) {
    invalidField.focus();
  }
}

function setMutationFieldError(mutation, message) {
  const form = resolveMutationForm(mutation);
  if (!form) {
    if (mutation.focusField) {
      mutation.focusField.focus();
    }
    return;
  }
  clearFieldErrors(form);
  const normalizedMessage = message.toLowerCase().replaceAll("_", " ");
  const fields = Array.from(form.elements).filter((element) => element.name);
  const field = fields.find((element) => normalizedMessage.includes(element.name.replaceAll("_", " ")))
    || (form.contains(mutation.focusField) ? mutation.focusField : fields[0]);
  setFieldError(field, message);
  focusFirstInvalidField(form);
}

function resolveMutationForm(mutation) {
  if (mutation.form && document.body.contains(mutation.form)) {
    return mutation.form;
  }
  const parts = mutation.path.split("/").filter(Boolean);
  const entityId = parts[parts.length - 1];
  if (parts.includes("gates")) {
    return ui.gateList.querySelector(`[data-gate-id="${CSS.escape(entityId)}"]`);
  }
  if (parts.includes("risks")) {
    return ui.riskList.querySelector(`[data-risk-id="${CSS.escape(entityId)}"]`);
  }
  return mutation.form || null;
}

function toggleFormDisabled(form, disabled) {
  Array.from(form.elements).forEach((element) => {
    element.disabled = disabled;
  });
}

function currentRelease() {
  return state.releases.find((release) => release.id === state.selectedReleaseId) || null;
}

function currentAuditEvents() {
  return state.auditMode === "all" ? state.globalAudit : state.selectedReleaseAudit;
}

function authHeaders() {
  return {
    Authorization: `Bearer ${state.token}`,
    "Content-Type": "application/json",
  };
}

async function request(path, options = {}) {
  const response = await window.fetch(path, options);
  let body = null;
  const text = await response.text();
  if (text) {
    try {
      body = JSON.parse(text);
    } catch (error) {
      body = null;
    }
  }
  return {
    ok: response.ok,
    status: response.status,
    body,
    headers: response.headers,
  };
}

function isNetworkError(error) {
  return error instanceof TypeError;
}

function sortReleases(releases) {
  return releases.slice().sort((left, right) => {
    const statusDelta = releaseStatusOrder.indexOf(left.status) - releaseStatusOrder.indexOf(right.status);
    if (statusDelta !== 0) {
      return statusDelta;
    }
    return right.updated_at.localeCompare(left.updated_at);
  });
}

function sortAuditEvents(events) {
  return events.slice().sort((left, right) => right.created_at.localeCompare(left.created_at));
}

function allowedReleaseStatuses(release) {
  const allowed = new Set([release.status, ...releaseTransitions[release.status]]);
  if (!releaseCanBecomeReady(release)) {
    allowed.delete("ready");
  }
  return releaseStatusOrder.filter((status) => allowed.has(status));
}

function allowedGateStatuses(gate) {
  const allowed = new Set([gate.status, ...(gateTransitions[gate.status] || [])]);
  return gateStatusOrder.filter((status) => allowed.has(status));
}

function allowedRiskStatuses(risk) {
  const allowed = new Set([risk.status, ...(riskTransitions[risk.status] || [])]);
  return riskStatusOrder.filter((status) => allowed.has(status));
}

function releaseCanBecomeReady(release) {
  return release.gates.every((gate) => !gate.required || gate.status === "passed" || gate.status === "waived")
    && release.risks.every((risk) => !risk.blocking || (risk.status !== "open" && risk.status !== "mitigated"));
}

function setSelectOptions(selectElement, values, selectedValue) {
  selectElement.innerHTML = values
    .map((value) => `<option value="${escapeHtml(value)}" ${value === selectedValue ? "selected" : ""}>${escapeHtml(value)}</option>`)
    .join("");
}

function describeAuditEvent(event) {
  const release = state.releases.find((item) => item.id === event.release_id);
  const entity = `${event.entity_type} ${String(event.entity_id).slice(0, 8)}`;
  const transition = event.prior_status !== null || event.new_status !== null
    ? ` · ${event.prior_status || "created"} \u2192 ${event.new_status || "unchanged"}`
    : "";
  if (state.auditMode === "all" && release) {
    return `${release.version} ${release.title} · ${entity} · ${event.action}${transition}`;
  }
  return `${entity} · ${event.action}${transition}`;
}

function summarizeCurrentState(current) {
  const title = current.title ? `${current.title} ` : "";
  const version = current.version ? `${current.version} ` : "";
  const status = current.status ? `is ${current.status}.` : "has been refreshed.";
  return `Current server state: ${title}${version}${status}`.trim();
}

function formatDateTime(value) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.valueOf())) {
    return value;
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(parsed);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function escapeAttribute(value) {
  return escapeHtml(value);
}
