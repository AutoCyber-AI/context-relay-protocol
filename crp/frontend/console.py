# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Pre-built frontend components for the CRP Agent SDK.

Provides a drop-in HTML chat console with depth selection, a live
AG-UI-compatible event panel, a readable chain-of-thought narrative, governance
cards, and a visual provenance chain.  This lets developers ship a governed
agent UI without building their own streaming components.
"""

from __future__ import annotations

from typing import Any

# NOTE: This is a self-contained embedded console.  A CDN-ready build lives in
# frontend/agent-console/ and is served by `crp/frontend/bundle.py` when built.
# The inline HTML below is kept as an air-gapped fallback.


def agent_console_html(
    *,
    title: str = "CRP Agent Console",
    stream_url: str = "/v1/tel/stream",
    chat_url: str = "/v1/chat/completions",
    session_id: str | None = None,
) -> str:
    """Return a self-contained HTML/JS agent console.

    Args:
        title: Page title.
        stream_url: SSE endpoint for the transparency stream.
        chat_url: HTTP endpoint to POST chat requests.
        session_id: Optional fixed session id.

    Returns:
        A complete HTML document as a string.
    """
    session = session_id or ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    :root {{
      color-scheme: light dark;
      --accent: #2563eb;
      --accent-soft: rgba(37, 99, 235, 0.12);
      --success: #16a34a;
      --warning: #f59e0b;
      --danger: #dc2626;
      --info: #06b6d4;
      --bg: #f8fafc;
      --panel: #ffffff;
      --text: #0f172a;
      --muted: #64748b;
      --border: rgba(148, 163, 184, 0.25);
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg: #0f172a;
        --panel: #1e293b;
        --text: #f8fafc;
        --muted: #94a3b8;
        --border: rgba(148, 163, 184, 0.15);
      }}
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.45;
    }}
    header {{
      padding: 0.75rem 1rem;
      border-bottom: 1px solid var(--border);
      display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap;
    }}
    h1 {{ margin: 0; font-size: 1.1rem; font-weight: 600; }}
    .spacer {{ flex: 1; }}
    .badge {{
      font-size: 0.7rem; padding: 0.2rem 0.5rem; border-radius: 999px;
      background: var(--accent-soft); color: var(--accent); font-weight: 600; text-transform: uppercase; letter-spacing: 0.02em;
    }}
    .badge.risk-low {{ background: rgba(22, 163, 74, 0.12); color: var(--success); }}
    .badge.risk-medium {{ background: rgba(245, 158, 11, 0.12); color: var(--warning); }}
    .badge.risk-high {{ background: rgba(220, 38, 38, 0.12); color: var(--danger); }}
    .badge.risk-critical {{ background: rgba(220, 38, 38, 0.18); color: var(--danger); }}
    .badge.chain-broken {{ background: rgba(220, 38, 38, 0.18); color: var(--danger); }}
    button.icon {{
      background: transparent; border: 1px solid var(--border); color: var(--muted);
      cursor: pointer; padding: 0.35rem 0.6rem; border-radius: 0.5rem; font-size: 0.8rem;
    }}
    button.icon:hover {{ color: var(--text); border-color: var(--muted); }}
    main {{
      display: grid;
      grid-template-columns: minmax(320px, 1fr) minmax(300px, 420px);
      gap: 0.75rem;
      padding: 0.75rem;
      height: calc(100vh - 58px);
    }}
    @media (max-width: 960px) {{
      main {{ grid-template-columns: 1fr; height: auto; }}
    }}
    .panel {{
      background: var(--panel);
      border-radius: 0.75rem;
      box-shadow: 0 1px 2px rgba(0,0,0,0.05);
      border: 1px solid var(--border);
      display: flex; flex-direction: column; overflow: hidden;
    }}
    .panel-header {{
      padding: 0.6rem 0.8rem;
      border-bottom: 1px solid var(--border);
      font-weight: 600; font-size: 0.85rem;
      display: flex; align-items: center; justify-content: space-between;
    }}
    .panel-body {{ flex: 1; overflow-y: auto; padding: 0.75rem; }}
    .chat {{ display: flex; flex-direction: column; gap: 0.5rem; }}
    .message {{
      padding: 0.65rem 0.9rem; border-radius: 0.65rem; max-width: 88%;
      font-size: 0.92rem; white-space: pre-wrap; word-break: break-word;
    }}
    .message.user {{ background: var(--accent); color: white; margin-left: auto; border-bottom-right-radius: 0.2rem; }}
    .message.agent {{ background: var(--bg); color: var(--text); border: 1px solid var(--border); border-bottom-left-radius: 0.2rem; }}
    .controls {{
      padding: 0.65rem 0.8rem; border-top: 1px solid var(--border);
      display: flex; gap: 0.5rem; align-items: center;
    }}
    input[type="text"], select {{
      padding: 0.55rem 0.75rem; border-radius: 0.5rem;
      border: 1px solid var(--border); background: var(--panel); color: var(--text); font-size: 0.9rem;
    }}
    input[type="text"] {{ flex: 1; }}
    select {{ min-width: 110px; }}
    button.primary {{
      background: var(--accent); color: white; border-color: var(--accent);
      padding: 0.55rem 1rem; border-radius: 0.5rem; border: 1px solid transparent;
      font-weight: 500; cursor: pointer;
    }}
    button.primary:disabled {{ opacity: 0.5; cursor: not-allowed; }}
    .governance-grid {{
      display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 0.5rem; margin-bottom: 0.75rem;
    }}
    .gov-card {{
      background: var(--bg); border: 1px solid var(--border); border-radius: 0.5rem;
      padding: 0.5rem; text-align: center;
    }}
    .gov-card .label {{ font-size: 0.65rem; text-transform: uppercase; color: var(--muted); letter-spacing: 0.04em; }}
    .gov-card .value {{ font-size: 1rem; font-weight: 700; margin-top: 0.15rem; }}
    .gov-card .value.ok {{ color: var(--success); }}
    .gov-card .value.warn {{ color: var(--warning); }}
    .gov-card .value.bad {{ color: var(--danger); }}
    .narrative {{
      display: flex; flex-direction: column; gap: 0.4rem;
    }}
    .narrative-step {{
      border-left: 3px solid var(--border); padding-left: 0.65rem;
      font-size: 0.84rem;
    }}
    .narrative-step.run {{ border-color: var(--accent); }}
    .narrative-step.intent {{ border-color: var(--info); }}
    .narrative-step.operation {{ border-color: var(--accent); }}
    .narrative-step.tool-select {{ border-color: var(--warning); }}
    .narrative-step.tool-call {{ border-color: var(--warning); }}
    .narrative-step.tool-result {{ border-color: var(--success); }}
    .narrative-step.safety {{ border-color: var(--danger); }}
    .narrative-step.quality {{ border-color: var(--success); }}
    .narrative-step.provenance {{ border-color: #8b5cf6; }}
    .narrative-step.verification {{ border-color: #ec4899; }}
    .narrative-step.interrupt {{ border-color: var(--danger); background: rgba(220,38,38,0.06); padding: 0.35rem 0.65rem; border-radius: 0.35rem; }}
    .narrative-title {{ font-weight: 600; color: var(--text); }}
    .narrative-detail {{ color: var(--muted); margin-top: 0.15rem; white-space: pre-wrap; }}
    .provenance {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 0.75rem;
      background: var(--bg); border: 1px solid var(--border); border-radius: 0.5rem; padding: 0.5rem;
      overflow-x: auto;
    }}
    .provenance .link {{
      display: flex; align-items: center; gap: 0.35rem; margin-bottom: 0.25rem; color: var(--muted);
    }}
    .provenance .hash {{ font-weight: 600; color: var(--text); }}
    .event-log {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 0.72rem;
      display: flex; flex-direction: column; gap: 0.25rem;
    }}
    .event {{
      padding: 0.25rem 0.4rem; border-radius: 0.3rem; background: var(--bg); color: var(--muted);
      border-left: 2px solid var(--border);
    }}
    .event.crp {{ border-color: var(--success); color: var(--text); }}
    .event.halt {{ border-color: var(--danger); color: var(--danger); }}
    .event code {{ font-size: 0.7rem; }}
    .empty-state {{
      color: var(--muted); font-size: 0.85rem; text-align: center; margin-top: 2rem;
    }}
    .hidden {{ display: none !important; }}
    .tabs {{ display: flex; gap: 0.25rem; }}
    .tab {{
      background: transparent; border: 1px solid transparent; color: var(--muted);
      padding: 0.25rem 0.5rem; border-radius: 0.35rem; cursor: pointer; font-size: 0.75rem;
    }}
    .tab.active {{ background: var(--bg); color: var(--text); border-color: var(--border); font-weight: 600; }}
  </style>
</head>
<body>
  <header>
    <h1>{title}</h1>
    <span class="badge" id="depth-badge">standard</span>
    <span class="badge" id="risk-badge" style="display:none">RISK</span>
    <span class="badge" id="quality-badge" style="display:none">S</span>
    <span class="badge chain-broken hidden" id="chain-badge">CHAIN BROKEN</span>
    <span class="spacer"></span>
    <button class="icon" id="theme-toggle" title="Toggle light/dark">🌓</button>
  </header>
  <main>
    <section class="panel">
      <div class="panel-header">Chat</div>
      <div class="panel-body chat" id="chat">
        <div class="empty-state">Send a message to start a governed agent run.</div>
      </div>
      <form class="controls" id="controls">
        <input type="text" id="message" placeholder="Ask the agent…" autocomplete="off" required />
        <select id="depth" title="Reasoning depth">
          <option value="quick">Quick</option>
          <option value="standard" selected>Standard</option>
          <option value="thorough">Thorough</option>
          <option value="exhaustive">Deep Research</option>
        </select>
        <button type="submit" class="primary" id="send-btn">Send</button>
      </form>
    </section>
    <section class="panel">
      <div class="panel-header">
        <span>What CRP is doing</span>
        <div class="tabs">
          <button class="tab active" data-tab="narrative">Narrative</button>
          <button class="tab" data-tab="governance">Governance</button>
          <button class="tab" data-tab="provenance">Provenance</button>
          <button class="tab" data-tab="events">Events</button>
        </div>
      </div>
      <div class="panel-body" id="right-body">
        <div class="governance-grid" id="governance-cards">
          <div class="gov-card"><div class="label">Risk</div><div class="value" id="g-risk">—</div></div>
          <div class="gov-card"><div class="label">Grounded</div><div class="value" id="g-grounded">—</div></div>
          <div class="gov-card"><div class="label">Chain</div><div class="value ok" id="g-chain">—</div></div>
          <div class="gov-card"><div class="label">Quality</div><div class="value" id="g-quality">—</div></div>
          <div class="gov-card"><div class="label">Confidence</div><div class="value" id="g-confidence">—</div></div>
          <div class="gov-card"><div class="label">Sources</div><div class="value" id="g-sources">—</div></div>
        </div>
        <div class="tab-panel" id="tab-narrative">
          <div class="narrative" id="narrative"><div class="empty-state">The reasoning chain will appear here as events stream in.</div></div>
        </div>
        <div class="tab-panel hidden" id="tab-governance">
          <div class="narrative" id="governance-log"><div class="empty-state">Governance events will appear here.</div></div>
        </div>
        <div class="tab-panel hidden" id="tab-provenance">
          <div class="provenance" id="provenance"><div class="empty-state">HMAC chain links will appear here.</div></div>
        </div>
        <div class="tab-panel hidden" id="tab-events">
          <div class="event-log" id="events"><div class="empty-state">Raw AG-UI + CRP events will appear here.</div></div>
        </div>
      </div>
    </section>
  </main>
  <script>
    const chat = document.getElementById('chat');
    const narrative = document.getElementById('narrative');
    const governanceLog = document.getElementById('governance-log');
    const provenancePanel = document.getElementById('provenance');
    const eventsPanel = document.getElementById('events');
    const form = document.getElementById('controls');
    const input = document.getElementById('message');
    const depthSelect = document.getElementById('depth');
    const depthBadge = document.getElementById('depth-badge');
    const riskBadge = document.getElementById('risk-badge');
    const qualityBadge = document.getElementById('quality-badge');
    const chainBadge = document.getElementById('chain-badge');
    const sendBtn = document.getElementById('send-btn');
    const themeToggle = document.getElementById('theme-toggle');
    let sessionId = '{session}' || 'session-' + Math.random().toString(36).slice(2, 10);

    const governance = {{
      risk: '', grounded: false, chain_valid: false, tier: '', confidence: 0, sources: 0
    }};
    let currentAgentMessage = null;

    function emptyIfNeeded(el) {{
      if (el.querySelector('.empty-state')) el.innerHTML = '';
    }}

    function appendMessage(role, text) {{
      emptyIfNeeded(chat);
      const div = document.createElement('div');
      div.className = 'message ' + role;
      div.textContent = text;
      chat.appendChild(div);
      chat.scrollTop = chat.scrollHeight;
      return div;
    }}

    function appendAgentToken(text) {{
      if (!currentAgentMessage || currentAgentMessage.dataset.done === 'true') {{
        emptyIfNeeded(chat);
        currentAgentMessage = document.createElement('div');
        currentAgentMessage.className = 'message agent';
        currentAgentMessage.dataset.done = 'false';
        chat.appendChild(currentAgentMessage);
      }}
      currentAgentMessage.textContent += text;
      chat.scrollTop = chat.scrollHeight;
    }}

    function finalizeAgentMessage() {{
      if (currentAgentMessage) currentAgentMessage.dataset.done = 'true';
      currentAgentMessage = null;
    }}

    function addNarrative(kind, title, detail, meta) {{
      emptyIfNeeded(narrative);
      const step = document.createElement('div');
      step.className = 'narrative-step ' + kind;
      const titleEl = document.createElement('div');
      titleEl.className = 'narrative-title';
      titleEl.textContent = title;
      step.appendChild(titleEl);
      if (detail) {{
        const detailEl = document.createElement('div');
        detailEl.className = 'narrative-detail';
        detailEl.textContent = detail;
        step.appendChild(detailEl);
      }}
      narrative.appendChild(step);
      narrative.scrollTop = narrative.scrollHeight;
    }}

    function addGovernanceEvent(title, detail) {{
      emptyIfNeeded(governanceLog);
      const step = document.createElement('div');
      step.className = 'narrative-step safety';
      const t = document.createElement('div');
      t.className = 'narrative-title';
      t.textContent = title;
      step.appendChild(t);
      if (detail) {{
        const d = document.createElement('div');
        d.className = 'narrative-detail';
        d.textContent = detail;
        step.appendChild(d);
      }}
      governanceLog.appendChild(step);
      governanceLog.scrollTop = governanceLog.scrollHeight;
    }}

    function addProvenanceLink(prev, cur, op) {{
      emptyIfNeeded(provenancePanel);
      const row = document.createElement('div');
      row.className = 'link';
      row.innerHTML = '<span class="hash">' + (prev || 'genesis').slice(0, 16) + '</span> → <span class="hash">' + cur.slice(0, 16) + '</span> <span style="margin-left:auto;color:var(--muted)">' + op + '</span>';
      provenancePanel.appendChild(row);
      provenancePanel.scrollTop = provenancePanel.scrollHeight;
    }}

    function logEvent(text, cls) {{
      emptyIfNeeded(eventsPanel);
      const div = document.createElement('div');
      div.className = 'event ' + (cls || '');
      const code = document.createElement('code');
      code.textContent = text;
      div.appendChild(code);
      eventsPanel.appendChild(div);
      eventsPanel.scrollTop = eventsPanel.scrollHeight;
    }}

    function updateGovernanceCards() {{
      const riskEl = document.getElementById('g-risk');
      riskEl.textContent = governance.risk || '—';
      riskEl.className = 'value' + (governance.risk ? ' ' + riskClass(governance.risk) : '');
      document.getElementById('g-grounded').textContent = governance.grounded ? 'YES' : 'NO';
      document.getElementById('g-grounded').className = 'value ' + (governance.grounded ? 'ok' : 'warn');
      document.getElementById('g-chain').textContent = governance.chain_valid ? 'VALID' : '—';
      document.getElementById('g-chain').className = 'value ' + (governance.chain_valid ? 'ok' : 'warn');
      document.getElementById('g-quality').textContent = governance.tier || '—';
      document.getElementById('g-confidence').textContent = governance.confidence ? governance.confidence.toFixed(2) : '—';
      document.getElementById('g-sources').textContent = governance.sources || '—';
      updateBadges();
    }}

    function riskClass(risk) {{
      const r = (risk || '').toLowerCase();
      if (r.includes('critical')) return 'bad';
      if (r.includes('high')) return 'warn';
      if (r.includes('medium')) return 'warn';
      return 'ok';
    }}

    function updateBadges() {{
      if (governance.risk) {{
        riskBadge.textContent = governance.risk;
        riskBadge.className = 'badge risk-' + governance.risk.toLowerCase();
        riskBadge.style.display = 'inline';
      }}
      if (governance.tier) {{
        qualityBadge.textContent = governance.tier;
        qualityBadge.style.display = 'inline';
      }}
      if (!governance.chain_valid && governance.chainChecked) {{
        chainBadge.classList.remove('hidden');
      }} else {{
        chainBadge.classList.add('hidden');
      }}
    }}

    // Tab switching
    document.querySelectorAll('.tab').forEach(btn => {{
      btn.addEventListener('click', () => {{
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        btn.classList.add('active');
        document.querySelectorAll('.tab-panel').forEach(p => p.classList.add('hidden'));
        document.getElementById('tab-' + btn.dataset.tab).classList.remove('hidden');
      }});
    }});

    // Theme toggle (manual override)
    themeToggle.addEventListener('click', () => {{
      const html = document.documentElement;
      const current = html.style.colorScheme;
      html.style.colorScheme = current === 'dark' ? 'light' : 'dark';
    }});

    depthSelect.addEventListener('change', () => depthBadge.textContent = depthSelect.value);

    form.addEventListener('submit', async (e) => {{
      e.preventDefault();
      const text = input.value.trim();
      if (!text) return;
      appendMessage('user', text);
      input.value = '';
      sendBtn.disabled = true;
      finalizeAgentMessage();

      addNarrative('run', 'Run started', 'Goal: ' + text);

      const body = JSON.stringify({{
        model: 'crp-learned',
        messages: [{{role: 'user', content: text}}],
        stream: true,
        session_id: sessionId,
        depth: depthSelect.value
      }});

      try {{
        const source = new EventSource('{stream_url}?session_id=' + encodeURIComponent(sessionId) + '&body=' + encodeURIComponent(body));
        source.onmessage = (ev) => {{
          let data;
          try {{ data = JSON.parse(ev.data); }} catch {{ data = {{type: ev.data}}; }}
          let type = (data.type || data.event || '').toString();
          let payload = data.payload || data.value || data.data || {{}};
          // CRP custom events are sent as type=CUSTOM with name/value payload; unwrap them.
          if (type === 'CUSTOM' && data.name) {{
            type = data.name;
            payload = data.value || {{}};
          }}

          if (type.startsWith('crp.')) {{
            const name = type.slice(4);
            logEvent('⚡ ' + type + ' ' + JSON.stringify(payload), 'crp');
            if (type === 'crp.intent') {{
              const ops = (payload.plan || []).join(', ');
              addNarrative('intent', 'Intent classified', (payload.detail || '') + (ops ? ' → operations: ' + ops : ''), payload);
            }} else if (type === 'crp.safety_scan') {{
              addGovernanceEvent('Safety scan — ' + (payload.risk || ''), 'Stage: ' + (payload.stage || '') + '; verdict: ' + (payload.verdict || ''));
            }} else if (type === 'crp.quality') {{
              governance.risk = payload.risk || governance.risk;
              governance.tier = payload.tier || governance.tier;
              governance.confidence = payload.confidence || 0;
              updateGovernanceCards();
              addGovernanceEvent('Quality tier: ' + (payload.tier || ''), 'Confidence: ' + (payload.confidence || 0).toFixed(2));
            }} else if (type === 'crp.verification') {{
              addNarrative('verification', 'Verification relay', 'Invalid steps: ' + (payload.invalid || 0) + '; repairs: ' + (payload.repairs || 0), payload);
            }} else if (type === 'crp.retrieval') {{
              governance.sources = (payload.sources || []).length;
              updateGovernanceCards();
              addNarrative('retrieval', 'Retrieval', governance.sources + ' source(s) identified', payload);
            }} else if (type === 'crp.provenance') {{
              governance.chain_valid = true;
              governance.chainChecked = true;
              updateGovernanceCards();
              addProvenanceLink(payload.prev, payload.hash, payload.op || 'agent_run');
            }} else if (type === 'crp.policy') {{
              addNarrative('policy', 'Policy envelope checked', 'Verdict: ' + (payload.verdict || 'allow'), payload);
            }} else if (type === 'crp.run_complete') {{
              addNarrative('run', 'Positioned loop complete', payload.detail || '', payload);
            }} else if (type === 'crp.progress') {{
              addNarrative('progress', 'Progress: ' + (payload.percent || 0) + '%', payload.current || '', payload);
            }} else if (type === 'crp.trust') {{
              const ts = payload.score !== undefined ? Number(payload.score).toFixed(2) : '—';
              addNarrative('safety', 'Trust decision — ' + (payload.action || ''), 'Score: ' + ts + (payload.reason ? '; ' + payload.reason : ''), payload);
            }} else if (type === 'crp.kill_switch') {{
              governance.risk = 'CRITICAL';
              updateGovernanceCards();
              addNarrative('interrupt', 'Kill switch fired', (payload.reason || 'trust collapsed') + ' (score ' + Number(payload.trust_score || 0).toFixed(2) + ')', payload);
            }} else if (type === 'crp.checkpoint') {{
              if (payload.action === 'requested') {{
                addNarrative('interrupt', 'Checkpoint requested', payload.request_id || 'human oversight required', payload);
              }} else {{
                addNarrative('safety', 'Checkpoint resolved', (payload.resolution || '') + (payload.reviewer ? ' by ' + payload.reviewer : ''), payload);
              }}
            }} else if (type === 'crp.governance') {{
              if (payload.risk !== undefined) governance.risk = payload.risk;
              if (payload.grounded !== undefined) governance.grounded = payload.grounded;
              if (payload.chain_valid !== undefined) {{ governance.chain_valid = payload.chain_valid; governance.chainChecked = true; }}
              if (payload.tier !== undefined) governance.tier = payload.tier;
              if (payload.confidence !== undefined) governance.confidence = payload.confidence;
              if (payload.sources !== undefined) governance.sources = payload.sources;
              updateGovernanceCards();
              addGovernanceEvent('Governance summary', 'Risk: ' + (payload.risk || '—') + ' | grounded: ' + (payload.grounded ? 'yes' : 'no') + ' | sources: ' + (payload.sources ?? '—'));
            }}
          }} else if (type === 'TEXT_MESSAGE_CONTENT') {{
            appendAgentToken(payload.content || '');
          }} else if (type === 'REASONING_CONTENT') {{
            // Surface reasoning tokens as narrative detail when available
            const delta = payload.delta || payload.content || '';
            if (delta) {{
              // We accumulate reasoning in a lightweight way: only create a step once
              let last = narrative.querySelector('.narrative-step.reasoning:last-child');
              if (!last) {{
                addNarrative('reasoning', 'Model reasoning', delta);
              }} else {{
                const d = last.querySelector('.narrative-detail');
                if (d) d.textContent += delta;
                narrative.scrollTop = narrative.scrollHeight;
              }}
            }}
          }} else if (type === 'TOOL_CALL_START') {{
            addNarrative('tool-select', 'Tool selected — ' + (payload.toolCallName || ''), payload.reason || '', payload);
          }} else if (type === 'TOOL_CALL_ARGS') {{
            // Args usually arrive as JSON delta; summarise lightly
            const delta = payload.delta || '';
            if (delta) {{
              let last = narrative.querySelector('.narrative-step.tool-call:last-child');
              if (!last) {{
                addNarrative('tool-call', 'Calling tool', delta);
              }} else {{
                const d = last.querySelector('.narrative-detail');
                if (d) d.textContent += delta;
                narrative.scrollTop = narrative.scrollHeight;
              }}
            }}
          }} else if (type === 'TOOL_CALL_RESULT') {{
            const content = payload.content;
            let summary = '';
            if (typeof content === 'string') summary = content.slice(0, 200) + (content.length > 200 ? '…' : '');
            else summary = JSON.stringify(content).slice(0, 200) + '…';
            addNarrative('tool-result', 'Tool result received', summary, payload);
          }} else if (type === 'RUN_FINISHED') {{
            finalizeAgentMessage();
            addNarrative('run', 'Run finished', 'Governance summary available.');
            sendBtn.disabled = false;
            source.close();
          }} else if (type === 'RUN_ERROR') {{
            finalizeAgentMessage();
            governance.risk = 'CRITICAL';
            governance.chainChecked = true;
            updateGovernanceCards();
            addNarrative('interrupt', 'Run halted', payload.error || 'Unknown error', payload);
            logEvent('Run error: ' + (payload.error || type), 'halt');
            sendBtn.disabled = false;
            source.close();
          }} else if (type === 'INTERRUPT') {{
            addNarrative('interrupt', 'Human oversight required', payload.reason || '', payload);
            logEvent('Interrupt: ' + (payload.reason || type), 'halt');
          }} else {{
            logEvent(type);
          }}
        }};
        source.onerror = () => {{
          logEvent('stream error / closed', 'halt');
          sendBtn.disabled = false;
          source.close();
        }};
      }} catch (err) {{
        logEvent('Error: ' + err.message, 'halt');
        sendBtn.disabled = false;
      }}
    }});
  </script>
</body>
</html>"""


