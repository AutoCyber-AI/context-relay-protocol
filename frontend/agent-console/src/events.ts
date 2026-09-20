/** AG-UI + CRP custom event vocabulary consumed by the console. */

export type EventType =
  | 'RUN_STARTED' | 'RUN_FINISHED' | 'RUN_ERROR'
  | 'STEP_STARTED' | 'STEP_FINISHED'
  | 'TEXT_MESSAGE_START' | 'TEXT_MESSAGE_CONTENT' | 'TEXT_MESSAGE_END'
  | 'REASONING_START' | 'REASONING_CONTENT' | 'REASONING_END'
  | 'TOOL_CALL_START' | 'TOOL_CALL_ARGS' | 'TOOL_CALL_END' | 'TOOL_CALL_RESULT'
  | 'STATE_SNAPSHOT' | 'STATE_DELTA' | 'MESSAGES_SNAPSHOT'
  | 'INTERRUPT' | 'CUSTOM' | 'RAW';

export interface AGUIEvent {
  type: EventType | `crp.${string}`;
  seq?: number;
  id?: string;
  ts?: number;
  payload?: Record<string, any>;
  data?: any;
  value?: any;
  event?: string;
}

export interface GovernanceSummary {
  risk: string;
  grounded: boolean;
  chain_valid: boolean;
  tier: string;
  confidence: number;
  semantic_entropy?: number | null;
  sources: number;
}

export interface ProvenanceLink {
  op: string;
  prev_hash: string;
  this_hash: string;
  seq: number;
  ts: number;
}

export interface NarrativeStep {
  kind: string;
  title: string;
  detail: string;
  timestamp: number;
  meta?: Record<string, any>;
}
