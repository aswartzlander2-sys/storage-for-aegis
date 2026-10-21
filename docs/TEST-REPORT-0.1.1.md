# Validation report — Robo Storage for Aegis 0.1.1

Date: 2026-10-21. **Development preview, not production-certified.** This report covers the automatic-enrollment and Aegis-design correction. Historical 0.1.0 results are retained separately in `TEST-REPORT-0.1.0.md`; they are not substituted for the tests below.

## Changes verified

- The manifest no longer asks for an agent enrollment base URL. Legacy manual values are removed from app configuration and cannot authorize command generation.
- Burrow automatically owns one dedicated agent tunnel and a restricted loopback proxy. Only `/agent/*` and `/enroll.sh` are exposed through that proxy. The administration mount remains behind Aegis authentication.
- Readiness requires HTTPS, normal certificate validation, no redirects, the addon identity and a fresh random nonce echoed by the application. Proposed addresses are not treated as ready. Errors/pending states retry; failed DNS publishing is retried through the owned route. Commands pin their verified base URL. Descriptor state is read afresh and expires after 90 seconds without a recent check.
- Updates reconnect the proxy target without duplicating the persisted tunnel identity. Uninstall disables automatic provisioning before removing owned routes.
- `app/static/aegis.css` is byte-identical to Aegis 2.24.2's `public/ui.css`. The actual shared black/grid background, neutral raised surfaces and white buttons are used. The former sidebar is gone; host-style top navigation and horizontal storage tabs replace it. Dialogs and the file browser use the same stylesheet.

## References and licenses

The normative Weft SPEC, hello-weft skeleton, helpers and closest examples were read during the original implementation. This update re-inspected the actual Aegis UI and extension/tunnel implementations. References remain:

- Weft: `f4f14b14bf3dabbbddfee2834bd9f46ee1315452`.
- Aegis × Burrow **2.24.2**: `3f48e0dbeda3628c33e3c005a9fe19b04816f3bc`.
- CloudGate: `74e7606bed9ecf04e5b2586c8f41d01c6b7c9b17`.
- Bulwark: `8530061c77ec69abb09825bc64de0da2d938f496`.

Vendored `weft/lib.sh` and `weft/mesh.py` remain byte-identical. The upstream Weft MIT notice is in `LICENSE`; Aegis's complete MIT notice is in `AEGIS-LICENSE.txt`. See `../THIRD-PARTY.md`.

## Static checks

Run from the Weft checkout:

```text
node tools/weft-check.mjs /home/user/robo-storage-aegis --publish
✔ /home/user/robo-storage-aegis
    robo-storage-aegis 0.1.1: Robo Storage for Aegis · platforms burrow
    update card: gray, glow, 3 highlights (preview: node tools/weft-card.mjs /home/user/robo-storage-aegis)
```

Zero checker errors. Exact output is saved in `check-refresh.txt`. Python compilation, JavaScript parsing, shell syntax, helper/stylesheet equality, README credits, archive integrity and uploaded-key absence are checked separately before packaging. No sample deployment credentials are used.

## Python regressions — 53 passed

```text
python3 -m unittest discover -s tests -p 'test_*.py' -v
Ran 53 tests
OK
```

Full observed output: `python-refresh.log`. Includes the original 44 core tests plus descriptor origin/TTL/corruption checks, an actual temporary HTTP service, blocked insecure/unready/legacy enrollment, verified command URL selection, pinning across route changes, public identity probes, direct-admin denial and exact upstream stylesheet serving.

## Extension regressions — 3 passed

```text
node --test tests/test_extension.mjs
# tests 3
# pass 3
# fail 0
```

Full observed output: `extension-refresh.log`. Uses supported Burrow context fixtures, real local HTTP proxy listeners and a real test Unix HTTP socket. External HTTPS is mocked **in this test suite only**. Checks identity/nonce readiness, non-sliding probe caching, pending/error recovery, HTTP/DNS-pending refusal, restricted public paths, absolute-URL/traversal rejection, stripped spoofed admin/session headers, preserved Basic credentials and encoded file-path queries, group/agent record coexistence, restoration and owned cleanup without re-creation.

## Full Weft lifecycle — passed

```text
python3 tests/lifecycle_acceptance.py /home/user/weft-reference
Lifecycle/linking/idempotence/ownership acceptance: passed
```

Full exact output: `lifecycle-refresh.log`. Executes real `weft-run` install/status/update/status/uninstall on Burrow, a second idempotent install, a read-only detect check, a retained-data sentinel, linked-copy behavior, refusal to seize a foreign port and stale-PID safety. Systemd was intentionally disabled for this sandbox fixture; actual systemd operation remains untested.

## Real Aegis host — passed locally

An isolated **actual Aegis × Burrow 2.24.2 server**, not a replacement/mock host, accepted the local addon and ran its real extension, Unix control socket and lifecycle jobs. No domain/account was configured on this disposable host.

