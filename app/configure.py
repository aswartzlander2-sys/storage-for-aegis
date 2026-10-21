"""Private runtime configuration. Never put deployment credentials in the addon."""
import json
import os
from pathlib import Path
import secrets
import sys
sys.dont_write_bytecode = True
from core import password_hash, require
p = Path(sys.argv[1])
c = json.loads(p.read_text())
c.setdefault('admin_key', secrets.token_urlsafe(48))
password = c.pop('admin_password', '')
if password:
    c['admin_password_hash'] = password_hash(password)
# The extension now owns agent-enrollment.json; the old manual setting is obsolete.
c.pop('public_url', None)
temp = p.with_suffix('.private.tmp')
fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, 'w') as f:
    json.dump(c, f, indent=2)
os.replace(temp, p)
os.chmod(p, 0o600)
