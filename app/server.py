"""Robo Cloud web service. Based on Weft's hello-weft lifecycle skeleton."""
import base64
import collections
import hashlib
import hmac
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import shlex
import sys
sys.dont_write_bytecode = True
import threading
import time
from urllib.parse import parse_qs, unquote, urlsplit

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / 'weft'))
import mesh
from core import Store, Problem, require, uid, digest, password_check, clean_path, quota, label, subdomain, MAX_FILE, validate_partitions, capacity_view
from backends import backend, AgentBroker, host_call
from enrollment import route_status
from routing import routing_view
from partitions import apply_plan
from cloud import visible_partitions, CLOUD_CSP, file_view, rename as rename_files

cfg = mesh.load_config(sys.argv[1])
DATA = Path(sys.argv[1]).resolve().parent
store = Store(DATA)
broker = AgentBroker()
locks = collections.defaultdict(threading.RLock)
failures = collections.defaultdict(list)


def scrub_server(s):
    return next(x for x in store.view()['servers'] if x['id'] == s['id'])


def scan(s):
    with locks[s['id']]:
        try:
            files, capacity = backend(s, broker).scan()
            with store.lock:
                store.update_inventory(s, files, capacity)
        except Exception:
            with store.lock:
                s['error'] = 'Connection test failed. Check credentials, permissions or agent connectivity.'
                store.save()
            raise
    return scrub_server(s)


def upload(s, path, data):
    with locks[s['id']]:
        scan(s)  # refresh externally changed usage before accepting uploads
        with store.lock:
            store.check_write(s, path, len(data))
        b = backend(s, broker)
        b.write(path, data)
        # Verify bytes before reporting a successful upload.
        require(hashlib.sha256(b.read(path)).digest() == hashlib.sha256(data).digest(), 'Upload verification failed.', 502)
        scan(s)
        store.event('File uploaded', s['name'] + ': ' + path)


def start_job(s, body):
    require(not cfg.get('demo'), 'Demo mode never moves or erases remote files.')
    require(body.get('confirmName') == s['name'], 'Type the exact server name to confirm.')
    mode = body.get('mode')
    require(mode in ('move', 'erase'), 'Choose Move files or Permanently erase.')
    targets = body.get('targets', [])
    require(isinstance(targets, list), 'Invalid destinations.')
    if mode == 'move':
        require(targets and sum(t.get('percent', 0) for t in targets) == 100, 'Destination shares must total 100%.')
        require(len(set(t['id'] for t in targets)) == len(targets), 'Each destination can appear once.')
        for t in targets:
            dest = store.get('servers', t['id'])
            require(type(t['percent']) is int and t['percent'] > 0, 'Shares must be positive whole percentages.')
            require(dest['id'] != s['id'] and dest['group'] == s['group'] and dest['verified'] and dest['status'] not in ('draining', 'removed'), 'Choose verified destinations in this group.')
    with locks[s['id']], store.lock:
        require(not any(store.get('servers', j['server'])['group'] == s['group'] and j['state'] == 'running' for j in store.state['jobs']), 'A removal job is already running.', 409)
        s['status'] = 'draining'
        j = {'id': uid(), 'server': s['id'], 'mode': mode, 'state': 'running', 'done': 0, 'total': 0, 'detail': 'Scanning source', 'created': int(time.time())}
        store.state['jobs'].insert(0, j)
        store.event('Server draining', s['name'] + ' / ' + mode)
    def work():
        try:
            with locks[s['id']]:
                scan(s)
                files = list(s['inventory'])
                j['total'] = len(files)
                moved = {t['id']: 0 for t in targets}
                for f in files:
                    require(f['size'] <= MAX_FILE, 'A file exceeds 16 MiB; move it independently before retrying.')
                    source = backend(s, broker)
                    if mode == 'move':
                        # Greedy weighted-bytes allocation; files are indivisible.
                        t = min(targets, key=lambda x: moved[x['id']] / x['percent'])
                        dest = store.get('servers', t['id'])
                        with locks[dest['id']]:
                            scan(dest)
                            require(not any(x['path'] == f['path'] for x in dest['inventory']), 'Destination path already exists; resolve the conflict before retrying: ' + f['path'], 409)
                            data = source.read(f['path'])
                            upload(dest, f['path'], data)
                            # Re-read source: don't delete a file modified while copying.
                            require(hashlib.sha256(source.read(f['path'])).digest() == hashlib.sha256(data).digest(), 'Source changed during migration. Source was retained.', 409)
                            moved[t['id']] += len(data)
                    source.delete(f['path'])
                    j['done'] += 1
                    j['detail'] = 'Processed ' + str(j['done']) + ' files'
                    store.save()
                scan(s)
                require(not s['inventory'], 'Files remain on the source. The server stays in draining mode.', 409)
                # Remove this server’s owned public route before final disconnection.
                if s.get('routePort'):
                    host_call(cfg, 'POST', '/x/' + cfg['id'] + '/unpublish', {'key': s['id']})
                    s.pop('routePort', None)
                    s['url'] = ''
                # Keep a tombstone for history; it is not an available destination.
                s.update(status='removed', verified=False, agentToken='')
                s.pop('credentials', None)
                j.update(state='done', detail='Source is empty. Disconnected; remote agent metadata was not erased.')
                store.event('Server disconnected', s['name'])
        except Exception as ex:
            j.update(state='error', detail=str(ex) if isinstance(ex, Problem) else 'Operation failed. Inspect provider/agent and retry explicitly.')
            store.event('Drain stopped safely', s['name'] + ': ' + j['detail'])
        store.save()
    threading.Thread(target=work, daemon=True).start()
    return {'job': j}


