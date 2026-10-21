"""Real S3, deployed CloudGate and outbound Linux-agent adapters."""
import base64
import datetime
import hashlib
import hmac
import http.client
import json
import os
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from core import MAX_FILE, Problem, require, clean_path, public_https, uid

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

OPENER = urllib.request.build_opener(NoRedirect)

def request(url, method='GET', data=None, headers=None, maximum=MAX_FILE):
    public_https(url.split('?')[0])
    try:
        req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
        with OPENER.open(req, timeout=40) as r:
            raw = r.read(maximum + 1)
            require(len(raw) <= maximum, 'Response exceeds the preview-release size limit.', 413)
            return raw
    except urllib.error.HTTPError as e:
        # Never echo upstream response bodies, URLs with keys, or credentials.
        raise Problem('Storage provider returned HTTP %d. Check credentials, bucket/category and permissions.' % e.code, 502)
    except (OSError, TimeoutError):
        raise Problem('Storage endpoint unavailable or timed out.', 502)

class Unix(http.client.HTTPConnection):
    def __init__(self, path):
        super().__init__('burrow', timeout=30)
        self.socket_path = os.path.realpath(path)
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.socket_path)

def host_call(cfg, method, path, body=None):
    require(cfg.get('burrow_socket'), 'Burrow control socket is not available. Install this addon in Aegis × Burrow.', 503)
    c = Unix(cfg['burrow_socket'])
    try:
        c.request(method, path, body=json.dumps(body).encode() if body is not None else None, headers={'Content-Type': 'application/json', 'X-Burrow-Client': cfg['id'] + '/' + cfg['version']})
        r = c.getresponse()
        data = json.loads(r.read(4 * 1024 * 1024) or b'{}')
        require(r.status < 400, data.get('error', 'Burrow request failed.'), r.status)
        return data
    except (OSError, ValueError, http.client.HTTPException):
        raise Problem('Burrow is not answering on its control socket.', 503)
    finally:
        c.close()

class E2:
    def __init__(self, server):
        self.c = server['credentials']
    def key(self, path):
        return (self.c['prefix'].rstrip('/') + '/' if self.c.get('prefix') else '') + clean_path(path)
    def call(self, method, path='', query=None, data=b''):
        c = self.c
        host = urllib.parse.urlsplit(c['endpoint']).netloc
        uri = '/' + urllib.parse.quote(c['bucket'], safe='') + ('/' + urllib.parse.quote(self.key(path), safe='/~') if path else '')
        qs = '&'.join(urllib.parse.quote(str(k), safe='~') + '=' + urllib.parse.quote(str(v), safe='~') for k, v in sorted((query or {}).items()))
        now = datetime.datetime.now(datetime.timezone.utc)
        stamp, day = now.strftime('%Y%m%dT%H%M%SZ'), now.strftime('%Y%m%d')
        hashed = hashlib.sha256(data).hexdigest()
        canonical_headers = 'host:%s\nx-amz-content-sha256:%s\nx-amz-date:%s\n' % (host, hashed, stamp)
        signed = 'host;x-amz-content-sha256;x-amz-date'
        canonical = '\n'.join([method, uri, qs, canonical_headers, signed, hashed])
        scope = day + '/' + c['region'] + '/s3/aws4_request'
        to_sign = 'AWS4-HMAC-SHA256\n' + stamp + '\n' + scope + '\n' + hashlib.sha256(canonical.encode()).hexdigest()
        sign = lambda key, msg: hmac.new(key, msg.encode(), hashlib.sha256).digest()
        k = sign(sign(sign(sign(('AWS4' + c['secret']).encode(), day), c['region']), 's3'), 'aws4_request')
        auth = 'AWS4-HMAC-SHA256 Credential=%s/%s, SignedHeaders=%s, Signature=%s' % (c['access'], scope, signed, hmac.new(k, to_sign.encode(), hashlib.sha256).hexdigest())
        return request(c['endpoint'] + uri + ('?' + qs if qs else ''), method, data if method == 'PUT' else None, {'Authorization': auth, 'x-amz-date': stamp, 'x-amz-content-sha256': hashed})
    def scan(self):
        token, out = None, []
        prefix = self.key('')
        while True:
            q = {'list-type': '2', 'prefix': prefix}
            if token:
                q['continuation-token'] = token
            root = ET.fromstring(self.call('GET', query=q))
            ns = {'s': 'http://s3.amazonaws.com/doc/2006-03-01/'}
            for f in root.findall('s:Contents', ns):
                key = f.findtext('s:Key', '', ns)
                if not key.endswith('/'):
                    out.append({'path': key[len(prefix):], 'size': int(f.findtext('s:Size', '0', ns))})
            require(len(out) <= 100000, 'Inventory exceeds 100,000 files.')
            token = root.findtext('s:NextContinuationToken', '', ns)
            if not token:
                break
        return out, None
    def read(self, path):
        return self.call('GET', path)
    def write(self, path, data):
        self.call('PUT', path, data=data)
    def delete(self, path):
        self.call('DELETE', path)

