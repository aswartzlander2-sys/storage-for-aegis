#!/usr/bin/env bash
# action "Restart".
set -euo pipefail
. "$(dirname "$0")/lib.sh"
. "$(dirname "$0")/safety.sh"
case "$(conf linked)" in True|true) echo "This copy is linked: restart it from the Weft host that runs it."; exit 1 ;; esac
service_start
wait_up && echo "restarted: $(url)" || { echo "it did not come back; see $LOG"; exit 1; }