def _built_static_dir() -> Any:
    """Return the Path to the built static bundle, or None if not built.

    Checks the development copy under ``crp/frontend/static`` first, then the
    canonical Vite output at ``frontend/agent-console/dist``.
    """
    try:
        from pathlib import Path

        here = Path(__file__).parent
        candidates = [
            here / "static",
            here.parent.parent / "frontend" / "agent-console" / "dist",
        ]
        for static_dir in candidates:
            if (static_dir / "index.html").exists():
                return static_dir
    except Exception:  # pragma: no cover - defensive
        pass
    return None


def mount_fastapi(
    app: Any,
    *,
    path: str = "/crp/console",
    stream_path: str = "/v1/tel/stream",
    cors_origins: list[str] | None = None,
) -> None:
    """Mount the agent console on a FastAPI app at ``path``.

    If ``crp/frontend/static/index.html`` exists (the built Vite bundle), it is
    served as the console and the ``static/assets`` directory is mounted under
    ``path`` so relative asset links resolve.  Otherwise the self-contained
    inline HTML console is served as a fallback.

    Also mounts the TEL transparency stream at ``stream_path`` so the
    console's default ``stream_url`` resolves to a live endpoint.

    CORS: browsers refuse cross-origin reads (including SSE) unless the
    backend allows the console's origin. The CDN-hosted console at
    ``https://console.crprotocol.io`` talks directly to a user's local backend,
    so that origin is allowed by default; pass ``cors_origins`` to override
    or extend (e.g. for a white-label domain).
    """
    from fastapi.middleware.cors import CORSMiddleware

    allowed = cors_origins or [
        "https://console.crprotocol.io",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    static_dir = _built_static_dir()

    if static_dir is not None:
        from fastapi.staticfiles import StaticFiles

        # Serve the built index.html at the console path; assets at path/assets/.
        app.mount(f"{path}/assets", StaticFiles(directory=static_dir / "assets"), name="crp_console_assets")

        def _route() -> Any:
            from fastapi.responses import FileResponse

            return FileResponse(static_dir / "index.html")

        app.get(path)(_route)
    else:
        html = agent_console_html(stream_url=stream_path)

        def _route() -> Any:
            from fastapi.responses import HTMLResponse

            return HTMLResponse(content=html)

        app.get(path)(_route)

    from crp.gateway.tel_stream import mount_fastapi as _mount_stream

    _mount_stream(app, path=stream_path)
