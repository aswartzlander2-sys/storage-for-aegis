# Robo Storage for Aegis 1.0.0 — validation report

Date: **2026-10-21**. This release was exercised through **actual public Burrow/Cloudflare HTTPS tunnels**, not just a localhost TLS simulation. It is not a claim that every provider, host configuration or failure mode has been certified.

## Release changes

1. **A server inherits its group address.** The Add Server modal no longer contains domain, subdomain or tunneling fields. Group links open the multi-server browser; server links use `<group URL>/s/<server-id>/`. Server-scoped URLs cannot select another server. No per-server tunnel is created.
2. **Use default Burrow tunnel** is checked below the group address. It uses Burrow’s existing linked domain and active naming base automatically, or the host’s default temporary HTTPS tunnel when no domain is linked. Stale legacy root/nested-domain inputs are ignored in default mode. There is no manual nested-base equality error in this path.
3. Unchecking the box offers only configured bases/aliases from Burrow’s actual naming and tunnel metadata. A selected extra zone is enabled only on the addon-owned group tunnel. The addon does not change global DNS/naming or invent certificate coverage.
4. Group status is refreshed as asynchronous public URLs arrive. Proposed addresses are kept separate from verified URLs. Ready status requires a normal certificate-validated HTTPS identity/nonce check for the correct group.
5. Existing groups, users and storage data remain in `ADDON_DATA`. Legacy independent server tunnels are left owned and recorded until uninstall, rather than silently deleting old public links. Newly launched server links use the group route.

## Summary

| Check | Observed result |
|---|---|
| Normative Weft publish checker | Zero errors |
| Python regressions | **69 passed** |
| Node extension regressions | **7 passed, 0 failed** |
| Real Weft Burrow lifecycle | Passed, including install/status/update/status/uninstall |
| Actual Aegis 2.24.2 install/update/uninstall | **DONE** |
| Default checkbox / inherited-domain UI | Passed, desktop and mobile |
| Actual signed-in Linux setup UI through public HTTPS | Passed |
| Real public Cloudflare enrollment, two Linux workers | Passed |
| Shared group tunnel and `/s/ID/` links | Passed; no per-server tunnel |
| Public Basic login, upload/download checksum, ACLs and quotas | Passed |
| Public-worker migration and explicit erasure | Passed |
| Real E2/CloudGate accounts | **Not tested**; uploaded credentials not used |
| Custom-domain DNS/TLS, independent remote-machine deployment, reboot/systemd | **Not tested** |

## Real host and public-network environment

- Actual upstream **Aegis × Burrow 2.24.2**, commit `3f48e0dbeda3628c33e3c005a9fe19b04816f3bc`.
- Actual `cloudflared 2026.10.3` installed only into the disposable test host’s private `bin/`. It is **not bundled** in the addon or installed globally.
- The host’s **real QuickTunnels implementation** created `*.trycloudflare.com` addresses. The extension did not substitute a fake tunnel adapter for this acceptance run.
- The host was run with `TUNNEL_TRANSPORT_PROTOCOL=http2` for this sandbox network. No TLS verification was disabled. This is test-host configuration, not a change imposed by the addon on users’ hosts.
- The actual host extension context and real mode-600 Unix control socket were used. The Aegis gate was authenticated; the host’s shield was disabled for the disposable test fixture only.
- Workers ran in dedicated local disposable directories, but **all enrollment/callback traffic and public file requests traversed the real public HTTPS tunnel**. This does not substitute for a test from a separate physical machine or another network.

### Commands actually run

```text
ROBO_KEEP_HOST_INSTALLED=1 python tests/host_refresh.py http://127.0.0.1:4310 /home/user/live-host-test
python tests/live_acceptance.py http://127.0.0.1:4310 /home/user/live-host-test/browser-session.json /home/user/live-host-test/storage-final
```

`host-1.0.0.log` records real host installation, mount/auth/CSS/file-browser checks and an update preserving the same enrollment tunnel identity and group data. Its provider/public-transfer disclaimer applies to that host-smoke script alone; the separate full public test below was then run.

### Final actual public acceptance output

Exact output is saved in `live-public-1.0.0.log`:

```text
REAL PUBLIC HTTPS: Burrow-created Cloudflare enrollment route returned app identity + nonce, certificate verification enabled
Live source: generated curl executed over real public HTTPS; write/read/delete storage probe completed
Actual signed-in UI: Add Server → Linux → generated public curl → live Verified → Verify & Launch succeeded, with no domain fields
Live destination: generated curl executed over real public HTTPS; write/read/delete storage probe completed
Two actual workers became Verified only after authenticated public HTTPS heartbeats
Default tunnel: stale nested domain ignored; one group tunnel added, shared agent tunnel, no per-server tunnels; both servers inherit group /s/ID/ addresses
Public group: anonymous request gets native HTTP Basic challenge; administration is not exposed
Actual public group and inherited per-server file-browser URLs returned 200 after Basic login
Actual public upload/download checksum matched; hidden/read-only ACLs and server/partition quotas enforced; encoded directory path works
Public HTTPS browser smoke: PASS; JavaScript errors: []
Actual public worker migration: copy → read-back checksum → source-change check → source deletion → disconnect: PASS
Actual public worker erasure and empty-inventory disconnect: PASS
Real IDrive E2/CloudGate accounts and custom-domain DNS: NOT TESTED; no supplied provider credentials used
Live group cleanup removed only its owned tunnel; enrollment and other groups unchanged
LIVE PUBLIC ACCEPTANCE: PASS
```

The test deliberately supplied a stale nested domain on group creation and wrong server-level address values at launch. Default mode ignored them and inherited the correct group route. The first worker was created through the **actual browser wizard**, its displayed command was executed, its live Verified state appeared, and its Verify & Launch button succeeded.

