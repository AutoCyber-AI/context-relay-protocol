import type { AGUIEvent, NarrativeStep, GovernanceSummary, ProvenanceLink } from './events.js';

export class NarrativeBuilder {
  steps: NarrativeStep[] = [];
  governance: GovernanceSummary = {
    risk: '',
    grounded: false,
    chain_valid: false,
    tier: '',
    confidence: 0,
    sources: 0,
  };
  provenance: ProvenanceLink[] = [];

  private reasoningBuffer: string[] = [];
  private textBuffer: string[] = [];
  private currentToolName = '';

  ingest(event: AGUIEvent): void {
    const type = (event.type || event.event || '').toString();
    const payload = event.payload || event.value || event.data || {};

    if (type.startsWith('crp.')) {
      this.onCustom(type, payload, event);
    } else {
      switch (type) {
        case 'RUN_STARTED': this.onRunStarted(payload); break;
        case 'RUN_FINISHED': this.onRunFinished(); break;
        case 'RUN_ERROR': this.onRunError(payload); break;
        case 'STEP_STARTED': this.onStepStarted(payload); break;
        case 'STEP_FINISHED': this.onStepFinished(payload); break;
        case 'REASONING_START': this.reasoningBuffer = []; break;
        case 'REASONING_CONTENT': this.reasoningBuffer.push(payload.delta || ''); break;
        case 'REASONING_END': this.flushReasoning(); break;
        case 'TEXT_MESSAGE_START': this.textBuffer = []; break;
        case 'TEXT_MESSAGE_CONTENT': this.textBuffer.push(payload.content || payload.delta || ''); break;
        case 'TEXT_MESSAGE_END': this.flushText(); break;
        case 'TOOL_CALL_START': this.onToolStart(payload); break;
        case 'TOOL_CALL_ARGS': this.onToolArgs(payload); break;
        case 'TOOL_CALL_END': break;
        case 'TOOL_CALL_RESULT': this.onToolResult(payload); break;
        case 'INTERRUPT': this.onInterrupt(payload); break;
      }
    }
  }

  private add(kind: string, title: string, detail: string, meta?: Record<string, any>, ts = Date.now() / 1000): void {
    this.steps.push({ kind, title, detail, timestamp: ts, meta });
  }

  private flushReasoning(): void {
    const text = this.reasoningBuffer.join('').trim();
    if (text) this.add('reasoning', 'Thinking', text);
    this.reasoningBuffer = [];
  }

  private flushText(): void {
    const text = this.textBuffer.join('').trim();
    if (text) this.add('answer', 'Final answer', text);
    this.textBuffer = [];
  }

  private onRunStarted(payload: any): void {
    this.add('run', 'Run started', `Goal: ${payload.goal || '(user request)'}`, payload);
  }

  private onRunFinished(): void {
    this.flushReasoning();
    this.flushText();
    this.add('run-done', 'Run finished', 'Governance summary available.');
  }

  private onRunError(payload: any): void {
    this.flushReasoning();
    this.flushText();
    this.governance.risk = 'CRITICAL';
    this.add('error', 'Run halted', payload.error || 'Unknown error', payload);
  }

  private onStepStarted(payload: any): void {
    this.add('operation', `Operation: ${payload.step || ''}`, 'Positioning the task and selecting tools.', payload);
  }

  private onStepFinished(payload: any): void {
    this.add('operation-done', `Operation completed: ${payload.step || ''}`, '', payload);
  }

  private onToolStart(payload: any): void {
    this.currentToolName = payload.toolCallName || '';
    const reason = payload.reason || '';
    this.add('tool-select', `Tool selected — ${this.currentToolName}`, reason ? `Reason: ${reason}` : '', payload);
  }

  private onToolArgs(payload: any): void {
    const delta = payload.delta || '';
    if (!delta) return;
    const last = this.steps[this.steps.length - 1];
    if (last && last.kind === 'tool-call') {
      last.detail += delta;
    } else {
      this.add('tool-call', `Calling ${this.currentToolName}`, delta);
    }
  }

  private onToolResult(payload: any): void {
    const content = payload.content;
    let summary = '';
    if (typeof content === 'string') {
      summary = content.length > 200 ? content.slice(0, 200) + '…' : content;
    } else {
      summary = JSON.stringify(content).slice(0, 200) + '…';
    }
    this.add('tool-result', 'Tool result received', summary, payload);
  }

