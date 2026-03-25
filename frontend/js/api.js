/**
 * Smart Memo — API 客户端
 * 统一封装对后端 HTTP API 的调用
 */

const API_BASE = (() => {
  const port = localStorage.getItem('sm_api_port') || '8765';
  return `http://localhost:${port}/api`;
})();

let _apiOnline = null;

export async function checkHealth() {
  try {
    const r = await fetch(API_BASE.replace('/api', '/health'), { signal: AbortSignal.timeout(2000) });
    _apiOnline = r.ok;
  } catch {
    _apiOnline = false;
  }
  return _apiOnline;
}

export function isOnline() { return _apiOnline; }

// ── 备忘录 API ──────────────────────────────────────────────────────────────

export async function getMemos({ category = 'all', limit = 100, offset = 0 } = {}) {
  const r = await fetch(`${API_BASE}/memos?category=${category}&limit=${limit}&offset=${offset}`);
  return r.json();
}

export async function searchMemos(q, limit = 30) {
  const r = await fetch(`${API_BASE}/memos/search?q=${encodeURIComponent(q)}&limit=${limit}`);
  return r.json();
}

export async function addMemo(content, useAI = true) {
  const r = await fetch(`${API_BASE}/memos`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content, use_ai: useAI }),
  });
  return r.json();
}

export async function updateMemo(id, fields) {
  const r = await fetch(`${API_BASE}/memos/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(fields),
  });
  return r.json();
}

export async function deleteMemo(id) {
  const r = await fetch(`${API_BASE}/memos/${id}`, { method: 'DELETE' });
  return r.json();
}

// ── 分类 API ────────────────────────────────────────────────────────────────

export async function classifyText(text) {
  const r = await fetch(`${API_BASE}/classify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  });
  return r.json();
}

// ── 行程 API ────────────────────────────────────────────────────────────────

export async function getSchedule(date) {
  const r = await fetch(`${API_BASE}/schedule?date=${date}`);
  return r.json();
}

export async function generateSchedule(date, useAI = true) {
  const r = await fetch(`${API_BASE}/schedule/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ date, use_ai: useAI }),
  });
  return r.json();
}

export async function getStats() {
  const r = await fetch(`${API_BASE}/stats`);
  return r.json();
}