class App(mesh.Handler):
    def log_message(self, *args):
        pass  # Enrollment tokens and user file paths must never appear in access logs.

    def send(self, code, body, ctype='application/json', headers=None):
        data = body if isinstance(body, bytes) else (json.dumps(body) if ctype == 'application/json' else str(body)).encode()
        self.send_response(code)
        self.send_header('Content-Type', ctype + ('; charset=utf-8' if ctype.startswith('text/') or ctype == 'application/json' else ''))
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', (headers or {}).get('Content-Security-Policy', "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'"))
        for k, v in (headers or {}).items():
            if k.lower() != 'content-security-policy':
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def body(self):
        require(not self.headers.get('Transfer-Encoding'), 'Chunked request bodies are not supported.', 411)
        try:
            n = int(self.headers.get('Content-Length', 0))
        except ValueError:
            raise Problem('Invalid Content-Length.')
        require(0 <= n <= 46 * 1024 * 1024, 'Request is too large.', 413)
        try:
            return json.loads(self.rfile.read(n) or b'{}')
        except (ValueError, UnicodeError):
            raise Problem('Invalid JSON body.')

    def basic(self):
        try:
            h = self.headers.get('Authorization', '')
            if not h.startswith('Basic '):
                return None
            user, password = base64.b64decode(h[6:], validate=True).decode().split(':', 1)
            require(len(password) <= 512, 'Password is too long.', 401)
            return user, password
        except (ValueError, UnicodeError):
            return None

    def challenge(self, realm):
        self.send(401, {'error': 'Sign in to continue.'}, headers={'WWW-Authenticate': 'Basic realm="' + realm + '", charset="UTF-8"'})
        return False

    def admin(self):
        if cfg.get('demo'):
            return True
        supplied = self.headers.get('X-Robo-Admin', '')
        if supplied and cfg.get('admin_key') and hmac.compare_digest(supplied, cfg['admin_key']):
            return True
        creds = self.basic()
        if cfg.get('admin_password_hash') and creds and creds[0] == cfg.get('admin_user', 'admin') and password_check(creds[1], cfg['admin_password_hash']):
            return True
        return self.challenge('Robo Cloud administration')

    def group_user(self, id):
        creds = self.basic()
        key = (self.client_address[0], id)
        failures[key] = [t for t in failures[key] if t > time.time() - 60]
        require(len(failures[key]) < 12, 'Too many sign-in attempts. Wait one minute.', 429)
        user = next((u for u in store.state['users'] if u['group'] == id and creds and u['username'] == creds[0] and u.get('enabled')), None)
        if user and password_check(creds[1], user['passwordHash']):
            return user
        if creds:
            failures[key].append(time.time())
        self.challenge('Robo Cloud group ' + id)
        return None

    def agent(self):
        token = self.headers.get('Authorization', '').removeprefix('Bearer ')
        require(len(token) >= 32, 'Agent token required.', 401)
        hashed = digest(token)
        s = next((s for s in store.state['servers'] if s.get('agentToken') and hmac.compare_digest(s['agentToken'], hashed)), None)
        require(s and s['status'] != 'removed', 'Agent token is invalid or revoked.', 401)
        return s

    def do_GET(self):
        self.dispatch('GET')
    def do_POST(self):
        self.dispatch('POST')

    def dispatch(self, method):
        try:
            u = urlsplit(self.path)
            path, q = u.path, parse_qs(u.query)
            if path == '/health' and method == 'GET':
                return self.send(200, {'app': cfg['id'], 'ok': True, 'version': cfg['version']})
            if path.startswith('/agent/') or path == '/enroll.sh':
                return self.agent_route(method, path, q)
            if method != 'GET':
                require(self.headers.get('X-Robo-Request') == '1', 'Same-origin application request required.', 403)
            if path.startswith('/g/'):
                require(not cfg.get('demo') or method == 'GET', 'Demo mode never writes remote files.', 403)
                return self.group_route(method, path, q)
            if not self.admin():
                return
            if path.startswith('/api/cloud/'):
                return self.cloud_admin(method,path,q)
            if method == 'GET' and (path in ('/','/cloud','/manage') or path.startswith('/assets/')):
                return self.static(path)
            if method == 'GET' and path == '/api/state':
                route = route_status(DATA)
                return self.send(200, {**routing_view(DATA, store.view()), 'demo': bool(cfg.get('demo')), 'version': cfg['version'], 'publicUrl': route.get('url', ''), 'agentRoute': route, 'maxFileBytes': MAX_FILE})
            if method == 'GET' and path == '/api/host':
                if cfg.get('demo'):
                    return self.send(200, {'domains': ['example.com'], 'rootDomains': [{'domain': 'example.com', 'available': False}], 'base': 'apps.example.com', 'routingBases': [{'base': 'apps.example.com', 'zone': 'example.com', 'kind': 'primary'}], 'mode': 'demo', 'tunnels': [], 'connected': False, 'note': 'Illustrative routing only — no Burrow host is connected.'})
                return self.send(200, host_call(cfg, 'GET', '/x/' + cfg['id'] + '/environment'))
            if method == 'POST':
                body = self.body()
                result = self.admin_post(path, body)
                return self.send(200, result)
            self.send(404, {'error': 'Not found.'})
        except Problem as ex:
            self.send(ex.status, {'error': str(ex)})
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as ex:
            print('request error:', type(ex).__name__, flush=True)
            self.send(500, {'error': 'Operation failed. No success was assumed; inspect service logs and connection settings.'})

    def static(self, path):
        if path == '/cloud':
            return self.cloud_document(True)
        if path in ('/', '/manage'):
            file = ROOT / 'static' / 'index.html'
        elif path == '/assets/logo.png':
            file = ROOT.parent / 'logo.png'
        else:
            name = path.removeprefix('/assets/')
            allowed={'app.js','style.css','aegis.css','files.js','files.html','robo.css','robo-theme.js','e2.svg','cloudgate.svg','linux.svg','cloud-logo.png','cloud-reference.css','cloud-mime.js','cloud-bridge.js','cloud-ui.js','cloud-synth.js','cloud-pdf-config.js','cloud-shell.js','cloud-fixes.css','partition-manager.js','partition-manager.css'}
            vendor=name.startswith('vendor/') and name.count('/')==1 and not name.split('/')[-1].startswith('.') and (ROOT/'static'/name).is_file()
            require(name in allowed or vendor, 'Not found.',404)
            file=ROOT/'static'/name
        require(file.is_file(), 'Not found.', 404)
        return self.send(200, file.read_bytes(), mimetypes.guess_type(str(file))[0] or 'application/octet-stream')

    def cloud_document(self, admin):
        html=(ROOT/'static/cloud.html').read_text().replace('__CLOUD_ADMIN__','true' if admin else 'false')
        return self.send(200,html,'text/html',{'Content-Security-Policy':CLOUD_CSP})

    def cloud_download(self,s,path,q):
        with locks[s['id']]:data=backend(s,broker).read(path)
        inline=q.get('inline',[''])[0]=='1'
        mime=(mimetypes.guess_type(path)[0] or 'application/octet-stream') if inline else 'application/octet-stream'
        if mime in ('text/html','application/xhtml+xml'):mime='text/plain'
        from urllib.parse import quote
        headers={'Content-Disposition':('inline' if inline else 'attachment')+"; filename*=UTF-8''"+quote(path.split('/')[-1],safe=''),'Accept-Ranges':'bytes'}
        if inline:headers['Content-Security-Policy']="default-src 'none'; img-src 'self' data: blob:; style-src 'unsafe-inline'; sandbox"
        code=200;request_range=self.headers.get('Range')
        if request_range:
            match=re.fullmatch(r'bytes=(\d*)-(\d*)',request_range)
            require(match and (match[1] or match[2]),'Invalid byte range.',416)
            total=len(data)
            start=int(match[1]) if match[1] else max(0,total-int(match[2]))
            end=min(total-1,int(match[2])) if match[1] and match[2] else total-1
            require(0<=start<=end<total,'Range outside file.',416)
            data=data[start:end+1];code=206;headers['Content-Range']=f'bytes {start}-{end}/{total}'
        return self.send(code,data,mime,headers)

    def cloud_admin(self,method,path,q):
        servers=[s for s in store.state['servers'] if s['status']!='removed']
        body=self.body() if method=='POST' else {}
        selected=body.get('server') or q.get('server',[servers[0]['id'] if servers else ''])[0]
        user={'username':'Aegis administrator','rules':[{'path':'','access':'write'}]}
        if method=='GET' and path=='/api/cloud/files':
            return self.send(200,{**file_view(store,servers,selected,user,'Robo Cloud'),'demo':bool(cfg.get('demo'))})
        s=next((s for s in servers if s['id']==selected),None);require(s,'Select a connected storage server.',404)
        p=clean_path(body.get('path') or q.get('path',[''])[0],False)
        if method=='GET' and path=='/api/cloud/download':return self.cloud_download(s,p,q)
        require(method=='POST','Not found.',404)
        require(not cfg.get('demo'),'Demo mode never writes remote files.',403)
        require(s['status']!='draining' and not s.get('readOnly'),'Server is read-only or draining.',409)
        if path=='/api/cloud/rename':return self.send(200,rename_files(store,broker,locks,scan,upload,s,user,body))
        if path=='/api/cloud/upload':
            try:data=base64.b64decode(body.get('data',''),validate=True)
            except ValueError:raise Problem('Invalid file payload.')
            upload(s,p,data);return self.send(200,{'ok':True})
        if path=='/api/cloud/delete':
            require(body.get('confirmPath')==p,'Confirm the exact file path.')
            with locks[s['id']]:backend(s,broker).delete(p);scan(s)
            store.event('File deleted',s['name']+': '+p);return self.send(200,{'ok':True})
        raise Problem('Not found.',404)

    def admin_post(self, path, body):
        if path == '/api/groups':
            with store.lock:
                return {'group': store.group(body)}
        m = re.fullmatch(r'/api/groups/([a-f0-9]+)/servers', path)
        if m:
            with store.lock:
                return {'server': scrub_server(store.server(m[1], body))}
        m = re.fullmatch(r'/api/groups/([a-f0-9]+)/users', path)
        if m:
            with store.lock:
                return store.user(m[1], body)
        m = re.fullmatch(r'/api/servers/([a-f0-9]+)/(test|settings|partition|partitions|enrollment|drain|pause)', path)
        if m:
            s = store.get('servers', m[1])
            action = m[2]
            require(s['status'] != 'removed', 'Server is disconnected.', 409)
            require(s['status'] != 'draining' or action in ('test', 'drain'), 'Management is blocked while draining.', 409)
            if action == 'test':
                require(not cfg.get('demo'), 'Demo usage is illustrative. Connect a real backend to test it.')
                return {'server': scan(s)}
            if action == 'enrollment':
                require(s['kind'] == 'linux', 'Only Linux uses an agent.')
                require(not cfg.get('demo'), 'Agent enrollment is unavailable in the demo.')
                route = route_status(DATA)
                if route['state'] != 'ready':
                    try:
                        host_call(cfg, 'POST', '/x/' + cfg['id'] + '/enrollment', {})
                    except Exception:
                        pass  # A host restart must not produce or guess a callback URL.
                    route = route_status(DATA)
                require(route['state'] == 'ready', route['detail'], 503)
                base_url = route['url']
                token = secrets.token_urlsafe(32)
                e = {'id': digest(token), 'server': s['id'], 'expires': int(time.time()) + 900, 'used': False, 'baseUrl': base_url}
                with store.lock:
                    store.state['enrollments'] = [x for x in store.state['enrollments'] if x['expires'] > time.time() and x['server'] != s['id']]
                    store.state['enrollments'].append(e)
                    store.save()
                url = base_url + '/enroll.sh?token=' + token
                # Download to a private temporary file, never pipe a failed response to bash.
                command = 'f=$(mktemp) && curl --proto \'=https\' --tlsv1.2 -fsS ' + shlex.quote(url) + ' -o "$f" && bash "$f"; rc=$?; rm -f "$f"; (exit "$rc")'
                return {'command': command, 'expires': e['expires']}
            if action == 'drain':
                return start_job(s, body)
            if action == 'pause':
                with locks[s['id']], store.lock:
                    s['readOnly'] = body.get('readOnly', True) is True
                    store.event('Server write access changed', s['name'])
                return {'ok': True}
            require(s['status'] != 'draining', 'Management is blocked while draining. Only tests and removal retries are allowed.', 409)
            with locks[s['id']], store.lock:
                if action == 'settings':
                    limit = quota(body.get('limit', s['limit']))
                    require(not limit or limit >= s['used'], 'Quota cannot be below current usage.')
                    validate_partitions(s['partitions'], limit)
                    s.update(limit=limit, name=label(body.get('name', s['name'])), readOnly=body.get('readOnly', s.get('readOnly', False)) is True)
                if action == 'partitions':
                    apply_plan(s,body)
                if action == 'partition':
                    p = clean_path(body.get('path', ''), False)
                    limit = quota(body.get('limit', 0))
                    existing = next((x for x in s['partitions'] if x['path'] == p), None)
                    # Nested partitions are budgets, not allocated disk images.
                    used = sum(f['size'] for f in s['inventory'] if f['path'] == p or f['path'].startswith(p + '/'))
                    require(not limit or limit >= used, 'Partition quota is below current usage.')
                    candidate = {'id': existing['id'] if existing else uid(), 'name': label(body.get('name', existing['name'] if existing else p)), 'path': p, 'limit': limit}
                    updated = [x for x in s['partitions'] if x != existing] + [candidate]
                    validate_partitions(updated, s['limit'])
                    s['partitions'] = updated
                store.event('Server settings updated', s['name'])
            return {'server': scrub_server(s)}
        m = re.fullmatch(r'/api/(groups|servers)/([a-f0-9]+)/launch', path)
        if m:
            require(not cfg.get('demo'), 'Demo mode cannot create live tunnels.')
            obj = store.get(m[1], m[2])
            if m[1] == 'servers':
                require(obj['verified'] and obj['status'] not in ('draining', 'removed'), 'Verify the server before launching.', 409)
                group = store.get('groups', obj['group'])
            else:
                group = obj
            require(any(u['group'] == group['id'] and u.get('enabled') for u in store.state['users']), 'Create at least one group user before publishing.')
            # Server launch always inherits its group. Ignore supplied server-level address fields.
            with locks['route:' + group['id']]:
                request = body if m[1] == 'groups' else {}
                sub = subdomain(request.get('sub', group['sub']))
                use_default = request.get('useDefaultTunnel', group.get('useDefaultTunnel', True))
                require(type(use_default) is bool, 'Invalid default-tunnel option.')
                base = request.get('base', group.get('base') or group.get('domain', '')) if not use_default else ''
                result = host_call(cfg, 'POST', '/x/' + cfg['id'] + '/publish', {'key': group['id'], 'group': group['id'], 'server': '', 'sub': sub, 'base': base, 'useDefaultTunnel': use_default, 'name': group['name']})
                with store.lock:
                    group.update(sub=sub, useDefaultTunnel=use_default, base=base, domain=base, tunnelSub='', url=result.get('url', ''), proposedUrl=result.get('proposedUrl',''), routeState=result.get('state','pending'), routePort=result.get('port'))
                    store.event('Group route requested', group['name'] + '; servers inherit the group address')
                if m[1] == 'servers':
                    result = {**result, 'groupUrl': result.get('url',''), 'url': result['url'].rstrip('/') + '/s/' + obj['id'] + '/' if result.get('url') else '', 'inheritsGroupAddress': True}
                return result
        raise Problem('Unknown operation.', 404)

    def agent_route(self, method, path, q):
        require(not cfg.get('demo'), 'Agent endpoints are disabled in demo mode.', 403)
        if method == 'GET' and path == '/agent/health':
            nonce = str(q.get('probe', [''])[0])
            require(bool(re.fullmatch(r'[a-f0-9]{32}', nonce)), 'Invalid health probe.', 400)
            return self.send(200, {'app': cfg['id'], 'ok': True, 'probe': nonce, 'version': cfg['version']})
        if method == 'GET' and path == '/enroll.sh':
            token = q.get('token', [''])[0]
            with store.lock:
                e = next((e for e in store.state['enrollments'] if e['id'] == digest(token)), None)
                require(e and not e['used'] and e['expires'] > time.time(), 'Enrollment expired or already used.', 410)
                s = store.get('servers', e['server'])
            require(e.get('baseUrl', '').startswith('https://'), 'Regenerate this enrollment command; it predates automatic HTTPS routing.', 410)
            payload = base64.urlsafe_b64encode(json.dumps({'url': e['baseUrl'], 'enrollment': token, 'root': s['path']}).encode()).decode()
            source = base64.b64encode((ROOT / 'agent.py').read_bytes()).decode()
            script = '#!/usr/bin/env bash\nset -euo pipefail\ncommand -v python3 >/dev/null || { echo "Install Python 3 first"; exit 1; }\nf=$(mktemp)\ntrap \'rm -f "$f"\' EXIT\nprintf %s ' + shlex.quote(source) + ' | base64 -d > "$f"\npython3 "$f" bootstrap ' + shlex.quote(payload) + '\n'
            return self.send(200, script, 'text/x-shellscript')
        require(method == 'POST', 'Not found.', 404)
        body = self.body()
        if path == '/agent/enroll':
            token = self.headers.get('Authorization', '').removeprefix('Bearer ')
            with store.lock:
                e = next((e for e in store.state['enrollments'] if e['id'] == digest(token)), None)
                require(e and not e['used'] and e['expires'] > time.time(), 'Enrollment expired or already used.', 410)
                s = store.get('servers', e['server'])
                require(s['status'] != 'removed', 'Server was removed.', 410)
                store.update_inventory(s, body.get('files', []), body.get('capacity'))
                s.update(verified=False, probeDone=True, hostname=str(body.get('hostname', ''))[:100], resolvedPath=str(body.get('root', ''))[:1000])
                secret = secrets.token_urlsafe(48)
                s['agentToken'] = digest(secret)
                e['used'] = True
                store.event('Linux probe completed', s['name'] + '; waiting for worker heartbeat')
            return self.send(200, {'token': secret})
        s = self.agent()
        with store.lock:
            s['lastSeen'] = int(time.time())
            if s.get('probeDone'):
                s['verified'] = True
                if s['status'] == 'pending':
                    s['status'] = 'online'
            store.save()
        if path == '/agent/poll':
            return self.send(200, {'task': broker.poll(s['id'])})
        if path == '/agent/result':
            broker.finish(s['id'], body.get('task'), body.get('result', {}))
            return self.send(200, {'ok': True})
        raise Problem('Unknown agent endpoint.', 404)

    def group_route(self, method, path, q):
        match = re.fullmatch(r'/g/([a-f0-9]+)(?:/s/([a-f0-9]+))?(/.*)?', path)
        require(match, 'Invalid group URL.', 404)
        gid, sid, rest = match[1], match[2], match[3] or '/'
        group = store.get('groups', gid)
        if method == 'GET' and rest == '/route-health':
            nonce = str(q.get('probe', [''])[0])
            require(bool(re.fullmatch(r'[a-f0-9]{32}', nonce)), 'Invalid route probe.', 400)
            return self.send(200, {'app': cfg['id'], 'ok': True, 'version': cfg['version'], 'group': gid, 'probe': nonce})
        user = self.group_user(gid)
        if not user:
            return
        servers = [s for s in store.state['servers'] if s['group'] == gid and s['status'] != 'removed']
        if sid:
            require(any(s['id'] == sid for s in servers), 'Server not found in group.', 404)
            servers = [s for s in servers if s['id'] == sid]
        if method == 'GET' and (rest == '/' or rest.startswith('/assets/')):
            if rest == '/':
                return self.cloud_document(False)
            return self.static(rest)
        from core import visible
        if method == 'GET' and rest == '/api/files':
            selected = q.get('server', [sid or (servers[0]['id'] if servers else '')])[0]
            s = next((s for s in servers if s['id'] == selected), None)
            require(not sid or selected == sid, 'This link is scoped to one server.', 403)
            files = [f for f in s['inventory'] if visible(user, f['path'])] if s else []
            return self.send(200, {'partitions':visible_partitions(s,user) if s else [], 'group': group['name'], 'username': user['username'], 'servers': [{'id': s['id'], 'name': s['name'], 'status': s['status'], 'used': s['used'], 'limit': s['limit'], 'readOnly': s.get('readOnly', False), **capacity_view(s)} for s in servers], 'selected': selected, 'files': files, 'rules': user['rules']})
        body = self.body() if method == 'POST' else {}
        selected = body.get('server') or q.get('server', [sid or ''])[0]
        s = next((s for s in servers if s['id'] == selected), None)
        require(s and (not sid or selected == sid), 'Server is not part of this storage link.', 403)
        p = clean_path(body.get('path') or q.get('path', [''])[0], False)
        if method == 'GET' and rest == '/api/download':
            require(visible(user,p),'This file is not visible to your user.',403)
            return self.cloud_download(s,p,q)
        require(method == 'POST', 'Not found.', 404)
        require(visible(user, p, 'write'), 'This file or directory is view-only or hidden.', 403)
        require(s['status'] != 'draining' and not s.get('readOnly'), 'Server is read-only or draining.', 409)
        if rest == '/api/rename':
            return self.send(200,rename_files(store,broker,locks,scan,upload,s,user,body))
        if rest == '/api/upload':
            try:
                data = base64.b64decode(body.get('data', ''), validate=True)
            except ValueError:
                raise Problem('Invalid file payload.')
            upload(s, p, data)
            return self.send(200, {'ok': True})
        if rest == '/api/delete':
            require(body.get('confirmPath') == p, 'Confirm the exact file path.')
            with locks[s['id']]:
                backend(s, broker).delete(p)
                scan(s)
            store.event('File deleted', s['name'] + ': ' + p)
            return self.send(200, {'ok': True})
        raise Problem('Not found.', 404)


mesh.heartbeat(lambda: mesh.announce(cfg, 'Robo Cloud', ['storage', 'dashboard'], items=[{'name': g['id'], 'title': g['name'], 'running': True, 'url': g.get('url', '')} for g in store.state['groups']]))
mesh.serve(cfg, App)
