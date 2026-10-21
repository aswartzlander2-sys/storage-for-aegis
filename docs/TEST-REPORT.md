# Robo Storage for Aegis 1.0.1 — correction validation

Date: **2026-10-21**. This report distinguishes successful checks from interrupted public-network runs. Historical 1.0.0 evidence is retained in `TEST-REPORT-1.0.0.md`; its complete public migration/erase pass is **not** claimed as a new full 1.0.1 pass.

## Corrections

### Unchecked means the root directly

- Checked: inherit existing Burrow naming, for example `studio.apps.example.com`, or the host's automatic Quick Tunnel when no domain is linked.
- Unchecked: request exactly `studio.example.com`. The UI offers root zones, not naming/wildcard prefixes. An unsupported root request fails before creating/changing tunnels; no prefixed or temporary fallback is selected and no global naming changes are made.
- Supported-context tests cover rejection on a prefixed-only host with no tunnel side effects; a host whose primary base really is the root; and an extra configured root alias without altering the primary/global naming. The selected URL must be exactly the requested root URL and pass the normal HTTPS identity/nonce check.
- Legacy unchecked/prefixed snapshots are blocked immediately, including before the extension refreshes. A root readiness marker and exact address match are required. Blocking a saved URL in the dashboard does not silently delete its existing tunnel resources.
- **Aegis 2.24.2 limitation:** when its primary naming prefix is active, the supported tunnel API has no per-tunnel override to publish directly under that primary root. Such a request is explicitly unavailable. The addon does not patch the host, scrape credentials, take over other routes, or change global naming. No real custom-domain account/DNS/TLS acceptance was performed.

### 1 GB is not the whole disk

- Root cause of lost edits: an existing draft ID caused `ensureServer()` to return without saving settings. Generating the enrollment command creates the draft; subsequent quota/name edits therefore used to be lost at Launch. Existing drafts now save the edited name and quota before testing/publishing.
- Physical capacity remains inventory metadata. `allocationLimit`, `physicalCapacity`, `allocatedCapacity` and `remainingAllocation` are separately projected by the administrator and public file-list APIs. Effective contribution is the lesser of configured quota and known physical capacity. No configured quota means the known physical capacity, or unknown if neither is known.
- Group totals, contribution widths, server bars and file-browser usage use effective allocation, not full disk size. The detail view separately labels physical capacity and configured ceiling.
- A configured 1 GB ceiling means **1,000,000,000 bytes**, enforced on writes through Robo Storage. It is a logical budget, not a physical reservation or control over direct filesystem writes.
- A previously lost quota cannot be reconstructed: existing affected installations must explicitly save their intended ceiling in server Settings and run Test after updating.

## Results

| Check | Observed result / evidence |
|---|---|
| Weft normative `--publish` checker | **Zero errors**, `check-1.0.1.txt` |
| Python regressions | **74 passed**, `python-1.0.1.log` |
| Node extension regressions | **9 passed, 0 failed**, `extension-1.0.1.log` |
| Real Weft lifecycle | **Passed**, `lifecycle-1.0.1.log` |
| Browser smoke, desktop/mobile, checkbox root-only choices | **Passed**, JavaScript errors `[]`, `ui-1.0.1.log` |
| Synthetic 512 GB disk / 1 GB UI contribution | **Passed**, `ui-quota-1.0.1.log`, `quota-regression-1.0.1.png` |
| Actual Aegis 2.24.2 install/update, mount/auth/CSS, route ownership | **Passed**, `host-1.0.1.log` |
| Final-source actual host restart retains edited quota/name/capacity | **Passed**, `host-final-update-1.0.1.log` |
| Actual signed-in UI: generate unlimited command, edit to 1 GB, verify and Launch | **Passed** in public-network runs; persisted limit and visible server card both 1 GB |
| Actual public 1 GB boundary: scanned 999,999,999 bytes; write two bytes | **HTTP 507 observed**, `live-network-write-timeout-1.0.1.log` |
| Complete 1.0.1 public migration/erase rerun | **Not completed**; interrupted by public-network failures, described below |
| Real E2/CloudGate/custom-domain provider accounts | **Not tested**; supplied credentials unused |

