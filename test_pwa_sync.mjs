// Focused test for the PWA's Supabase sync logic with a mocked client.
// Run: node test_pwa_sync.mjs
import assert from 'node:assert';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const html = readFileSync(new URL('./index.html', import.meta.url), 'utf8');
const js = html.match(/<script>([\s\S]*?)<\/script>/)[1];

class El {
  constructor() { this._h = ''; this.style = {}; this.dataset = {}; this.value = ''; this.textContent = '';
    this.classList = { toggle() {}, add() {}, remove() {} }; }
  set innerHTML(v) { this._h = v; } get innerHTML() { return this._h; }
  remove() {}
}
const els = new Map();
const elFor = id => { if (!els.has(id)) els.set(id, new El()); return els.get(id); };
const store = {};
const upserts = [];
let cloudRow = null;
const fakeClient = {
  auth: {
    getSession: async () => ({ data: { session: { user: { id: 'user-123', email: 'a@b.c' } } } }),
    signInWithOtp: async () => ({ error: null }),
    verifyOtp: async () => ({ error: null }),
    signOut: async () => ({}),
  },
  from: table => ({
    upsert: async (payload, opts) => { upserts.push({ table, payload, opts }); return { error: null }; },
    select: () => ({ eq: () => ({ maybeSingle: async () => ({ data: cloudRow, error: null }) }) }),
  }),
};
const sandbox = {
  console, setTimeout, clearTimeout, setInterval, clearInterval, Date, JSON, Math, Promise, encodeURIComponent,
  navigator: { vibrate() {} },
  location: { protocol: 'file:', href: 'http://localhost/index.html' },
  confirm: () => true,
  document: {
    querySelector: s => elFor(s), querySelectorAll: () => [],
    getElementById: id => elFor('#' + id),
    createElement: () => new El(), body: { appendChild() {} }, head: { appendChild() {} },
  },
  localStorage: {
    getItem: k => store[k] ?? null, setItem: (k, v) => { store[k] = String(v); }, removeItem: k => { delete store[k]; },
  },
  supabase: { createClient: (url, key) => { assert.match(url, /\.supabase\.co$/); assert.ok(key.length >= 20); return fakeClient; } },
};
sandbox.window = sandbox;
store['ironlog_supabase_v1'] = JSON.stringify({ url: 'https://abcd.supabase.co', key: 'k'.repeat(30), email: 'a@b.c' });
vm.createContext(sandbox);
vm.runInContext(js, sandbox);
await new Promise(r => setTimeout(r, 50));

// Config validation fails closed on junk
assert.equal(sandbox.validSbConfig({ url: 'https://evil.example.com', key: 'k'.repeat(30) }), false);
assert.equal(sandbox.validSbConfig({ url: 'https://abcd.supabase.co', key: 'short' }), false);
assert.equal(sandbox.validSbConfig({ url: 'https://abcd.supabase.co', key: 'k'.repeat(30) }), true);

// Sync upserts the whole local state under the signed-in user's id only
assert.equal(await sandbox.syncToCloud(false), true);
assert.equal(upserts.length, 1);
assert.equal(upserts[0].table, 'workout_state');
assert.equal(upserts[0].payload.user_id, 'user-123');
assert.equal(upserts[0].payload.state.last['Lat Pulldown'].weight_kg, 50);
assert.deepEqual(upserts[0].payload.state.last['Lat Pulldown'].sets, [9, 9, 9, 9]);
assert.equal(upserts[0].opts.onConflict, 'user_id');

// Restore replaces local state with the cloud row (confirm stubbed true)
const cloudState = sandbox.seedState();
cloudState.history = [{ id: 1, date: '2026-10-19T00:00:00.000Z', day_type: 'pull',
  exercises: [{ exercise: 'Lat Pulldown', weight_kg: 55, sets: [8, 8] }] }];
cloudRow = { state: cloudState, updated_at: '2026-10-19T00:00:00.000Z' };
await sandbox.restoreFromCloud();
const restored = JSON.parse(store['ironlog_v1']);
assert.equal(restored.history.length, 1);
assert.equal(restored.history[0].exercises[0].weight_kg, 55);

console.log('PWA SUPABASE SYNC PASS: config validation, signed-in upsert, restore');
process.exit(0);
