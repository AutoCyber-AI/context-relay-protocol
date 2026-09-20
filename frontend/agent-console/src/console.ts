import type { AGUIEvent, GovernanceSummary, NarrativeStep, ProvenanceLink } from './events.js';
import { NarrativeBuilder } from './narrative.js';

export interface ConsoleConfig {
  title?: string;
  streamUrl?: string;
  chatUrl?: string;
  sessionId?: string;
  /** Base URL the user pointed the console at (e.g. http://127.0.0.1:8000), if any. */
  endpoint?: string;
}

export class AgentConsole {
  private container: HTMLElement;
  private config: ConsoleConfig;
  private builder = new NarrativeBuilder();
  private currentAgentMessage: HTMLElement | null = null;
  private governance: GovernanceSummary = {
    risk: '', grounded: false, chain_valid: false, tier: '', confidence: 0, sources: 0,
  };

  private chatEl!: HTMLElement;
  private narrativeEl!: HTMLElement;
  private governanceLogEl!: HTMLElement;
  private provenanceEl!: HTMLElement;
  private eventsEl!: HTMLElement;

  constructor(container: HTMLElement, config: ConsoleConfig = {}) {
    this.container = container;
    this.config = {
      title: 'CRP Agent Console',
      streamUrl: '/v1/tel/stream',
      chatUrl: '/v1/chat/completions',
      sessionId: '',
      ...config,
    };
    this.render();
    this.bindTabs();
  }

  private render(): void {
    this.container.innerHTML = `
      <header class="global">
        <h1>${this.escape(this.config.title || '')}</h1>
        <form class="conn" id="conn-form" title="Point this console at your CRP backend, then press Enter">
          <span class="conn-dot" id="conn-dot"></span>
          <input type="text" id="conn-input" placeholder="Backend URL — e.g. http://127.0.0.1:8000" autocomplete="off" spellcheck="false" />
          <button type="submit" class="icon" id="conn-btn">Connect</button>
        </form>
        <span class="badge" id="depth-badge">standard</span>
        <span class="badge" id="risk-badge" style="display:none">RISK</span>
        <span class="badge" id="quality-badge" style="display:none">S</span>
        <span class="spacer"></span>
        <button class="icon" id="theme-toggle" title="Toggle light/dark">🌓</button>
      </header>
      <main class="app">
        <section class="panel">
          <div class="panel-header">Chat</div>
          <div class="panel-body chat" id="chat"><div class="empty-state">Send a message to start a governed agent run.</div></div>
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
              <div class="gov-card"><div class="label">Chain</div><div class="value" id="g-chain">—</div></div>
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
    `;

    this.chatEl = this.container.querySelector('#chat') as HTMLElement;
    this.narrativeEl = this.container.querySelector('#narrative') as HTMLElement;
    this.governanceLogEl = this.container.querySelector('#governance-log') as HTMLElement;
    this.provenanceEl = this.container.querySelector('#provenance') as HTMLElement;
    this.eventsEl = this.container.querySelector('#events') as HTMLElement;

    this.bindForm();
    this.bindTheme();
    this.bindConnection();
  }

