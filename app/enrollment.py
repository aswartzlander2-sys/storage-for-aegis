"""The Burrow extension owns this descriptor. The app never guesses a public URL."""
import json
import math
import time
from pathlib import Path
from urllib.parse import urlsplit

def route_status(directory, now=None):
    now = time.time() if now is None else now
    fallback = {'state': 'pending', 'url': '', 'detail': 'Burrow is preparing a dedicated HTTPS enrollment route automatically. Try again in a moment.', 'updated': 0}
    try:
        data = json.loads((Path(directory) / 'agent-enrollment.json').read_text())
        if not isinstance(data, dict):
            return fallback
        state = data.get('state')
        url = str(data.get('url') or '')
        if state == 'ready':
            parsed = urlsplit(url)
            if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/') or (parsed.port is not None and not 1 <= parsed.port <= 65535):
                return {**fallback, 'detail': 'Burrow has not supplied a valid HTTPS enrollment address yet.'}
            stamps = [float(data.get(k, 0)) for k in ('checkedAt', 'updated')]
            if any(not math.isfinite(t) or not -30 <= now - t <= 90 for t in stamps):
                return {**fallback, 'detail': 'Waiting for Burrow to recheck the enrollment route. No manual URL configuration is needed.'}
            return {**fallback, **data, 'url': url.rstrip('/')}
        return {**fallback, **data, 'state': state if state in ('pending', 'error') else 'pending', 'url': ''}
    except (OSError, ValueError, TypeError):
        return fallback
