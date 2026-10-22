"""Robo Cloud core. Standard library only; state never lives in ADDON_DIR."""
import base64
import copy
import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import socket
import threading
import time
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

MAX_FILE = 16 * 1024 * 1024
COLORS = {'audio': '#b39aff', 'video': '#f5b86c', 'images': '#66b8ee', 'text': '#75cfac', 'code': '#f58da0', 'other': '#8795aa'}

class Problem(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status

def require(ok, message, status=400):
    if not ok:
        raise Problem(message, status)

def uid():
    return secrets.token_hex(8)

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def password_hash(password):
    require(isinstance(password, str) and 12 <= len(password) <= 512, 'Use a password of 12–512 characters.')
    salt = secrets.token_bytes(16)
    return salt.hex() + ':' + hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1).hex()

def password_check(password, encoded):
    try:
        salt, expected = encoded.split(':')
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False

def clean_path(value, allow_empty=True):
    require(isinstance(value, str) and len(value) <= 1024 and '\\' not in value and '\x00' not in value, 'Invalid storage path.')
    require(not value.startswith('/') and all(p not in ('.', '..', '.robo-agent') for p in value.split('/')), 'Use a relative path without traversal or reserved directories.')
    require(allow_empty or bool(value), 'A file path is required.')
    return value.strip('/')

def linux_path(value):
    require(isinstance(value, str) and (value.startswith('~/') or value.startswith('/')), 'Start with ~/ for your home directory or / for an absolute path.')
    require(len(value) <= 1000 and '\x00' not in value and '\n' not in value and '..' not in value.split('/'), 'Invalid Linux directory.')
    require(value not in ('/', '~/', '/etc', '/proc', '/sys', '/dev', '/boot', '/usr', '/bin', '/var', '/home'), 'Choose a dedicated storage directory, not a system root.')
    require(not any(value.startswith(p + '/') for p in ('/etc', '/proc', '/sys', '/dev', '/boot', '/usr', '/bin')), 'System directories cannot be storage roots.')
    return value.rstrip('/')

def label(value):
    require(isinstance(value, str) and 1 <= len(value.strip()) <= 60, 'Name must be 1–60 characters.')
    return value.strip()

