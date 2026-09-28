// Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
// Licensed under Elastic License 2.0 — see LICENSE.md for details.
// App 5 — CRP Agent vs raw LLM, side-by-side live streaming.

let source = null;
let rawBuf = "";
let rawTimer = null;
let runId = null;

async function loadModelTag() {
  try {
    const d = await apiGet("/api/detect");
    el("model-tag").textContent = d.primary
      ? `${d.primary.id} via ${d.primary.runtime}` : "no model loaded";
  } catch { el("model-tag").textContent = "detection unavailable"; }
}

function scheduleRawRender() {
  if (rawTimer) return;
  rawTimer = setTimeout(() => {
    rawTimer = null;
    el("raw-out").innerHTML = `<div class="md">${mdToHtml(rawBuf)}</div>` || `<p class="muted">thinking…</p>`;
    const pane = el("raw-out");
    pane.scrollTop = pane.scrollHeight;
  }, 250);
}

const EVENT_META = {
  intent_classified: ["intent", "blue"],
  operation_positioned: ["operation", "blue"],
  tool_selected: ["tool selected", "amber"],
  tool_called: ["tool call", "amber"],
  observation_received: ["observation", "green"],
  operation_verified: ["verified", "green"],
  integrated: ["integrated", "green"],
  model_reasoning: ["reasoning", "grey"],
  halt: ["halt", "red"],
  clarification_requested: ["clarify", "amber"],
  trust_decision: ["trust", "grey"],
  kill_switch_fired: ["kill switch", "red"],
  checkpoint_requested: ["checkpoint", "amber"],
  checkpoint_resolved: ["checkpoint ok", "green"],
  warning: ["warning", "amber"],
  final: ["final", "green"],
  governance: ["governance", "blue"],
};

function timelineEntry(ev) {
  const meta = EVENT_META[ev.kind] || [ev.kind, "grey"];
  const div = document.createElement("div");
  div.className = "fact";
  let body = "";
  if (ev.kind === "tool_called") {
    body = `<div class="cat">${esc(JSON.stringify(ev.data || {}).slice(0, 220))}</div>`;
  } else if (ev.kind === "observation_received") {
    const obs = String((ev.data || {}).excerpt || JSON.stringify(ev.data || {}).slice(0, 220));
    body = `<div class="cat">…${esc(obs.slice(0, 220))}…</div>`;
  } else if (ev.detail) {
    body = `<div class="cat">${esc(ev.detail.slice(0, 220))}</div>`;
  }
  div.innerHTML = `${pill(meta[0], meta[1])} ${ev.operation ? `<span class="tag">${esc(ev.operation)}</span>` : ""}${body}`;
  return div;
}

function renderGovernance(gov) {
  if (!gov) return `<p class="muted">No governance metadata - the raw arm has none to give.</p>`;
  const rows = [
    ["risk", gov.risk], ["grounded", gov.grounded],
    ["chain valid", gov.chain_valid], ["operations", (gov.operations || []).length],
    ["sources", (gov.sources || []).length],
  ].map(([k, v]) => `<tr><td>${esc(k)}</td><td>${esc(String(v))}</td></tr>`).join("");
  const ops = (gov.operations || []).map(o =>
    `<span class="pill blue">${esc(typeof o === "string" ? o : (o.op || o.operation || JSON.stringify(o)))}</span>`).join(" ");
  return `<table class="hdr-table">${rows}</table>
    <div class="flex" style="margin-top:0.4rem">${ops}</div>
    <p class="tag" style="margin-top:0.4rem">audit: ${esc(gov.audit_url || " - ")}</p>`;
}

