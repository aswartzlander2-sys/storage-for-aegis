#!/usr/bin/env bash
# status: one JSON line, quickly: {"state", "url", "port", "version", "detail"}.
set -u
. "$(dirname "$0")/lib.sh"
[ -f "$CONF" ] || { echo '{"state":"error","detail":"no settings: install it again"}'; exit 0; }
how="its own service"; case "$(conf linked)" in True|true) how="run by another Weft host" ;; esac
if healthy; then status_line running "on port $(conf port), $how"; else status_line stopped "not answering on port $(conf port) ($how)"; fi
