#!/usr/bin/env bash
# Sourced after lib.sh by mutating lifecycle scripts only.
set -euo pipefail
# Additional Robo Storage behavior; the vendored Weft helpers stay unchanged.
# Never signal a stale/reused PID that no longer identifies this service.
eval "$(declare -f service_stop | sed '1s/service_stop/weft_base_service_stop/')"
service_stop() {
  if [ -f "$PIDF" ]; then
    if ! python3 - "$PIDF" "$DIR/app/server.py" "$CONF" <<'PY'
import os, pathlib, sys
try:
    pid = int(pathlib.Path(sys.argv[1]).read_text().strip())
    if pid <= 1:
        raise ValueError('invalid pid')
    args = pathlib.Path('/proc/%d/cmdline' % pid).read_bytes().split(b'\0')
    wanted = [os.fsencode(sys.argv[2]), os.fsencode(sys.argv[3])]
    if not all(a in args for a in wanted):
        raise ValueError('another process')
except (OSError, ValueError):
    sys.exit(1)
PY
    then
      echo "::warn Stale service PID was ignored; no unrelated process was signalled."
      rm -f "$PIDF"
    fi
  fi
  weft_base_service_stop
}
