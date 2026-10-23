#!/usr/bin/env python3
"""Robo Cloud Linux worker: outbound HTTPS only; no listening port or root required.
All storage I/O uses no-follow directory descriptors beneath the selected root.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
sys.dont_write_bytecode = True
import time
import urllib.request
import urllib.error

MAX_FILE = 16 * 1024 * 1024

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None

OPENER = urllib.request.build_opener(NoRedirect)

def call(cfg, path, body, token=None):
    req = urllib.request.Request(cfg['url'] + path, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + (token or cfg.get('token', ''))}, method='POST')
    with OPENER.open(req, timeout=80) as r:
        return json.loads(r.read(48 * 1024 * 1024))

def write_private(path, value):
    tmp = str(path) + '.tmp'
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(value, f)
    os.replace(tmp, path)

def parts(path):
    p = path.split('/')
    if not path or path.startswith('/') or '\\' in path or '\x00' in path or any(x in ('', '.', '..', '.robo-agent') for x in p):
        raise ValueError('Unsafe file path')
    return p

def parent(rootfd, path, create=False):
    p = parts(path)
    fd = os.dup(rootfd)
    try:
        for item in p[:-1]:
            if create:
                try:
                    os.mkdir(item, 0o700, dir_fd=fd)
                except FileExistsError:
                    pass
            nextfd = os.open(item, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = nextfd
        return fd, p[-1]
    except Exception:
        os.close(fd)
        raise

def scan(root):
    out = []
    # fwalk does not follow symlinks; stat/open use the yielded directory fd.
    for path, dirs, files, fd in os.fwalk(root, follow_symlinks=False):
        dirs[:] = [d for d in dirs if d != '.robo-agent' and not os.path.islink(os.path.join(path, d))]
        for name in files:
            stat = os.stat(name, dir_fd=fd, follow_symlinks=False)
            import stat as statlib
            if not statlib.S_ISREG(stat.st_mode):
                continue
            rel = os.path.relpath(os.path.join(path, name), root)
            parts(rel)
            out.append({'path': rel, 'size': stat.st_size})
            if len(out) > 100000:
                raise ValueError('Inventory exceeds 100,000 files')
    space = shutil.disk_usage(root)
    return {'files': out, 'capacity': space.total, 'free': space.free}

def execute(root, task):
    op = task['op']
    if op == 'scan':
        return scan(root)
    rootfd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    fd = None
    try:
        fd, name = parent(rootfd, task['path'], create=op == 'write')
        if op == 'read':
            f = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
            with os.fdopen(f, 'rb') as stream:
                data = stream.read(MAX_FILE + 1)
            if len(data) > MAX_FILE:
                raise ValueError('File exceeds 16 MiB')
            return {'data': base64.b64encode(data).decode()}
        if op == 'write':
            data = base64.b64decode(task['data'], validate=True)
            if len(data) > MAX_FILE:
                raise ValueError('File exceeds 16 MiB')
            if shutil.disk_usage(root).free < len(data) + 1024 * 1024:
                raise ValueError('Insufficient disk space')
            temp = '.robo-upload-' + secrets.token_hex(12)
            f = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
            try:
                with os.fdopen(f, 'wb') as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.rename(temp, name, src_dir_fd=fd, dst_dir_fd=fd)
            finally:
                try:
                    os.unlink(temp, dir_fd=fd)
                except FileNotFoundError:
                    pass
            return {'ok': True}
        if op == 'delete':
            # Removing a symlink removes only the link, never its target.
            os.unlink(name, dir_fd=fd)
            return {'ok': True}
        raise ValueError('Unsupported operation')
    finally:
        if fd is not None:
            os.close(fd)
        os.close(rootfd)

def run(config):
    cfg = json.loads(Path(config).read_text())
    root = cfg['root']
    while True:
        try:
            task = call(cfg, '/agent/poll', {}) .get('task')
            if task:
                try:
                    result = execute(root, task)
                except Exception as ex:
                    result = {'error': type(ex).__name__ + ': storage operation failed; inspect agent host.'}
                call(cfg, '/agent/result', {'task': task['id'], 'result': result})
            else:
                time.sleep(2)
        except urllib.error.HTTPError as ex:
            if ex.code in (401, 403, 410):
                print('Agent authorization revoked; stopping.', flush=True)
                return
            time.sleep(5)
        except Exception:
            time.sleep(5)

DEVELOPER = "Robo Universal"

def bootstrap(encoded):
    print("Robo Cloud Enrollment — developer: " + DEVELOPER, flush=True)
    print("Signing status: unsigned HTTPS enrollment. Developer branding is not a verified signature.", flush=True)
    cfg = json.loads(base64.urlsafe_b64decode(encoded))
    if not cfg['url'].startswith('https://'):
        raise ValueError('Enrollment requires HTTPS')
    root = Path(os.path.expanduser(cfg['root']))
    # Do not accept symlink roots or parent components.
    absolute = root.absolute()
    if any(p.is_symlink() for p in [absolute, *absolute.parents]):
        raise ValueError('Storage path must not contain symlinks')
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root = root.resolve()
    probe = root / ('.robo-probe-' + secrets.token_hex(10))
    try:
        fd = os.open(probe, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as f:
            f.write(b'Robo Cloud probe')
            f.flush()
            os.fsync(f.fileno())
        if probe.read_bytes() != b'Robo Cloud probe':
            raise ValueError('Storage probe failed')
    finally:
        probe.unlink(missing_ok=True)
    info = scan(str(root))
    info.update(root=str(root), hostname=os.uname().nodename)
    result = call(cfg, '/agent/enroll', info, cfg['enrollment'])
    cfg.update(root=str(root), token=result['token'])
    cfg.pop('enrollment')
    agentdir = root / '.robo-agent'
    agentdir.mkdir(exist_ok=True, mode=0o700)
    if agentdir.is_symlink():
        raise ValueError('Agent directory cannot be a symlink')
    os.chmod(agentdir, 0o700)
    script = agentdir / 'agent.py'
    if script.is_symlink():
        raise ValueError('Agent script cannot be a symlink')
    fd = os.open(script, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as f:
        f.write(Path(__file__).read_text())
    config = agentdir / 'config.json'
    write_private(config, cfg)
    pidfile = agentdir / 'agent.pid'
    # Re-enrollment rotates the token: the previous worker exits on its next poll.
    with open(agentdir / 'agent.log', 'ab') as log:
        process = subprocess.Popen([sys.executable, str(script), 'run', str(config)], stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    pidfile.write_text(str(process.pid))
    print('Storage probe succeeded. Agent started for ' + str(root))
    print('No listening port was opened. Keep this process running; repeat enrollment after reboot.')
    print('To stop: kill "$(cat ' + str(pidfile) + ')". Never delete the storage directory to uninstall the agent.')

if __name__ == '__main__':
    if sys.argv[1] == 'bootstrap':
        bootstrap(sys.argv[2])
    else:
        run(sys.argv[2])
