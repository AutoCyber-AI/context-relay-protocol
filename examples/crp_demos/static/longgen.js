// Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
// Licensed under Elastic License 2.0 — see LICENSE.md for details.
// App 4 — Long-Context Document Generation (Demo D).

let runId = null;
let source = null;
let docText = "";
let fullText = "";
let renderTimer = null;
let elapsedTimer = null;
let startedAt = 0;

async function loadModelTag() {
  try {
    const d = await apiGet("/api/detect");
    el("model-tag").textContent = d.primary
      ? `${d.primary.id} via ${d.primary.runtime} · loaded window ` +
        `${(d.primary.loaded_context_length || "?").toLocaleString()} tokens`
      : "no model loaded";
  } catch { el("model-tag").textContent = "detection unavailable"; }
}

function scheduleRender() {
  if (renderTimer) return;
  renderTimer = setTimeout(() => {
    renderTimer = null;
    el("doc").innerHTML = mdToHtml(docText) || `<p class="muted">writing…</p>`;
    const pane = el("doc");
    pane.scrollTop = pane.scrollHeight;
  }, 250);
}

function startElapsed() {
  startedAt = Date.now();
  elapsedTimer = setInterval(() => {
    el("pg-elapsed").textContent = `${Math.round((Date.now() - startedAt) / 1000)}s`;
  }, 1000);
}

function stopElapsed() {
  if (elapsedTimer) { clearInterval(elapsedTimer); elapsedTimer = null; }
}

function setRunning(running) {
  el("start").disabled = running;
  el("cancel").disabled = !running;
  el("sections").disabled = running;
  el("words").disabled = running;
  el("tpw").disabled = running;
  el("section-titles").disabled = running;
}

function windowCard(w) {
  const m = w.metrics || {};
  // Window 1 has no predecessor — coherence with the previous window is
  // undefined, not zero.
  const coherence = w.window > 1 && m.coherence_with_prev != null
    ? (m.coherence_with_prev * 100).toFixed(1) + "%" : " - ";
  const div = document.createElement("div");
  div.className = "fact";
  div.innerHTML = `${pill("window " + w.window, "blue")}
    <span class="cat">${w.words_in_window.toLocaleString()} words ·
    ${(m.latency_s || 0).toFixed(1)}s · rep ${((m.repetition_6gram || 0) * 100).toFixed(2)}% ·
    coherence ${coherence}</span>
    ${m.section_title ? `<div class="cat">section: ${esc(m.section_title)}</div>` : ""}`;
  return div;
}

function renderGate(acceptance) {
  el("gate-card").classList.remove("hide");
  el("gate-verdict").innerHTML = acceptance.pass
    ? pill("PASS - real long-form document", "green")
    : pill("FAIL - gate not met", "red");
  const rows = (acceptance.checks || []).map(c =>
    `<tr><td>${esc(c.check)}</td><td>${esc(String(c.value))}</td>
     <td>${esc(c.threshold)}</td>
     <td>${c.pass ? pill("pass", "green") : pill("fail", "red")}</td></tr>`).join("");
  el("gate").innerHTML =
    `<table class="hdr-table"><tr><td>check</td><td>measured</td><td>threshold</td><td></td></tr>${rows}</table>`;
}

async function startRun() {
  if (source) return;
  docText = ""; fullText = "";
  el("doc").innerHTML = `<p class="muted">connecting…</p>`;
  el("windows").innerHTML = "";
  el("gate-card").classList.add("hide");
  el("progress").classList.remove("hide");
  el("pg-words").textContent = "0";
  el("pg-windows").textContent = "0";
  el("pg-rep").textContent = "0%";
  el("pg-elapsed").textContent = "0s";
  el("download").disabled = true;

  const customTitles = el("section-titles").value
    .split("\n").map(s => s.trim()).filter(Boolean);
  const payload = {
    sections: parseInt(el("sections").value, 10) || 3,
    words: parseInt(el("words").value, 10) || 1500,
    tokens_per_window: parseInt(el("tpw").value, 10) || 700,
  };
  if (customTitles.length) payload.section_titles = customTitles;
  const d = await apiPost("/api/longgen/start", payload);
  runId = d.run_id;
  setRunning(true);
  startElapsed();

  source = new EventSource(`/api/longgen/stream?run_id=${encodeURIComponent(runId)}`);
  source.onmessage = (msg) => {
    let evt;
    try { evt = JSON.parse(msg.data); } catch { return; }
    if (evt.type === "run_started") {
      el("doc").innerHTML = `<p class="muted">run started - ${esc(evt.data.model)}, ` +
        `${evt.data.section_titles.length} sections, target ${evt.data.target_words.toLocaleString()} words</p>`;
    } else if (evt.type === "chunk") {
      docText += evt.data.text;
      scheduleRender();
    } else if (evt.type === "window_metrics") {
      const m = evt.data.metrics || {};
      el("pg-words").textContent = (m.running_words || 0).toLocaleString();
      el("pg-rep").textContent = `${((m.repetition_6gram || 0) * 100).toFixed(2)}%`;
    } else if (evt.type === "window_done") {
      el("pg-windows").textContent = String(evt.data.window);
      if (el("windows").querySelector(".muted")) el("windows").innerHTML = "";
      el("windows").appendChild(windowCard(evt.data));
    } else if (evt.type === "run_done") {
      stopElapsed();
      el("doc").innerHTML = mdToHtml(docText);
      el("pg-words").textContent = (evt.data.result.total_words || 0).toLocaleString();
      el("pg-windows").textContent = String(evt.data.result.windows || 0);
      renderGate(evt.data.acceptance || { pass: false, checks: [] });
      enableDownload();
      closeStream();
    } else if (evt.type === "run_error") {
      stopElapsed();
      el("doc").innerHTML = `<p class="pill red">run failed: ${esc(evt.data.error)}</p>`;
      closeStream();
    }
  };
  source.onerror = () => closeStream();
}

function closeStream() {
  if (source) { source.close(); source = null; }
  setRunning(false);
  runId = null;
}

async function cancelRun() {
  if (!runId) return;
  await apiPost("/api/longgen/cancel", { run_id: runId });
  stopElapsed();
  closeStream();
}

function enableDownload() {
  const btn = el("download");
  btn.disabled = !docText;
  btn.onclick = () => {
    const blob = new Blob([docText], { type: "text/markdown" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "crp-document.md";
    a.click();
    URL.revokeObjectURL(a.href);
  };
}

el("start").addEventListener("click", startRun);
el("cancel").addEventListener("click", cancelRun);
loadModelTag();