class CloudGate:
    def __init__(self, server):
        self.c = server['credentials']
        self.keys = {}
    def call(self, path, method='GET', body=None, raw=False, content_type=None):
        c = self.c
        auth = base64.b64encode((c['username'] + ':' + c['password']).encode()).decode()
        headers = {'Authorization': 'Basic ' + auth}
        if content_type:
            headers['Content-Type'] = content_type
        elif body is not None:
            headers['Content-Type'] = 'application/json'
            body = json.dumps(body).encode()
        result = request(c['endpoint'] + path, method, body, headers, maximum=MAX_FILE)
        return result if raw else json.loads(result or b'{}')
    def scan(self):
        files = self.call('/api/all-files')
        out = []
        for f in files:
            if f['category'] != self.c['category']:
                continue
            p = ((f.get('folder_path', '').strip('/') + '/') if f.get('folder_path') else '') + f['filename']
            p = clean_path(p, False)
            self.keys[p] = f['key']
            out.append({'path': p, 'size': int(f['size'])})
        return out, None  # account-wide quota must not pretend to be this category's capacity
    def key(self, path):
        self.scan()
        require(path in self.keys, 'CloudGate file not found.', 404)
        return self.keys[path]
    def read(self, path):
        return self.call('/api/download?' + urllib.parse.urlencode({'key': self.key(path)}), raw=True)
    def write(self, path, data):
        boundary = 'robo-' + uid()
        folder, _, name = path.rpartition('/')
        parts = []
        for k, v in [('category', self.c['category']), ('path', folder)]:
            parts.append(('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n' % (boundary, k, v)).encode())
        require('"' not in name and '\r' not in name and '\n' not in name, 'Invalid filename.')
        parts.append(('--%s\r\nContent-Disposition: form-data; name="file"; filename="%s"\r\nContent-Type: application/octet-stream\r\n\r\n' % (boundary, name)).encode() + data + b'\r\n')
        parts.append(('--%s--\r\n' % boundary).encode())
        self.call('/api/upload', 'POST', b''.join(parts), content_type='multipart/form-data; boundary=' + boundary)
    def delete(self, path):
        self.call('/api/files', 'DELETE', {'key': self.key(path)})

class AgentBroker:
    """Tasks are transient. Interrupted writes are idempotent; deletions are never retried automatically."""
    def __init__(self):
        self.lock = threading.Lock()
        self.pending = {}
    def call(self, server, op, **args):
        task = {'id': uid(), 'op': op, **args}
        entry = {'server': server['id'], 'task': task, 'done': threading.Event(), 'sent': False}
        with self.lock:
            self.pending[task['id']] = entry
        try:
            require(entry['done'].wait(65), 'Linux agent did not finish in time. Check the host and test again.', 504)
            result = entry['result']
            require(not result.get('error'), result.get('error', 'Linux operation failed.'), 502)
            return result
        finally:
            with self.lock:
                self.pending.pop(task['id'], None)
    def poll(self, id):
        with self.lock:
            for p in self.pending.values():
                if p['server'] == id and not p['sent']:
                    p['sent'] = True
                    return p['task']
        return None
    def finish(self, id, task, result):
        with self.lock:
            p = self.pending.get(task)
            require(p and p['server'] == id, 'Task expired or not owned by this agent.', 409)
            p['result'] = result
            p['done'].set()

class Linux:
    def __init__(self, server, broker):
        self.s, self.broker = server, broker
    def scan(self):
        r = self.broker.call(self.s, 'scan')
        return r['files'], r['capacity']
    def read(self, path):
        return base64.b64decode(self.broker.call(self.s, 'read', path=path)['data'], validate=True)
    def write(self, path, data):
        self.broker.call(self.s, 'write', path=path, data=base64.b64encode(data).decode())
    def delete(self, path):
        self.broker.call(self.s, 'delete', path=path)

def backend(server, broker):
    return {'e2': lambda: E2(server), 'cloudgate': lambda: CloudGate(server), 'linux': lambda: Linux(server, broker)}[server['kind']]()
