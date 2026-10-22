// Robo Cloud's Burrow extension. Uses the real mount hook used by Bulwark.
import { readFileSync, writeFileSync, renameSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { realpathSync } from 'node:fs';
import { createServer, request } from 'node:http';
import { randomBytes, createHash } from 'node:crypto';
import { GroupRoutes } from './group-routes.mjs';
let ctx, groups, proxies = new Map();
const ID = 'robo-storage-aegis';
const AGENT = '_agent';
let automatic = false, enrollmentTimer = null, enrollmentTask = null, lastProbe = null, lastDnsRetry = 0;
const file = () => join(ctx.dataDir, 'burrow-routes.json');
const config = () => JSON.parse(readFileSync(join(ctx.dataDir, 'config.json'), 'utf8'));
function load() { return existsSync(file()) ? JSON.parse(readFileSync(file(), 'utf8')) : {}; }
function save(value) { writeFileSync(file() + '.tmp', JSON.stringify(value, null, 2), { mode: 0o600 }); renameSync(file() + '.tmp', file()); }
function upstream() { const c = config(); const bind = ['0.0.0.0', '::', ''].includes(c.bind) ? '127.0.0.1' : c.bind; return `http://${bind.includes(':') ? '[' + bind + ']' : bind}:${c.port}`; }
function own(port) { return ctx.tunnels.list().find(t => t.port === port && t.app === ID); }
async function naming() {
  const c = config();
  return await new Promise((resolve, reject) => {
    const r = request({ socketPath: realpathSync(c.burrow_socket), path: '/tunnels/naming', headers: { 'X-Burrow-Client': ID + '/' + c.version }, timeout: 10000 }, res => {
      let text = ''; res.on('data', b => { text += b; }); res.on('end', () => { try { if (res.statusCode >= 400) throw Error('Burrow naming is unavailable.'); resolve(JSON.parse(text)); } catch(e) { reject(e); } });
    });
    r.on('error', reject); r.on('timeout', () => r.destroy(Error('Naming lookup timed out.'))); r.end();
  });
}
function actualBase(n, d) { return n.active && n.prefix ? n.prefix + '.' + d.zone : d.zone; }
async function proxy(key, spec) {
  if (proxies.has(key)) return proxies.get(key).address().port;
  const srv = createServer((req, res) => {
    const c = config();
    const path = req.url || '/';
    if (!path.startsWith('/') || path.startsWith('//') || /[\r\n]/.test(path)) { res.writeHead(400); res.end(); return; }
    let target;
    // WHATWG URL normalization must not turn a public path into an admin path.
    let parsed; try { parsed = new URL(path, 'http://local'); } catch { res.writeHead(400); res.end(); return; }
    const rawPath = path.split('?')[0];
    if (rawPath.includes('\\') || /%2f|%5c/i.test(rawPath) || rawPath.split('/').some(p => /^(?:\.|%2e){1,2}$/i.test(p))) { res.writeHead(400); res.end(); return; }
    if (spec.agent) {
      if (!(parsed.pathname.startsWith('/agent/') || ['/enroll.sh', '/enroll.exe'].includes(parsed.pathname))) { res.writeHead(404); res.end(); return; }
      target = path;
    } else {
      target = `/g/${spec.group}${spec.server ? '/s/' + spec.server : ''}` + path;
    }
    const headers = { ...req.headers };
    for (const h of ['x-robo-admin', 'cookie', 'proxy-authorization', 'x-forwarded-for', 'x-forwarded-host']) delete headers[h];
    headers.host = `127.0.0.1:${c.port}`;
    // A group-scoped proxy never injects the administration secret.
    const url = new URL(target, upstream());
    const r = request(url, { method: req.method, headers, timeout: 180000 }, response => {
      res.writeHead(response.statusCode, response.headers); response.pipe(res);
    });
    r.on('timeout', () => r.destroy());
    r.on('error', () => { if (!res.headersSent) res.writeHead(502); res.end('Storage service unavailable'); });
    req.pipe(r);
  });
  for (let attempt = 0; ; attempt++) {
    await new Promise((resolve, reject) => { const fail = e => reject(e); srv.once('error', fail); srv.listen(0, '127.0.0.1', () => { srv.off('error', fail); resolve(); }); });
    if (!ctx.tunnels.list().some(t => t.port === srv.address().port)) break;
    await new Promise(resolve => srv.close(resolve));
    if (attempt >= 7) throw new Error('Unable to allocate a unique local proxy port.');
  }
  proxies.set(key, srv);
  return srv.address().port;
}
function enrollmentSub() { return 'robo-agent-' + createHash('sha256').update(ctx.dataDir).digest('hex').slice(0, 8); }
function writeEnrollment(data) {
  const path = join(ctx.dataDir, 'agent-enrollment.json');
  const value = { updated: Date.now() / 1000, ...data };
  writeFileSync(path + '.tmp', JSON.stringify(value, null, 2), { mode: 0o600 });
  renameSync(path + '.tmp', path);
  return value;
}
async function reachable(url) {
  const nonce = randomBytes(16).toString('hex');
  const r = await fetch(url + '/agent/health?probe=' + nonce, { redirect: 'error', signal: AbortSignal.timeout(6500) });
  if (!r.ok) return false;
  const reader = r.body.getReader();
  let size = 0, chunks = [];
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.length;
    if (size > 2048) { await reader.cancel(); return false; }
    chunks.push(Buffer.from(value));
  }
  const text = Buffer.concat(chunks).toString('utf8');
  const health = JSON.parse(text);
  return health.app === ID && health.ok === true && health.probe === nonce;
}
async function syncEnrollment() {
  if (!automatic) return { state: 'pending', url: '', detail: 'The Burrow extension is restarting.' };
  try {
    const c = config();
    if (!c.admin_key || c.linked) return writeEnrollment({ state: 'error', url: '', detail: 'This is a linked copy. Manage enrollment from the host that owns the storage service.' });
    const routes = load();
    const sub = enrollmentSub();
    let t = routes[AGENT] && own(routes[AGENT].port);
    if (!t) t = ctx.tunnels.list().find(t => t.app === ID && t.sub === sub);
    const targetPort = await proxy(AGENT, { agent: true });
    if (!automatic) return { state: 'pending', url: '' };
    if (!t) {
      lastProbe = null;
      writeEnrollment({ state: 'pending', url: '', detail: 'Burrow is creating a dedicated HTTPS enrollment route automatically.' });
      t = await ctx.tunnels.create({ port: targetPort, targetPort, targetHost: '127.0.0.1', scheme: 'http', name: 'Robo Cloud · Folder-worker enrollment', sub, access: 'public' });
      lastDnsRetry = Date.now();
      const latest = load(); latest[AGENT] = { agent: true, port: t.port, sub }; save(latest);
    } else if (t.targetPort !== targetPort) {
      lastProbe = null;
      t = await ctx.tunnels.update(t.port, { targetPort, targetHost: '127.0.0.1' });
      const latest = load(); latest[AGENT] = { agent: true, port: t.port, sub }; save(latest);
    } else if (!routes[AGENT]) {
      const latest = load(); latest[AGENT] = { agent: true, port: t.port, sub }; save(latest);
    }
    t = own(t.port) || t;
    if (t.enabled !== false && t.dns?.error && Date.now() - lastDnsRetry >= 60000) {
      lastDnsRetry = Date.now();
      t = await ctx.tunnels.update(t.port, {}); // Burrow retries DNS only for this owned route.
    }
    const url = String(t.url || '').replace(/\/+$/, '');
    if (!url.startsWith('https://') || t.enabled === false || t.dns?.ready === false) {
      lastProbe = null;
      return writeEnrollment({ state: 'pending', url: '', port: t.port, detail: 'Burrow is waiting for its HTTPS address and DNS. The URL will be filled in automatically.' });
    }
    let ready = false;
    if (lastProbe?.url === url && Date.now() - lastProbe.at < 20000) ready = true;
    else { ready = await reachable(url); if (ready) lastProbe = { url, at: Date.now() }; }
    if (!automatic) return { state: 'pending', url: '' };
    if (!ready) {
      lastProbe = null;
      return writeEnrollment({ state: 'pending', url: '', port: t.port, detail: 'The route exists; waiting for an HTTPS health check to reach this storage service. No manual enrollment URL is needed.' });
    }
    return writeEnrollment({ state: 'ready', url, port: t.port, checkedAt: lastProbe.at / 1000, detail: 'Created by Burrow and checked over HTTPS. Enrollment is ready.' });
  } catch (e) {
    lastProbe = null;
    if (!automatic) return { state: 'pending', url: '' };
    return writeEnrollment({ state: 'error', url: '', detail: 'Burrow could not prepare the enrollment route yet: ' + String(e.cause?.code || e.message).slice(0, 180) + '. It will retry automatically.' });
  }
}
function ensureEnrollment() {
  if (!enrollmentTask) enrollmentTask = syncEnrollment().finally(() => { enrollmentTask = null; });
  return enrollmentTask;
}
export async function start(c) {
  ctx = c; automatic = true; lastProbe = null; lastDnsRetry = 0;
  groups = new GroupRoutes(ctx, { load, save, proxy, naming });
  const routes = load();
  for (const [key, spec] of Object.entries(routes)) {
    if (key === AGENT || !own(spec.port)) continue;
    const port = await proxy(key, spec);
    await ctx.tunnels.update(spec.port, { targetPort: port });
  }
  // Own one restricted agent route, separate from the signed-in dashboard mount.
  ensureEnrollment().catch(e => ctx.log('enrollment:', e.message));
  groups.refresh().catch(e => ctx.log('group routes:', e.message));
  enrollmentTimer = setInterval(() => { ensureEnrollment().catch(e => ctx.log('enrollment:', e.message)); groups.refresh().catch(e => ctx.log('group routes:', e.message)); }, 15000);
  enrollmentTimer.unref?.();
}
export async function stop() {
  automatic = false;
  clearInterval(enrollmentTimer);
  await enrollmentTask?.catch(() => {});
  await groups?.stop();
  writeEnrollment({ state: 'pending', url: '', detail: 'The Burrow extension is restarting; the enrollment address will be restored automatically.' });
  for (const srv of proxies.values()) srv.close();
  proxies.clear();
}
export function mount() {
  try {
    const c = config();
    return c.admin_key ? { prefix: '/__gate/robo-storage', upstream: upstream(), headers: { 'x-robo-admin': c.admin_key }, name: 'Robo Cloud', tile: { text: 'Your storage, connected. Groups, servers and access.' } } : null;
  } catch { return null; }
}
export async function handle({ method, path, json }) {
  const ok = json => ({ status: 200, json });
  try {
    if ((method === 'GET' || method === 'POST') && path === '/enrollment') return ok(await ensureEnrollment());
    if (method === 'GET' && path === '/environment') return ok(await groups.environment());
    if (method === 'POST' && path === '/publish') return ok(await groups.publish(await json()));
    if ((method === 'GET' || method === 'POST') && path === '/routes') { await groups.refresh(); return ok({ ok: true }); }
    if (method === 'POST' && path === '/unpublish') {
      const b = await json();
      if (b.key === AGENT) throw new Error('The enrollment route is managed automatically.');
      await groups.remove(b.key, async () => {
        const routes = load(), spec = routes[b.key];
        if (spec) {
          if (own(spec.port)) await ctx.tunnels.remove(spec.port);
          proxies.get(b.key)?.close(); proxies.delete(b.key);
          const latest = load(); delete latest[b.key]; save(latest);
        }
      });
      return ok({ ok: true });
    }
    if (method === 'POST' && path === '/unpublish-all') {
      automatic = false; clearInterval(enrollmentTimer); await enrollmentTask?.catch(() => {}); await groups?.stop();
      const routes = load();
      for (const [key, spec] of Object.entries(routes)) {
        if (own(spec.port)) await ctx.tunnels.remove(spec.port);
        proxies.get(key)?.close(); proxies.delete(key); delete routes[key];
        save(routes);
      }
      const snapshot = join(ctx.dataDir, 'published-routes.json'); writeFileSync(snapshot + '.tmp', JSON.stringify({ updated: Date.now() / 1000, groups: {} }), { mode: 0o600 }); renameSync(snapshot + '.tmp', snapshot);
      writeEnrollment({ state: 'pending', url: '', detail: 'Enrollment routes were removed during uninstall.' });
      return ok({ ok: true });
    }
    if (path === '/summary' && method === 'GET') {
      const r = await fetch(upstream() + '/api/state', { headers: { 'x-robo-admin': config().admin_key }, signal: AbortSignal.timeout(5000) });
      const s = await r.json();
      return ok({ groups: s.groups.length, servers: s.servers.filter(s => s.status !== 'removed').length, used: s.servers.reduce((n, s) => n + s.used, 0) });
    }
    return { status: 404, json: { error: 'Unknown extension route.' } };
  } catch (e) { return { status: 400, json: { error: e.message } }; }
}
