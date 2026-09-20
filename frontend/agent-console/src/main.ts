import { AgentConsole } from './console.js';
import './style.css';

const app = document.getElementById('app');
if (!app) {
  throw new Error('No #app element found');
}

const storedEndpoint = localStorage.getItem('crp.endpoint') || '';
const base = storedEndpoint.replace(/\/+$/, '');

const config = {
  title: (window as any).CRP_CONSOLE_TITLE || 'CRP Agent Console',
  streamUrl: base
    ? `${base}/v1/tel/stream`
    : (window as any).CRP_STREAM_URL || '/v1/tel/stream',
  chatUrl: base
    ? `${base}/v1/chat/completions`
    : (window as any).CRP_CHAT_URL || '/v1/chat/completions',
  sessionId: (window as any).CRP_SESSION_ID || '',
  endpoint: storedEndpoint,
};

new AgentConsole(app, config);
