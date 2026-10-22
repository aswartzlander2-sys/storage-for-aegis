#!/usr/bin/env bash
# Derived from Weft's hello-weft skeleton; linked copies stay untouched.
set -euo pipefail
. "$(dirname "$0")/lib.sh"
. "$(dirname "$0")/safety.sh"
case "$(conf linked 2>/dev/null)" in
  True|true) echo "it was linked: the host that owns it keeps running it"; exit 0 ;;
esac
if [ -f "$DATA/burrow-routes.json" ]; then
  # Fail rather than silently leave public tunnels behind when Burrow is down.
  python3 "$DIR/app/cleanup.py" "$CONF"
fi
service_remove
mesh_withdraw
echo "stopped and removed Robo Cloud; remote files and agents were left intact"
