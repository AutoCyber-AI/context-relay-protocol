// Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
// Licensed under Elastic License 2.0 — see LICENSE.md for details.
// App 2 — Context Management & Provenance Explorer.

let sessionId = null;
let lastResult = null;

function shortHmac(h) { return h ? h.slice(0, 19) + "…" : "—"; }

function renderPressure(cp, model) {
  if (!cp || !cp.available) {
    el("pressure").innerHTML = model
      ? `Chatting with <strong>${esc(model.id)}</strong>.`
      : "No model loaded — chain, CKF and token signals still work; replies will be empty.";
    return;
  }
  const util = cp.context_utilisation != null ? (cp.context_utilisation * 100).toFixed(1) + "%" : "—";
  el("pressure").innerHTML = `
    <div class="flex" style="gap:1.4rem">
      <div><div class="tag">loaded window</div><b>${cp.loaded_context_length.toLocaleString()}</b> tokens</div>
      <div><div class="tag">model ceiling</div><b>${cp.max_context_length.toLocaleString()}</b> tokens</div>
      <div><div class="tag">utilisation</div><b>${util}</b></div>
      <div><div class="tag">CKF-managed facts</div><b>${cp.ckf_managed_facts}</b></div>
    </div>
    <p style="margin:0.6rem 0 0">${esc(cp.note || "")}</p>`;
}

function renderChain(chain) {
  el("chain-status").innerHTML = ({
    VALID: pill("VALID", "green"),
    BROKEN: pill("BROKEN at window " + chain.broken_at_window, "red"),
    UNVERIFIED: pill("UNVERIFIED (root only)", "grey"),
    PARTIAL: pill("PARTIAL", "amber"),
  })[chain.status] || pill(chain.status, "grey");

  const broken = chain.broken_at_window;
  const nodes = (chain.windows || []).map((w, i) => {
    const isBroken = broken > 0 && w.window_number >= broken;
    const cls = isBroken ? "broken" : "ok";
    const node = `<div class="node ${cls}" title="${esc(w.hmac)}">
      W${w.window_number} · ${esc(shortHmac(w.hmac))}</div>`;
    return i === 0 ? node : `<span class="arrow">→</span>${node}`;
  }).join("");
  el("chain").innerHTML = nodes || `<p class="muted">No windows yet.</p>`;

  el("tamper-row").innerHTML = (chain.windows || []).map(w =>
    `<button class="danger" data-w="${w.window_number}">Tamper window ${w.window_number}</button>`).join("");
  el("tamper-row").querySelectorAll("button").forEach(b =>
    b.addEventListener("click", () => tamper(parseInt(b.dataset.w, 10))));
}

function renderToken(t) {
  el("token").innerHTML = `
    <div class="grid cols-3">
      <div class="kpi"><div class="v">${t.window}</div><div class="k">Window</div></div>
      <div class="kpi"><div class="v">${t.safety_budget}</div><div class="k">Safety budget</div></div>
      <div class="kpi"><div class="v" style="font-size:0.9rem">${esc(t.chain_tip)}</div><div class="k">Chain tip</div></div>
    </div>
    <h3>CRP-Set-Session header</h3>
    <pre class="json">${esc(t.set_session_header)}</pre>`;
}

function pushMsg(role, text, meta) {
  const div = document.createElement("div");
  div.className = "msg " + (role === "user" ? "user" : "bot");
  div.innerHTML = esc(text) + (meta ? `<div class="meta">${esc(meta)}</div>` : "");
  el("chat").appendChild(div);
  el("chat").scrollTop = el("chat").scrollHeight;
}

function applyTurn(r) {
  lastResult = r;
  if (r.turn.reply) pushMsg("bot", r.turn.reply, `window ${r.turn.window_number} · ${r.turn.latency_ms} ms`);
  el("ckf-total").textContent = r.ckf.total_facts;
  el("ckf-window").textContent = r.ckf.facts_this_window;
  el("ckf-retrieved").textContent = r.ckf.retrieved;
  el("recalled").innerHTML = (r.turn.retrieved_facts || []).length
    ? r.turn.retrieved_facts.map(f =>
        `<div class="fact">${esc(f.text)} <span class="cat">score ${f.score}</span></div>`).join("")
    : `<p class="muted">Nothing recalled yet (first turn).</p>`;
  renderChain(r.chain);
  renderToken(r.token);
  renderPressure(r.context_pressure, r.detected_model);
  el("headers").innerHTML = renderHeaders(r.headers);
}

async function sendTurn() {
  const msg = el("message").value.trim();
  if (!msg || !sessionId) return;
  const btn = el("send");
  setBusy(btn, true, "Thinking…");
  pushMsg("user", msg);
  el("message").value = "";
  try {
    const r = await apiPost("/api/context/turn", { session_id: sessionId, message: msg });
    if (r.error) pushMsg("bot", "Error: " + r.error);
    else applyTurn(r);
  } catch (e) { pushMsg("bot", "Request failed: " + e); }
  setBusy(btn, false);
}

async function tamper(windowNumber) {
  const r = await apiPost("/api/context/tamper", { session_id: sessionId, window_number: windowNumber });
  if (r.error) { alert(r.error); return; }
  renderChain(r.chain);
}

async function newSession() {
  el("chat").innerHTML = "";
  el("chain").innerHTML = `<p class="muted">No windows yet.</p>`;
  el("chain-status").innerHTML = "";
  el("tamper-row").innerHTML = "";
  el("pressure").innerHTML = `<span class="spinner"></span> Starting session…`;
  const d = await apiPost("/api/context/new", {});
  sessionId = d.session_id;
  el("model-tag").textContent = d.detected_model ? `${d.detected_model.id} via ${d.detected_model.runtime}` : "no model loaded";
  renderPressure(null, d.detected_model);
  el("pressure").innerHTML = (d.guidance || "").replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
}

el("send").addEventListener("click", sendTurn);
el("reset").addEventListener("click", newSession);
el("message").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) sendTurn();
});

newSession();
