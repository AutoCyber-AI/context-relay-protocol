// Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
// Licensed under Elastic License 2.0 — see LICENSE.md for details.
// Shared client helpers for the CRP demo apps.

async function apiGet(path) {
  const r = await fetch(path);
  return r.json();
}

async function apiPost(path, body) {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  return r.json();
}

function el(id) { return document.getElementById(id); }

function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function pill(text, cls) {
  return `<span class="pill ${cls}">${esc(text)}</span>`;
}

// ── Human-readable labels for wire-level enum values ────────────────────────
// Raw codes stay visible (small <code> tags / collapsible raw views) so the
// consoles remain honest about what is on the wire.

// Fallback rendering for crp_halt_reason when the 451 body predates the
// crp_halt_explanation field. Bodies from crp >= 6.1.2 carry the explanation
// already, so these are only a safety net.
const HALT_REASON_FALLBACK = {
  CRITICAL_HALLUCINATION_RISK: ["Critical hallucination risk",
    "CRP halted the response because its analysis indicates a critical risk that the model invented or distorted facts."],
  UNACCEPTABLE_EU_AI_ACT: ["Prohibited under the EU AI Act",
    "CRP halted the response because the request falls under a practice the EU AI Act prohibits."],
  SAFETY_BUDGET_DEPLETED: ["Safety budget depleted",
    "CRP halted the session because its multi-agent safety budget was consumed by repeated high-risk activity."],
  GROUNDING_BELOW_THRESHOLD: ["Answer not grounded in allowed sources",
    "CRP halted the response because too few of its claims trace back to the provided context."],
  QUALITY_TIER_REJECTED: ["Answer below required quality tier",
    "CRP halted the response because its quality tier is lower than the policy minimum."],
  UNTRUSTED_SOURCE: ["Untrusted source used",
    "CRP halted the response because it relied on a source the policy does not trust."],
  PROMPT_INJECTION_DETECTED: ["Prompt injection detected",
    "CRP halted the response because its input shield detected an attempt to override the system's instructions."],
  SAFETY_POLICY_VIOLATION: ["Safety policy violated",
    "CRP halted the response because it violated one or more directives in the safety policy."],
};

const VIOLATION_LABELS = {
  HALT_ON_RISK: "Risk above halt threshold",
  WARN_ON_RISK: "Risk above warn threshold",
  GROUNDING_BELOW_THRESHOLD: "Grounding below policy threshold",
  ENTAILMENT_BELOW_THRESHOLD: "Entailment below policy threshold",
  QUALITY_TIER_REJECTED: "Quality tier below policy minimum",
  FLOW_BELOW_THRESHOLD: "Flow below policy threshold",
  COMPLETENESS_BELOW_THRESHOLD: "Answer incomplete",
  UNGROUNDED_CLAIM: "Ungrounded claim",
  PARAMETRIC_CONTENT: "Model-internal (parametric) claim",
  PII_DETECTED: "Personal data detected",
  FABRICATION_DETECTED: "Fabricated claim detected",
  MIXED_CONTENT: "Partially grounded claim",
  REPETITION_EXCEEDED: "Repetition exceeded",
  SOURCE_NOT_TRUSTED: "Untrusted source",
};

const ACTION_LABELS = {
  PASS: "passed", WARN: "warned", CONTINUE: "continue",
  REDISPATCH: "re-dispatch", HALT: "halted",
};

function violationLabel(type) {
  return VIOLATION_LABELS[type] || type;
}

// Render one CRP-* header value; known machine formats get a plain-English
// rendering with the raw wire value kept alongside in a <code> tag.
function formatHeaderValue(key, value) {
  const raw = `<code>${esc(value)}</code>`;
  if (key === "CRP-Quality-Completeness") {
    // "PARTIAL; sub-queries=1/3; uncovered=foo,bar" → plain English.
    const m = /^([A-Z_]+); sub-queries=(\d+)\/(\d+)(?:; uncovered=(.*))?$/.exec(value || "");
    if (m) {
      const level = m[1].replace(/_/g, " ").toLowerCase();
      const covered = +m[2], total = +m[3];
      const uncovered = m[4] ? m[4].split(",").join(", ") : "";
      let text = `Answer ${level} - covered ${covered} of ${total} sub-questions.`;
      if (uncovered) text += ` Uncovered: ${uncovered}.`;
      return `${esc(text)} ${raw}`;
    }
    return raw;
  }
  if (value === "oversight-required") {
    return `Human oversight required before retry ${raw}`;
  }
  return raw;
}

// Render a detected-model summary card body. Returns HTML.
function renderModel(m) {
  if (!m) return `<p class="muted">No model loaded.</p>`;
  const util = m.context_utilisation != null
    ? (m.context_utilisation * 100).toFixed(1) + "%" : " - ";
  const caps = [];
  if (m.supports_tools) caps.push(pill("tools / MCP", "blue"));
  if (m.is_reasoning_model) caps.push(pill("reasoning", "amber"));
  if (m.is_vision_model) caps.push(pill("vision", "blue"));
  caps.push(pill(m.state, m.state === "loaded" ? "green" : "grey"));
  return `
    <div class="flex-between">
      <div><b>${esc(m.id)}</b> <span class="tag">via ${esc(m.runtime)}</span></div>
      <div class="flex">${caps.join(" ")}</div>
    </div>
    <div class="grid cols-3" style="margin-top:0.8rem">
      <div class="kpi"><div class="v">${m.max_context_length != null ? m.max_context_length.toLocaleString() : "unknown"}</div><div class="k">Max context</div></div>
      <div class="kpi"><div class="v">${m.loaded_context_length != null ? m.loaded_context_length.toLocaleString() : "unknown"}</div><div class="k">Loaded window</div></div>
      <div class="kpi ${m.context_utilisation && m.context_utilisation < 0.2 ? 'warn':''}"><div class="v">${util}</div><div class="k">Utilisation</div></div>
    </div>
    <p class="tag" style="margin-top:0.6rem">arch: ${esc(m.architecture||"?")} · quant: ${esc(m.quantization||"?")} · type: ${esc(m.model_type)}</p>
  `;
}

// Render the CRP-* header set as a table.
function renderHeaders(headers) {
  const keys = Object.keys(headers || {}).sort();
  if (!keys.length) return `<p class="muted">No headers.</p>`;
  const rows = keys.map(k =>
    `<tr><td>${esc(k)}</td><td>${formatHeaderValue(k, headers[k])}</td></tr>`).join("");
  return `<table class="hdr-table">${rows}</table>`;
}

function setBusy(btn, busy, label) {
  if (!btn) return;
  btn.disabled = busy;
  if (busy) {
    btn.dataset.label = btn.innerHTML;
    btn.innerHTML = `<span class="spinner"></span> ${label || "Working…"}`;
  } else if (btn.dataset.label) {
    btn.innerHTML = btn.dataset.label;
  }
}