  /** Backend endpoint picker: saves the base URL in localStorage and reloads so the
   *  stream/chat URLs are rebuilt against it. Clearing the field reverts to the
   *  defaults baked into the page (same-origin or window.CRP_* overrides). */
  private bindConnection(): void {
    const form = this.container.querySelector('#conn-form') as HTMLFormElement;
    const input = this.container.querySelector('#conn-input') as HTMLInputElement;
    const dot = this.container.querySelector('#conn-dot') as HTMLElement;
    if (this.config.endpoint) {
      input.value = this.config.endpoint;
      dot.classList.add('on');
      input.title = 'Connected backend (remembered by this browser only)';
    }
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      const value = input.value.trim().replace(/\/+$/, '');
      if (value) {
        try {
          new URL(value);
        } catch {
          dot.classList.add('err');
          input.title = 'Not a valid URL — use e.g. http://127.0.0.1:8000';
          return;
        }
        localStorage.setItem('crp.endpoint', value);
      } else {
        localStorage.removeItem('crp.endpoint');
      }
      location.reload();
    });
  }

  private bindForm(): void {
    const form = this.container.querySelector('#controls') as HTMLFormElement;
    const input = this.container.querySelector('#message') as HTMLInputElement;
    const depthSelect = this.container.querySelector('#depth') as HTMLSelectElement;
    const depthBadge = this.container.querySelector('#depth-badge') as HTMLElement;
    const sendBtn = this.container.querySelector('#send-btn') as HTMLButtonElement;

    depthSelect.addEventListener('change', () => { depthBadge.textContent = depthSelect.value; });

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const text = input.value.trim();
      if (!text) return;
      this.appendMessage('user', text);
      input.value = '';
      sendBtn.disabled = true;
      this.finalizeAgentMessage();

      const sessionId = this.config.sessionId || `session-${Math.random().toString(36).slice(2, 10)}`;
      const body = JSON.stringify({
        model: 'crp-learned',
        messages: [{ role: 'user', content: text }],
        stream: true,
        session_id: sessionId,
        depth: depthSelect.value,
      });

      this.builder = new NarrativeBuilder();
      this.governance = { risk: '', grounded: false, chain_valid: false, tier: '', confidence: 0, sources: 0 };

      const url = `${this.config.streamUrl}?session_id=${encodeURIComponent(sessionId)}&body=${encodeURIComponent(body)}`;
      const source = new EventSource(url);

      source.onmessage = (ev) => {
        let data: AGUIEvent;
        try { data = JSON.parse(ev.data); } catch { data = { type: ev.data as any }; }
        this.handleEvent(data);
      };
      source.onerror = () => {
        this.logEvent('stream error / closed — is the backend URL reachable and CORS-enabled?', 'halt');
        const dot = this.container.querySelector('#conn-dot') as HTMLElement;
        dot.classList.remove('on');
        dot.classList.add('err');
        sendBtn.disabled = false;
        source.close();
      };
    });
  }

  private bindTabs(): void {
    this.container.querySelectorAll('.tab').forEach((btn) => {
      btn.addEventListener('click', () => {
        this.container.querySelectorAll('.tab').forEach((t) => t.classList.remove('active'));
        (btn as HTMLElement).classList.add('active');
        this.container.querySelectorAll('.tab-panel').forEach((p) => p.classList.add('hidden'));
        const target = this.container.querySelector(`#tab-${(btn as HTMLElement).dataset.tab}`);
        target?.classList.remove('hidden');
      });
    });
  }

  private bindTheme(): void {
    const btn = this.container.querySelector('#theme-toggle') as HTMLElement;
    btn.addEventListener('click', () => {
      const html = document.documentElement;
      const current = html.style.colorScheme;
      html.style.colorScheme = current === 'dark' ? 'light' : 'dark';
    });
  }

  private handleEvent(event: AGUIEvent): void {
    let type = (event.type || event.event || '').toString();
    // CRP custom events are sent as type=CUSTOM with name/value payload; unwrap them.
    if (type === 'CUSTOM' && (event as any).name) {
      type = (event as any).name;
      event = { ...event, type: type as any, payload: (event as any).value } as AGUIEvent;
    }
    this.builder.ingest(event);

    // Update narrative panel incrementally.
    const step = this.builder.steps[this.builder.steps.length - 1];
    if (step) {
      if (step.kind === 'safety' || step.kind === 'quality' || step.kind === 'policy') {
        this.addGovernanceEvent(step.title, step.detail);
      }
      this.addNarrativeStep(step);
    }

    // Update provenance panel.
    if (this.builder.provenance.length > 0) {
      const last = this.builder.provenance[this.builder.provenance.length - 1];
      this.addProvenanceLink(last);
    }

    // Raw event log.
    this.logEvent(type, type.startsWith('crp.') ? 'crp' : '');

    // Streaming answer tokens.
    if (type === 'TEXT_MESSAGE_CONTENT') {
      const payload = event.payload || event.data || {};
      this.appendAgentToken(payload.content || payload.delta || '');
    }

    // Governance cards.
    this.governance = { ...this.governance, ...this.builder.governance };
    this.updateGovernanceCards();

    if (type === 'RUN_FINISHED' || type === 'RUN_ERROR') {
      const sendBtn = this.container.querySelector('#send-btn') as HTMLButtonElement;
      sendBtn.disabled = false;
      this.finalizeAgentMessage();
    }
  }

  private appendMessage(role: 'user' | 'agent', text: string): void {
    this.ensureNotEmpty(this.chatEl);
    const div = document.createElement('div');
    div.className = `message ${role}`;
    div.textContent = text;
    this.chatEl.appendChild(div);
    this.chatEl.scrollTop = this.chatEl.scrollHeight;
    if (role === 'agent') this.currentAgentMessage = div;
  }

  private appendAgentToken(text: string): void {
    if (!this.currentAgentMessage) {
      this.appendMessage('agent', '');
    }
    this.currentAgentMessage!.textContent += text;
    this.chatEl.scrollTop = this.chatEl.scrollHeight;
  }

  private finalizeAgentMessage(): void {
    this.currentAgentMessage = null;
  }

  private addNarrativeStep(step: NarrativeStep): void {
    this.ensureNotEmpty(this.narrativeEl);
    const el = document.createElement('div');
    el.className = `narrative-step ${this.escape(step.kind)}`;
    el.innerHTML = `<div class="narrative-title">${this.escape(step.title)}</div><div class="narrative-detail">${this.escape(step.detail).replace(/\n/g, '<br>')}</div>`;
    this.narrativeEl.appendChild(el);
    this.narrativeEl.scrollTop = this.narrativeEl.scrollHeight;
  }

  private addGovernanceEvent(title: string, detail: string): void {
    this.ensureNotEmpty(this.governanceLogEl);
    const el = document.createElement('div');
    el.className = 'narrative-step safety';
    el.innerHTML = `<div class="narrative-title">${this.escape(title)}</div><div class="narrative-detail">${this.escape(detail)}</div>`;
    this.governanceLogEl.appendChild(el);
    this.governanceLogEl.scrollTop = this.governanceLogEl.scrollHeight;
  }

  private addProvenanceLink(link: ProvenanceLink): void {
    this.ensureNotEmpty(this.provenanceEl);
    const el = document.createElement('div');
    el.className = 'link';
    el.innerHTML = `<span class="hash">${this.escape(link.prev_hash.slice(0, 16) || 'genesis')}</span> → <span class="hash">${this.escape(link.this_hash.slice(0, 16))}</span> <span style="margin-left:auto;color:var(--muted)">${this.escape(link.op)}</span>`;
    this.provenanceEl.appendChild(el);
    this.provenanceEl.scrollTop = this.provenanceEl.scrollHeight;
  }

  private logEvent(text: string, cls: string): void {
    this.ensureNotEmpty(this.eventsEl);
    const el = document.createElement('div');
    el.className = `event ${cls}`;
    const code = document.createElement('code');
    code.textContent = text;
    el.appendChild(code);
    this.eventsEl.appendChild(el);
    this.eventsEl.scrollTop = this.eventsEl.scrollHeight;
  }

  private updateGovernanceCards(): void {
    const riskEl = this.container.querySelector('#g-risk') as HTMLElement;
    riskEl.textContent = this.governance.risk || '—';
    riskEl.className = 'value ' + this.riskClass(this.governance.risk);

    const groundedEl = this.container.querySelector('#g-grounded') as HTMLElement;
    groundedEl.textContent = this.governance.grounded ? 'YES' : 'NO';
    groundedEl.className = 'value ' + (this.governance.grounded ? 'ok' : 'warn');

    const chainEl = this.container.querySelector('#g-chain') as HTMLElement;
    chainEl.textContent = this.governance.chain_valid ? 'VALID' : '—';
    chainEl.className = 'value ' + (this.governance.chain_valid ? 'ok' : 'warn');

    const qualityEl = this.container.querySelector('#g-quality') as HTMLElement;
    qualityEl.textContent = this.governance.tier || '—';

    const confidenceEl = this.container.querySelector('#g-confidence') as HTMLElement;
    confidenceEl.textContent = this.governance.confidence ? this.governance.confidence.toFixed(2) : '—';

    const sourcesEl = this.container.querySelector('#g-sources') as HTMLElement;
    sourcesEl.textContent = this.governance.sources ? String(this.governance.sources) : '—';

    const riskBadge = this.container.querySelector('#risk-badge') as HTMLElement;
    if (this.governance.risk) {
      riskBadge.textContent = this.governance.risk;
      riskBadge.className = 'badge risk-' + this.governance.risk.toLowerCase();
      riskBadge.style.display = 'inline';
    }
    const qualityBadge = this.container.querySelector('#quality-badge') as HTMLElement;
    if (this.governance.tier) {
      qualityBadge.textContent = this.governance.tier;
      qualityBadge.style.display = 'inline';
    }
  }

  private riskClass(risk: string): string {
    const r = risk.toLowerCase();
    if (r.includes('critical')) return 'bad';
    if (r.includes('high')) return 'warn';
    if (r.includes('medium')) return 'warn';
    return 'ok';
  }

  private ensureNotEmpty(el: HTMLElement): void {
    if (el.querySelector('.empty-state')) el.innerHTML = '';
  }

  private escape(text: string): string {
    const div = document.createElement('div');
    div.textContent = String(text ?? '');
    return div.innerHTML;
  }
}
