# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Pre-built frontend components for the CRP Agent SDK.

Provides a drop-in HTML chat console with depth selection and a live
AG-UI-compatible event panel.  This lets developers ship a governed agent UI
without building their own streaming components.
"""

from __future__ import annotations

from typing import Any


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
    :root {{ color-scheme: light dark; --accent: #2563eb; --bg: #f8fafc; --panel: #ffffff; --text: #0f172a; }}
    @media (prefers-color-scheme: dark) {{ :root {{ --bg: #0f172a; --panel: #1e293b; --text: #f8fafc; }} }}
    body {{ margin: 0; font-family: ui-sans-serif, system-ui, sans-serif; background: var(--bg); color: var(--text); }}
    header {{ padding: 1rem 1.5rem; border-bottom: 1px solid rgba(128,128,128,0.2); display: flex; align-items: center; gap: 1rem; }}
    h1 {{ margin: 0; font-size: 1.25rem; }}
    main {{ display: grid; grid-template-columns: 1fr 380px; gap: 1rem; padding: 1rem; height: calc(100vh - 70px); box-sizing: border-box; }}
    .panel {{ background: var(--panel); border-radius: 0.75rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); display: flex; flex-direction: column; overflow: hidden; }}
    .chat {{ padding: 1rem; overflow-y: auto; flex: 1; }}
    .message {{ margin: 0.5rem 0; padding: 0.75rem 1rem; border-radius: 0.5rem; max-width: 80%; }}
    .user {{ background: var(--accent); color: white; margin-left: auto; }}
    .agent {{ background: rgba(128,128,128,0.15); }}
    .event-log {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.8rem; padding: 1rem; overflow-y: auto; flex: 1; }}
    .event {{ margin-bottom: 0.5rem; opacity: 0.85; }}
    .event.crp {{ color: #16a34a; }}
    .event.halt {{ color: #dc2626; }}
    .controls {{ padding: 1rem; border-top: 1px solid rgba(128,128,128,0.2); display: flex; gap: 0.5rem; }}
    input[type="text"] {{ flex: 1; padding: 0.6rem 0.8rem; border-radius: 0.5rem; border: 1px solid rgba(128,128,128,0.3); background: transparent; color: inherit; }}
    select, button {{ padding: 0.6rem 0.8rem; border-radius: 0.5rem; border: 1px solid rgba(128,128,128,0.3); background: var(--panel); color: inherit; cursor: pointer; }}
    button.primary {{ background: var(--accent); color: white; border-color: var(--accent); }}
    .depth-badge {{ font-size: 0.75rem; padding: 0.15rem 0.4rem; border-radius: 999px; background: rgba(128,128,128,0.2); }}
    .quality-badge {{ font-size: 0.75rem; padding: 0.15rem 0.4rem; border-radius: 999px; background: #16a34a; color: white; }}
    @media (max-width: 900px) {{ main {{ grid-template-columns: 1fr; height: auto; }} }}
  </style>
</head>
<body>
  <header>
    <h1>{title}</h1>
    <span class="depth-badge" id="depth-badge">standard</span>
    <span class="quality-badge" id="quality-badge" style="display:none">S</span>
  </header>
  <main>
    <section class="panel">
      <div class="chat" id="chat"></div>
      <form class="controls" id="controls">
        <input type="text" id="message" placeholder="Ask the agent…" autocomplete="off" required />
        <select id="depth" title="Reasoning depth">
          <option value="quick">Quick</option>
          <option value="standard" selected>Standard</option>
          <option value="thorough">Thorough</option>
          <option value="exhaustive">Deep Research</option>
        </select>
        <button type="submit" class="primary">Send</button>
      </form>
    </section>
    <section class="panel">
      <div style="padding: 0.75rem 1rem; border-bottom: 1px solid rgba(128,128,128,0.2); font-weight: 600;">Operations & Governance</div>
      <div class="event-log" id="events"></div>
    </section>
  </main>
  <script>
    const chat = document.getElementById('chat');
    const events = document.getElementById('events');
    const form = document.getElementById('controls');
    const input = document.getElementById('message');
    const depthSelect = document.getElementById('depth');
    const depthBadge = document.getElementById('depth-badge');
    const qualityBadge = document.getElementById('quality-badge');
    let sessionId = '{session}' || 'session-' + Math.random().toString(36).slice(2, 10);

    function appendMessage(role, text) {{
      const div = document.createElement('div');
      div.className = 'message ' + role;
      div.textContent = text;
      chat.appendChild(div);
      chat.scrollTop = chat.scrollHeight;
    }}

    function logEvent(text, cls) {{
      const div = document.createElement('div');
      div.className = 'event ' + (cls || '');
      div.textContent = text;
      events.appendChild(div);
      events.scrollTop = events.scrollHeight;
    }}

    depthSelect.addEventListener('change', () => depthBadge.textContent = depthSelect.value);

    form.addEventListener('submit', async (e) => {{
      e.preventDefault();
      const text = input.value.trim();
      if (!text) return;
      appendMessage('user', text);
      input.value = '';
      logEvent('→ intent_classified (' + depthSelect.value + ')');

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
          if (data.type && data.type.startsWith('crp.')) {{
            logEvent('⚡ ' + data.type + ' ' + JSON.stringify(data.payload || data.data), 'crp');
            if (data.type === 'crp.quality' && data.payload && data.payload.tier) {{
              qualityBadge.textContent = data.payload.tier;
              qualityBadge.style.display = 'inline';
            }}
          }} else if (data.type === 'TEXT_MESSAGE_CONTENT') {{
            // streaming token chunk
            let last = chat.querySelector('.agent:last-child');
            if (!last || last.dataset.done) {{
              last = document.createElement('div');
              last.className = 'message agent';
              last.dataset.done = 'false';
              chat.appendChild(last);
            }}
            last.textContent += data.data?.content || '';
            chat.scrollTop = chat.scrollHeight;
          }} else if (data.type === 'RUN_FINISHED' || data.type === 'RUN_ERROR') {{
            const last = chat.querySelector('.agent:last-child');
            if (last) last.dataset.done = 'true';
            source.close();
          }} else {{
            logEvent(data.type);
          }}
        }};
        source.onerror = () => {{
          logEvent('stream error / closed', 'halt');
          source.close();
        }};
      }} catch (err) {{
        logEvent('Error: ' + err.message, 'halt');
      }}
    }});
  </script>
</body>
</html>"""


def mount_fastapi(app: Any, *, path: str = "/crp/console", stream_path: str = "/v1/tel/stream") -> None:
    """Mount the agent console on a FastAPI app at ``path``.

    Also mounts the TEL transparency stream at ``stream_path`` so the
    console's default ``stream_url`` resolves to a live endpoint.
    """
    html = agent_console_html(stream_url=stream_path)

    def _route() -> Any:
        from fastapi.responses import HTMLResponse

        return HTMLResponse(content=html)

    app.get(path)(_route)

    from crp.gateway.tel_stream import mount_fastapi as _mount_stream

    _mount_stream(app, path=stream_path)