def subdomain(value):
    require(isinstance(value, str) and re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', value), 'Use a DNS label: lowercase letters, digits and internal dashes.')
    return value

def quota(value):
    require(type(value) is int and 0 <= value <= 10**15, 'Invalid capacity. Use a non-negative byte count; 0 means no configured limit.')
    return value

def validate_partitions(partitions, server_limit):
    """Validate a directory-budget tree without double-counting nested budgets."""
    for parent in [None, *partitions]:
        prefix = parent['path'] if parent else None
        children = []
        for p in partitions:
            ancestors = [a for a in partitions if p['path'].startswith(a['path'] + '/')]
            closest = max(ancestors, key=lambda a: len(a['path'])) if ancestors else None
            if closest is parent:
                children.append(p)
        ceilings = ([server_limit] if server_limit else []) + ([parent['limit']] if parent and parent['limit'] else [])
        if parent:
            ceilings += [a['limit'] for a in partitions if parent['path'].startswith(a['path'] + '/') and a['limit']]
        ceiling = min(ceilings) if ceilings else 0
        if ceiling:
            require(sum(p['limit'] for p in children) <= ceiling, 'Child partition budgets exceed their parent or server quota.')
            require(all(not p['limit'] or p['limit'] <= ceiling for p in children), 'A partition budget exceeds its parent or server quota.')
    for p in partitions:
        ancestors = [a for a in partitions if p['path'].startswith(a['path'] + '/') and a['limit']]
        ceilings = [a['limit'] for a in ancestors] + ([server_limit] if server_limit else [])
        require(not p['limit'] or not ceilings or p['limit'] <= min(ceilings), 'A partition budget exceeds an inherited quota.')


def public_https(value):
    u = urlsplit(value)
    require(u.scheme == 'https' and u.hostname and not u.username and not u.password and not u.query and not u.fragment, 'Use an HTTPS URL without credentials, query or fragment.')
    try:
        for info in socket.getaddrinfo(u.hostname, u.port or 443, type=socket.SOCK_STREAM):
            require(ipaddress.ip_address(info[4][0]).is_global, 'Storage endpoints must resolve to public addresses.')
    except OSError:
        raise Problem('The endpoint hostname could not be resolved.')
    return value.rstrip('/')

def parse_e2(text):
    require(isinstance(text, str) and len(text) <= 16384, 'Import a small IDrive E2 access-keys text file.')
    rows = {}
    for line in text.splitlines():
        if ':' in line:
            k, v = line.split(':', 1)
            rows[re.sub(r'[^a-z0-9]', '', k.lower())] = v.strip()
    endpoint = rows.get('endpoint', '').rstrip('/')
    if not endpoint.startswith('https://'):
        endpoint = 'https://' + endpoint
    host = urlsplit(endpoint).hostname or ''
    require(host.endswith('.idrivee2.com') and urlsplit(endpoint).path in ('', '/'), 'The file must contain an IDrive E2 endpoint.')
    out = {'endpoint': endpoint, 'region': rows.get('regioncode', ''), 'access': rows.get('accesskeyid', ''), 'secret': rows.get('secretaccesskey', '')}
    require(all(out.values()), 'The file must contain Endpoint, Region Code, Access key ID and Secret Access Key.')
    return out

def file_kind(path):
    e = PurePosixPath(path).suffix.lower()
    for kind, exts in {'audio': '.mp3 .wav .flac .ogg .m4a', 'video': '.mp4 .mkv .webm .mov', 'images': '.png .jpg .jpeg .svg .gif .webp', 'text': '.txt .md .pdf .docx .csv', 'code': '.py .js .ts .html .css .json .sh .go .rs'}.items():
        if e in exts.split():
            return kind
    return 'other'

def capacity_view(server):
    """Keep physical disk size separate from the maximum managed allocation."""
    physical = server.get('capacity')
    physical = physical if type(physical) is int and physical >= 0 else None
    limit = server.get('limit', 0)
    allocated = min(limit, physical) if limit and physical is not None else (limit or physical)
    return {'physicalCapacity': physical, 'allocationLimit': limit or None, 'allocatedCapacity': allocated,
            'remainingAllocation': max(0, allocated - server.get('used', 0)) if allocated is not None else None}


def visible(user, path, operation='read'):
    rules = [r for r in user.get('rules', []) if not r['path'] or path == r['path'] or path.startswith(r['path'] + '/')]
    if not rules:
        return False
    r = max(rules, key=lambda x: len(x['path']))
    return r['access'] == 'write' or (operation == 'read' and r['access'] == 'read')

class Store:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.directory / 'storage-state.json'
        self.lock = threading.RLock()
        if self.path.exists():
            self.state = json.loads(self.path.read_text())  # fail closed on corruption
        else:
            self.state = {'schema': 1, 'groups': [], 'servers': [], 'users': [], 'enrollments': [], 'jobs': [], 'audit': []}
            self.save()
        # Never automatically resume deletion after a restart.
        for job in self.state['jobs']:
            if job['state'] == 'running':
                job.update(state='interrupted', detail='Service restarted. Inspect source/destination and explicitly retry.')
        self.save()

    def save(self):
        with self.lock:
            temp = self.path.with_suffix('.tmp')
            fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, 'w') as f:
                json.dump(self.state, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp, self.path)
            os.chmod(self.path, 0o600)

    def event(self, action, detail):
        self.state['audit'].insert(0, {'at': int(time.time()), 'action': action, 'detail': str(detail)[:300]})
        self.state['audit'] = self.state['audit'][:500]
        self.save()

    def get(self, collection, id):
        for item in self.state[collection]:
            if item['id'] == id:
                return item
        raise Problem('Item not found.', 404)

    def view(self):
        with self.lock:
            state = copy.deepcopy(self.state)
            state.pop('enrollments')
            state.pop('usedInstallers', None)
            for s in state['servers']:
                s['hasCredentials'] = bool(s.pop('credentials', None))
                s.pop('agentToken', None)
                s.update(capacity_view(s))
                s['online'] = s.get('kind') not in ('linux', 'windows') or time.time() - s.get('lastSeen', 0) < 45
            for u in state['users']:
                u.pop('passwordHash', None)
            return state

    def group(self, body):
        name, sub = label(body.get('name')), subdomain(body.get('sub'))
        use_default = body.get('useDefaultTunnel', True)
        require(type(use_default) is bool, 'Invalid default-tunnel option.')
        base = str(body.get('base') or body.get('domain') or '').strip().lower().rstrip('.')
        # Old nested inputs are ignored in default mode; Burrow is authoritative.
        if not use_default:
            require(bool(re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?', base)), 'Select a configured tunnel domain.')
        else:
            base = ''
        require(not any(g['sub'] == sub and g.get('useDefaultTunnel', True) == use_default and (use_default or g.get('base', g.get('domain', '')) == base) for g in self.state['groups']), 'That group address is already in use.')
        g = {'id': uid(), 'name': name, 'sub': sub, 'domain': base, 'base': base, 'useDefaultTunnel': use_default, 'tunnelSub': '', 'url': '', 'routeState': 'not-published', 'created': int(time.time())}
        self.state['groups'].append(g)
        self.event('Group created', name)
        return g

    def server(self, group_id, body):
        self.get('groups', group_id)
        kind = body.get('kind')
        require(kind in ('e2', 'cloudgate', 'linux', 'windows'), 'Choose IDrive E2, CloudGate, Linux or Windows.')
        s = {'id': uid(), 'group': group_id, 'name': label(body.get('name')), 'kind': kind, 'limit': quota(body.get('limit', 0)), 'used': 0, 'capacity': None, 'verified': False, 'status': 'pending', 'url': '', 'partitions': [], 'inventory': [], 'types': {}, 'lastTest': None, 'error': '', 'readOnly': False}
        if kind == 'e2':
            credentials = parse_e2(body.get('keysFile', ''))
            bucket = body.get('bucket', '')
            require(re.fullmatch(r'[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]', bucket), 'Enter an existing S3 bucket name.')
            credentials.update(bucket=bucket, prefix=clean_path(body.get('prefix', '')))
            s['credentials'] = credentials
        elif kind == 'cloudgate':
            s['credentials'] = {'endpoint': public_https(body.get('endpoint', '')), 'username': label(body.get('username')), 'password': body.get('password', ''), 'category': body.get('category', 'general')}
            require(len(s['credentials']['password']) >= 1, 'Enter your deployed CloudGate client password, not the reauthentication key.')
            require(re.fullmatch(r'[a-z0-9_-]+', s['credentials']['category']), 'Invalid CloudGate category.')
        elif kind == 'linux':
            s['path'] = linux_path(body.get('path', ''))
        else:
            s['path'] = ''  # A local Windows folder is chosen by the native installer.
        self.state['servers'].append(s)
        self.event('Server added', s['name'])
        return s

    def update_inventory(self, s, files, capacity=None, persist=True):
        require(isinstance(files, list) and len(files) <= 100000, 'Inventory is too large.')
        inv, types = [], {k: 0 for k in COLORS}
        for f in files:
            path = clean_path(f['path'], False)
            size = int(f['size'])
            require(size >= 0, 'Invalid file size.')
            inv.append({'path': path, 'size': size})
            types[file_kind(path)] += size
        s.update(inventory=inv, types=types, used=sum(f['size'] for f in inv), capacity=capacity, verified=True, lastTest=int(time.time()), error='')
        if s['status'] not in ('draining', 'removed'):
            s['status'] = 'full' if s['limit'] and s['used'] >= s['limit'] else 'online'
        if persist:
            self.save()

    def check_write(self, s, path, size):
        require(s['status'] not in ('draining', 'removed') and not s.get('readOnly'), 'This server is read-only or draining.', 409)
        require(s['verified'], 'Verify this server first.', 409)
        require(size <= MAX_FILE, 'This release supports files up to 16 MiB.', 413)
        old = next((f['size'] for f in s['inventory'] if f['path'] == path), 0)
        require(not s['limit'] or s['used'] - old + size <= s['limit'], 'Server quota reached.', 507)
        for p in s['partitions']:
            if path == p['path'] or path.startswith(p['path'] + '/'):
                used = sum(f['size'] for f in s['inventory'] if f['path'] == p['path'] or f['path'].startswith(p['path'] + '/'))
                require(not p['limit'] or used - old + size <= p['limit'], 'Partition quota reached.', 507)

    def user(self, group, body):
        self.get('groups', group)
        username = body.get('username', '')
        require(isinstance(username, str) and re.fullmatch(r'[a-zA-Z0-9_.@-]{2,64}', username), 'Username must be 2–64 letters, digits, dots, dashes, @ or underscores.')
        if body.get('id'):
            existing = self.get('users', body['id'])
            require(existing['group'] == group, 'User does not belong to this group.', 403)
            require(not any(u['group'] == group and u['username'] == username and u['id'] != existing['id'] for u in self.state['users']), 'That username is already in use in this group.')
        else:
            existing = next((u for u in self.state['users'] if u['group'] == group and u['username'] == username), None)
        rules = body.get('rules', [])
        require(isinstance(rules, list) and 1 <= len(rules) <= 100, 'Add between 1 and 100 path rules.')
        rules = [{'path': clean_path(r.get('path', '')), 'access': r.get('access')} for r in rules]
        require(all(r['access'] in ('none', 'read', 'write') for r in rules), 'Invalid access level.')
        require(len(set(r['path'] for r in rules)) == len(rules), 'Remove duplicate paths.')
        u = existing or {'id': uid(), 'group': group, 'username': username}
        if body.get('password'):
            u['passwordHash'] = password_hash(body['password'])
        require(u.get('passwordHash'), 'A password is required for a new user.')
        u.update(username=username, rules=rules, enabled=body.get('enabled', True) is True)
        if not existing:
            self.state['users'].append(u)
        self.event('User access updated', username)
        return {'id': u['id']}