The Python regressions specifically cover 512,000,000,000-byte physical capacity with a 1,000,000,000-byte allocation, inventory refresh and restart preservation, the precise ceiling boundary, smaller physical disks, unknown capacity, legacy root snapshots and malformed root-route shapes. Existing permission, migration, quota, confinement and enrollment tests remain included.

The synthetic browser regression intercepts only the demo's read-only state response. It does **not** claim a real 512 GB disk: it verifies total/group/server contribution of 1.0 GB, 250 MB usage as 25%, and a separately labeled physical 512.0 GB value. The real public tests use the sandbox's actual disk capacity, which is greater than the allocated 1 GB.

Lifecycle acceptance executes real install/status/update/status/uninstall, repeated install, read-only detection, data retention, linked-copy safety, foreign-port refusal and stale-PID handling. The actual host was separately installed and updated through authenticated Aegis API jobs, not a context mock. The final host restart retained every saved quota and edited name.

## Public-network run history — deliberately not summarized as a full pass

Tests use real Aegis 2.24.2, Burrow Quick Tunnels and Cloudflare `cloudflared` 2026.10.3 with HTTP/2. Normal public certificate validation remains enabled. No provider secrets were used. Disposable storage is confined under `/home/user/live-host-test/`.

1. `live-network-initial-1.0.1.log`: enrollment identity check succeeded, but the installer GET then failed to connect. No installer write was replayed.
2. `live-network-write-timeout-1.0.1.log`: two Linux workers enrolled over public HTTPS and heartbeated. The actual UI generated the source command with no quota, then changed the name and quota to 1 GB before Launch. Stored allocation remained exactly 1 GB, independent of physical disk size. Group/server links, Basic challenge and scoped selector checks passed. A sparse test fixture produced **999,999,999 inventory bytes**, and a two-byte public upload returned **507**. The sparse file was removed in `finally` and inventory refreshed. A later partition-quota request timed out; its write was **not retried**.
3. `live-ui-selector-1.0.1.log`: a new UI assertion matched two identically named fixtures left by earlier runs. This was a test-selector ambiguity, not a capacity mismatch; both returned matching 1 GB text. The selector was corrected to scope to the exact group ID.
4. `live-network-final-1.0.1.log`: the corrected, group-scoped UI assertion passed; edited settings, real enrollment, inherited routes, public Basic access and selector isolation passed again. The next public write failed with network unreachable. This interrupted run is **not** a complete acceptance pass. Its sparse fixture was again removed in `finally`.

Uncertain write outcomes were never automatically replayed. Interrupted workers are stopped only after their `/proc` command lines identify this exact disposable test root. Final actual-host uninstall and owned-route cleanup are recorded separately in `host-uninstall-1.0.1.log`.

## References, packaging and remaining limits

- The original implementation copied hello-weft and reviewed normative SPEC, every skeleton file, closest references and helpers. References remain Weft commit `f4f14b14bf3dabbbddfee2834bd9f46ee1315452` and Aegis 2.24.2 commit `3f48e0dbeda3628c33e3c005a9fe19b04816f3bc`.
- Vendored `weft/lib.sh` and `weft/mesh.py` remain byte-identical; `app/static/aegis.css` remains byte-identical to Aegis `public/ui.css`. Licenses and the required ending README Credits remain preserved.
- Packaging excludes private runtime/browser state, caches, symlinks and the user's uploads. Python/JavaScript/shell syntax, helper/CSS identity and ZIP integrity are checked separately.
- Temporary tunnel addresses can change and require re-enrollment. Detached Linux workers do not automatically survive reboot. Systemd/reboot, independent-machine, endurance and real-provider/custom-domain acceptance remain untested.
- Limits remain 16 MiB per file and 100,000 inventory files. Logical quotas cannot prevent direct external writes. Whole-file weighted migration, private mode-600 but unencrypted-at-rest secrets, and retention of the source until successful verified copy are unchanged.