function renderSummary(s, elapsed) {
  el("summary").classList.remove("hide");
  const winner = s.crp_operation_count > 0;
  el("summary").innerHTML = `
    <div class="flex" style="gap:1.6rem">
      <div><div class="tag">raw arm</div><b>${s.raw_word_count.toLocaleString()}</b> words ·
        governance: <b>none</b></div>
      <div><div class="tag">CRP agent</div><b>${s.crp_word_count.toLocaleString()}</b> words ·
        <b>${s.crp_operation_count}</b> operation(s) · governance:
        ${pill("full", "green")}</div>
      <div><div class="tag">elapsed</div><b>${elapsed}s</b></div>
    </div>
    <p style="margin:0.7rem 0 0">${winner
      ? "Same model, same tools, same question. The raw arm could only talk about tools; the CRP agent executed them and answered with provenance."
      : "Both arms answered without tool operations this run - try a question that clearly needs a search."}</p>`;
}

async function runBoth() {
  if (source) return;
  rawBuf = "";
  el("raw-out").innerHTML = `<p class="muted">starting…</p>`;
  el("raw-final").innerHTML = "";
  el("raw-status").innerHTML = pill("running", "amber");
  el("crp-timeline").innerHTML = "";
  el("crp-out").innerHTML = "";
  el("crp-status").innerHTML = pill("running", "amber");
  el("summary").classList.add("hide");

  const d = await apiPost("/api/agent/start", {
    question: el("question").value.trim(),
    real_search: el("real-search").checked,
  });
  runId = d.run_id;
  el("run").disabled = true;
  el("cancel").disabled = false;

  source = new EventSource(`/api/agent/stream?run_id=${encodeURIComponent(runId)}`);
  source.onmessage = (msg) => {
    let evt;
    try { evt = JSON.parse(msg.data); } catch { return; }
    const t = evt.type, data = evt.data || {};
    if (t === "run_started") {
      el("model-tag").textContent = `${data.model} via ${data.runtime} · tools: ${data.tool_set}`;
      el("raw-out").innerHTML = `<p class="muted">raw arm generating…</p>`;
      el("crp-timeline").innerHTML = `<p class="muted">agent working…</p>`;
    } else if (t === "raw_token") {
      if (el("raw-out").querySelector(".muted")) el("raw-out").innerHTML = "";
      rawBuf += data.delta;
      scheduleRawRender();
    } else if (t === "crp_event") {
      const ev = data.event || {};
      if (el("crp-timeline").querySelector(".muted")) el("crp-timeline").innerHTML = "";
      const entry = timelineEntry(ev);
      el("crp-timeline").appendChild(entry);
      entry.scrollIntoView({ block: "nearest" });
    } else if (t === "raw_done") {
      el("raw-status").innerHTML = pill("done · finish " + (data.finish_reason || "stop"), "grey");
      el("raw-final").innerHTML =
        `<h3>Raw arm final output</h3><div class="md fact">${mdToHtml(data.response || "(empty)")}</div>
         <p class="tag">No tool executed. No provenance. No governance.</p>`;
    } else if (t === "crp_done") {
      el("crp-status").innerHTML = pill("done", "green");
      el("crp-out").innerHTML =
        `<h3>Agent answer</h3><div class="md fact">${mdToHtml(data.response || "(empty)")}</div>
         <h3>Governance</h3>${renderGovernance(data.governance)}`;
    } else if (t === "run_done") {
      renderSummary(data.summary || {}, data.elapsed_s || 0);
      closeStream();
    } else if (t === "run_error" || t === "arm_error") {
      el("summary").classList.remove("hide");
      el("summary").innerHTML = `<p class="pill red">${esc(data.error || "run error")}</p>`;
      closeStream();
    }
  };
  source.onerror = () => closeStream();
}

function closeStream() {
  if (source) { source.close(); source = null; }
  el("run").disabled = false;
  el("cancel").disabled = true;
  runId = null;
}

async function cancelRun() {
  if (runId) await apiPost("/api/agent/cancel", { run_id: runId });
  closeStream();
}

el("run").addEventListener("click", runBoth);
el("cancel").addEventListener("click", cancelRun);
loadModelTag();
