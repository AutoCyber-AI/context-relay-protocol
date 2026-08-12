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

// Render a detected-model summary card body. Returns HTML.
function renderModel(m) {
  if (!m) return `<p class="muted">No model loaded.</p>`;
  const util = m.context_utilisation != null
    ? (m.context_utilisation * 100).toFixed(1) + "%" : "—";
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
      <div class="kpi"><div class="v">${(m.max_context_length||0).toLocaleString()}</div><div class="k">Max context</div></div>
      <div class="kpi"><div class="v">${(m.loaded_context_length||0).toLocaleString()}</div><div class="k">Loaded window</div></div>
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
    `<tr><td>${esc(k)}</td><td>${esc(headers[k])}</td></tr>`).join("");
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