  private onInterrupt(payload: any): void {
    this.add('interrupt', 'Human oversight required', payload.reason || '', payload);
  }

  private onCustom(type: string, payload: any, event: AGUIEvent): void {
    switch (type) {
      case 'crp.intent': {
        const ops = (payload.plan || []).join(', ');
        this.add('intent', 'Intent classified', `${payload.detail || ''}${ops ? ' → operations: ' + ops : ''}`, payload);
        break;
      }
      case 'crp.safety_scan':
        this.add('safety', `Safety scan — ${payload.risk || ''}`, `Stage: ${payload.stage || ''}; verdict: ${payload.verdict || ''}`, payload);
        break;
      case 'crp.quality': {
        this.governance.risk = payload.risk || this.governance.risk;
        this.governance.tier = payload.tier || this.governance.tier;
        this.governance.confidence = payload.confidence || 0;
        this.add('quality', `Quality tier: ${payload.tier || ''}`, `Confidence: ${(payload.confidence || 0).toFixed(2)}`, payload, event.ts || Date.now() / 1000);
        break;
      }
      case 'crp.verification':
        this.add('verification', 'Verification relay', `Invalid: ${payload.invalid || 0}; repairs: ${payload.repairs || 0}`, payload);
        break;
      case 'crp.retrieval': {
        const sources = (payload.sources || []).length;
        this.governance.sources = sources;
        this.add('retrieval', 'Retrieval', `${sources} source(s) identified`, payload);
        break;
      }
      case 'crp.provenance': {
        this.governance.chain_valid = true;
        this.provenance.push({
          op: payload.op || 'agent_run',
          prev_hash: payload.prev || 'genesis',
          this_hash: payload.hash || '',
          seq: event.seq || 0,
          ts: event.ts || Date.now() / 1000,
        });
        const prev = (payload.prev || 'genesis').toString().slice(0, 16);
        const cur = (payload.hash || '').toString().slice(0, 16);
        this.add('provenance', 'Provenance link added', `${prev} → ${cur}`, payload);
        break;
      }
      case 'crp.policy':
        this.add('policy', 'Policy envelope checked', `Verdict: ${payload.verdict || 'allow'}`, payload);
        break;
      case 'crp.run_complete':
        this.add('run', 'Positioned loop complete', payload.detail || '', payload);
        break;
      case 'crp.progress':
        this.add('progress', `Progress: ${payload.percent || 0}%`, payload.current || '', payload);
        break;
      case 'crp.trust': {
        const ts = payload.score !== undefined ? Number(payload.score).toFixed(2) : '—';
        this.add('safety', `Trust decision — ${payload.action || ''}`, `Score: ${ts}${payload.reason ? '; ' + payload.reason : ''}`, payload);
        break;
      }
      case 'crp.kill_switch':
        this.governance.risk = 'CRITICAL';
        this.add('interrupt', 'Kill switch fired', `${payload.reason || 'trust collapsed'} (score ${Number(payload.trust_score || 0).toFixed(2)})`, payload);
        break;
      case 'crp.checkpoint': {
        const cpAction = payload.action || '';
        if (cpAction === 'requested') {
          this.add('interrupt', 'Checkpoint requested', payload.request_id || 'human oversight required', payload);
        } else {
          this.add('safety', 'Checkpoint resolved', `${payload.resolution || ''}${payload.reviewer ? ' by ' + payload.reviewer : ''}`, payload);
        }
        break;
      }
      case 'crp.governance': {
        const g = payload as GovernanceSummary;
        if (g.risk !== undefined) this.governance.risk = g.risk;
        if (g.grounded !== undefined) this.governance.grounded = g.grounded;
        if (g.chain_valid !== undefined) this.governance.chain_valid = g.chain_valid;
        if (g.tier !== undefined) this.governance.tier = g.tier;
        if (g.confidence !== undefined) this.governance.confidence = g.confidence;
        if (g.sources !== undefined) this.governance.sources = g.sources;
        this.add('quality', 'Governance summary', `Risk: ${g.risk || '—'} | grounded: ${g.grounded ? 'yes' : 'no'} | sources: ${g.sources ?? '—'}`, payload);
        break;
      }
      default:
        this.add('custom', type, JSON.stringify(payload), payload);
    }
  }
}