```text
python3 tests/host_refresh.py http://127.0.0.1:4310 /home/user/host-test-data
```

Full observed output: `host-refresh.log`. The run observed:

- Actual host install, update and uninstall jobs: **DONE**.
- Installed settings do not include a URL setting.
- The real Burrow tunnel registry automatically received exactly one addon-owned agent route, without supplying a manual tunnel or enrollment URL.
- Mounted dashboard and exact upstream CSS: HTTP 200; computed background `rgb(3, 3, 4)` and primary buttons `rgb(241, 242, 243)`; top navigation and no sidebar.
- The actual restricted proxy reaches `/agent/health`, but returns 404 for dashboard/admin paths. Direct service administration without credentials returns 401.
- Native Basic-auth file browser, Aegis styles, server selector and mobile width checked.
- Host update preserved the group and the same agent tunnel identity, without a duplicate. Uninstall removed the owned automatic route.
- Browser page errors: `[]`.

**Public HTTPS was not available for the agent route on this sandbox host.** The app correctly returned **503 with automatic-provisioning status and no command**, rather than inventing a URL or asking for a manual setting. This is evidence of actual-host provisioning/ownership and safe pending behavior, **not** successful public DNS/TLS acceptance.

Screenshots: `actual-host-dashboard.png`, `actual-host-connections.png`, `files-browser.png`. These are disposable local-host fixtures, not cloud-provider evidence.

## Actual HTTPS readiness + real workers — passed with a local fixture

To test the success path independently of unavailable public tunneling, a separate fixture used a disposable, locally trusted CA-signed `https://localhost:9443` route. The **actual extension performed its real certificate-validated HTTPS identity/nonce fetch** through its restricted proxy to the actual Python service. TLS verification was not disabled. The route adapter was a supported-context test fixture, not actual public DNS or Burrow's cloud tunnel engine.

Fixture commands (test data and certificates are not included):

```text
python3 app/server.py /home/user/tls-test-data/config.json
NODE_EXTRA_CA_CERTS=/home/user/tls-test-data/cert.pem node tests/automatic_tls_fixture.mjs /home/user/tls-test-data /home/user/tls-test-data/cert.pem /home/user/tls-test-data/key.pem
python3 tests/automatic_tls_acceptance.py /home/user/tls-test-data
```

Full observed output: `automatic-tls-refresh.log`:

```text
Automatic extension: actual local CA-trusted HTTPS + nonce + app identity verified (supported context fixture, not public DNS)
Disposable source: HTTPS enrollment and local write/read/delete probe succeeded
Disposable destination: HTTPS enrollment and local write/read/delete probe succeeded
Both Linux agents Verified only after authenticated heartbeat: passed
Test button backend: real inventory usage matched file size
Real Linux writes: hidden/read-only ACLs denied; server/partition quotas enforced; allowed upload verified
Copy -> read-back checksum -> source-change check -> source delete -> empty disconnect: passed
Removed source no longer accepts uploads: passed
Explicit erasure -> empty inventory -> disconnect; agent metadata retained: passed
External E2, CloudGate and public DNS/TLS acceptance: NOT RUN
```

Generated curl commands were actually run against two disposable directories. No user/cloud storage was targeted. Workers exited after disconnection; test host/service/TLS processes were stopped. The clearly labeled demo remains available separately.

## Browser smoke — passed

```text
python3 tests/ui_smoke.py
Browser page errors: []
```

Full output: `ui-refresh.log`. Actual Chromium exercised the labeled demo at desktop 1440px and mobile 390px, checked no document overflow, E2 key-upload gating using synthetic credentials, Linux command/verification gating, group bars, partition dialogs, draggable redistribution percentages totaling 100%, and separate move/erase confirmations. Updated screenshots: `dashboard.png`, `mobile.png`, `linux-setup.png`, `group-settings.png`. These screenshots show illustrative demo usage, not live providers.

## Still untested / operational limits

- No real IDrive E2 or CloudGate account requests. Uploaded credentials were deliberately not used.
- No successful public DNS/TLS/cloud-tunnel enrollment acceptance, external-machine enrollment, host internet failure endurance, systemd user-service or Linux reboot-persistence test.
- Temporary Quick Tunnel addresses can change; existing remote workers require re-enrollment when that happens. A stable linked Burrow domain is recommended.
- Preview limits remain: 16 MiB/file, whole-file weighted migration, logical gateway allocation quotas rather than disk reservation, private mode-600 runtime secrets not encrypted at rest, and detached Linux workers rather than an automatically installed reboot service.
- Pending readiness means the route is not yet usable. Automatic configuration cannot replace a working host tunnel engine, network, domain or certificate setup.

Finish public-network and real-provider acceptance using scoped credentials and disposable storage before relying on this for important data.