The public client verified native Basic authentication, both inherited server URLs, server-selector scoping/cross-server rejection, public upload/download including an encoded directory path, file checksums, hidden/read-only rules, server and partition quotas, migration and confirmed erasure. The public browser loaded the actual file browser without JavaScript errors.

**Observed network failure, not hidden:** an earlier extended UI run hit a transient public GET failure (`Network is unreachable`) after the wizard had succeeded. That failed output is retained in `live-network-retry-1.0.0.log`. The final complete run above passed. The test client permits bounded retries for read-only transport failures; it never automatically replays writes with unknown outcomes. This is not an internet-outage/endurance certification.

### Cleanup observed

The test host’s actual uninstall job completed. `host-uninstall-1.0.0.log` records:

```text
Actual Aegis 2.24.2 uninstall: DONE
All addon-owned agent and group tunnels removed; no automatic recreation
Other host services remain running; host health: 200
```

The disposable Aegis process was then stopped. Completed workers exited after disconnection; workers from the interrupted fixture were explicitly stopped only after their executable/config paths were verified to be inside the disposable test directory. No customer filesystem or provider account was used. Test certificates, host binaries, private runtime state and browser sessions are excluded from the archive. The separately labeled demo remains available.

## Automated regressions

### Python — 69 passed

```text
python -m unittest discover -s tests -p 'test_*.py' -v
Ran 69 tests
OK
```

Full output: `python-1.0.0.log`. Includes core persistence/secrets/path confinement, ACL/passwords, quotas/nested budgets, worker I/O and endpoint/signing tests; enrollment origin/TTL and URL pinning; read-only group snapshot overlays; stale/corrupt readiness; default/legacy/custom routing; and actual HTTP plus Unix control-socket launch calls. Verified server launches ignore injected server-level domains and publish the group, not the server.

### Extension — 7 passed

```text
node --test tests/test_extension.mjs
# tests 7
# pass 7
# fail 0
```

Full output: `extension-1.0.0.log`. These regressions use supported-context fixtures and real local HTTP/Unix listeners, with external HTTPS mocked **in this suite only**. They cover restricted agent proxies, spoofed-header/traversal/absolute-URL rejection, encoded file-path queries, fresh non-sliding probes, URL assignment after creation, default mode ignoring old nested values, no-domain mode, correct group identity, concurrent launches without duplicate tunnels, disabling/cleanup, and configured extra wildcard alias selection without changing global naming.

The real public acceptance above is separate and does not mock HTTPS or the tunnel context.

### Lifecycle and UI

```text
python tests/lifecycle_acceptance.py /home/user/weft-reference
Lifecycle/linking/idempotence/ownership acceptance: passed

python tests/ui_smoke.py
Browser page errors: []
```

Full outputs: `lifecycle-1.0.0.log`, `ui-1.0.0.log`. Lifecycle executes real install/status/update/status/uninstall, repeated install, read-only detection, retained data, linked-copy safety, foreign-port refusal and stale-PID safety. The sandbox uses background-service mode; actual systemd behavior is not certified.

Chromium covered the default checked checkbox below the address, inherited/disabled domain field, explicit custom-mode toggle, absence of all server address fields, synthetic E2 file gating, Linux command/verification gating, group partitions, 100% redistribution boundaries, move/erase confirmation dialogs and mobile overflow at 390px. Screenshots show either the clearly marked demo or the explicitly disposable live fixture:

- `default-group-1.0.0.png`, `dashboard.png`, `mobile.png`, `linux-setup.png`, `group-settings.png`: labeled demo.
- `actual-host-dashboard.png`, `actual-host-connections.png`, `files-browser.png`: local actual host.
- `live-ui-server-1.0.0.png`, `live-public-browser.png`: actual live/public test flow.

## Static, attribution and packaging

The manifest uses spec 1, the unchanged published addon ID and Burrow-only platform requirement `>=2.24.2`. Final exact checker output is in `check-1.0.0.txt`.

- The original addon was copied from hello-weft. Normative `SPEC.md`, every skeleton file, the closest references and shared helpers were reviewed; this update re-inspected actual routing, naming, QuickTunnels and UI implementations.
- `weft/lib.sh` and `weft/mesh.py` remain byte-identical to Weft reference commit `f4f14b14bf3dabbbddfee2834bd9f46ee1315452`.
- `app/static/aegis.css` remains byte-identical to upstream Aegis `public/ui.css`. Complete MIT notices remain in `LICENSE` and `AEGIS-LICENSE.txt`; `THIRD-PARTY.md` identifies copied material.
- Python/JavaScript/shell syntax, mandatory ending README Credits, path confinement, supplied-key absence and ZIP integrity are checked before packaging.
- Historical `TEST-REPORT-0.1.0.md` and `TEST-REPORT-0.1.1.md` retain prior results and limitations; they do not override this release’s public-network evidence.

## Remaining limits

- No real E2 or CloudGate provider acceptance; no use of the user’s uploaded credentials.
- No live custom-domain/extra-wildcard certificate test. Those mappings are covered by supported-context regressions, not a real account/zone.
- Temporary Quick Tunnel addresses can change; workers must be re-enrolled if their callback address changes. Stable linked domains are recommended for long-lived storage.
- 16 MiB/file remains the gateway limit. Quotas are logical gateway budgets, not reserved disks; direct external changes are discovered by scanning, not prevented by this gateway.
- Whole-file weighted migration, private mode-600 secrets not encrypted at rest, and detached Linux workers without automatic reboot persistence remain documented behavior.
- No independent-machine, reboot, systemd or extended network/provider outage acceptance. Back up important data and finish provider-specific acceptance before relying on those integrations.
