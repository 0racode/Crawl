import AsyncStorage from '@react-native-async-storage/async-storage';

const KEY = 'sitecrawler.settings';
let cache = null;

export async function getSettings() {
  if (cache) return cache;
  try {
    const raw = await AsyncStorage.getItem(KEY);
    cache = raw ? JSON.parse(raw) : {};
  } catch { cache = {}; }
  // 10.0.2.2 reaches the host machine from the Android emulator
  cache = { baseUrl: 'http://10.0.2.2:8000', apiKey: '', ...cache };
  return cache;
}

export async function saveSettings(next) {
  cache = { ...(await getSettings()), ...next };
  await AsyncStorage.setItem(KEY, JSON.stringify(cache));
  return cache;
}

async function call(path, { method = 'GET', body } = {}) {
  const { baseUrl, apiKey } = await getSettings();
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 30000);
  try {
    const res = await fetch(baseUrl.replace(/\/+$/, '') + path, {
      method,
      headers: { 'Content-Type': 'application/json', ...(apiKey ? { 'X-API-Key': apiKey } : {}) },
      body: body ? JSON.stringify(body) : undefined,
      signal: ctrl.signal,
    });
    const text = await res.text();
    let data; try { data = JSON.parse(text); } catch { data = text; }
    if (!res.ok) {
      const d = data && data.detail;
      throw new Error(typeof d === 'string' ? d : d ? JSON.stringify(d) : `HTTP ${res.status}`);
    }
    return data;
  } catch (e) {
    if (e.name === 'AbortError') throw new Error('Request timed out. Check the backend URL in Settings.');
    if (e.message === 'Network request failed') throw new Error('Cannot reach the backend. Check the URL in Settings.');
    throw e;
  } finally { clearTimeout(timer); }
}

export const api = {
  health: () => call('/health'),
  createJob: (cfg) => call('/jobs', { method: 'POST', body: cfg }),
  listJobs: () => call('/jobs'),
  getJob: (id) => call(`/jobs/${id}`),
  results: (id, after = 0, limit = 50) => call(`/jobs/${id}/results?after=${after}&limit=${limit}`),
  page: (id, pageId) => call(`/jobs/${id}/pages/${pageId}`),
  cancel: (id) => call(`/jobs/${id}/cancel`, { method: 'POST' }),
  remove: (id) => call(`/jobs/${id}`, { method: 'DELETE' }),
  extract: (body) => call('/extract', { method: 'POST', body }),
  async exportUrl(id, format = 'json') {
    const { baseUrl, apiKey } = await getSettings();
    return `${baseUrl.replace(/\/+$/, '')}/jobs/${id}/export?format=${format}${apiKey ? `&key=${encodeURIComponent(apiKey)}` : ''}`;
  },
};
