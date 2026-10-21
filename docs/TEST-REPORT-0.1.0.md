# Validation report — Robo Storage for Aegis 0.1.0

Date: 2026-10-21. This report distinguishes observed local results from untested external integrations. The archive is a **development preview**, not a production-readiness certificate.

## References actually read

- Weft `SPEC.md`, every file in `examples/hello-weft/`, the Relay example, `tools/lib.sh`, `tools/mesh.py`.
- Weft checkout: `f4f14b14bf3dabbbddfee2834bd9f46ee1315452`.
- Aegis × Burrow **2.24.2**, checkout `3f48e0dbeda3628c33e3c005a9fe19b04816f3bc`.
- CloudGate checkout `74e7606bed9ecf04e5b2586c8f41d01c6b7c9b17`: README, setup helper and actual server/storage routes.
- Bulwark's `mount()` hook and Burrow Pages' extension usage.
- Uploaded Robo Storage HTML references were inspected for visual/behavioral reference, not copied wholesale. Their embedded configuration was not reused.
- The uploaded key-file field **labels only** informed the importer. Its credential values were never used for a provider request or copied into the addon/archive.

## Static validation

Commands run from the Weft checkout:

```text
node tools/weft-check.mjs ../robo-storage-aegis
node tools/weft-check.mjs ../robo-storage-aegis --publish
```

Observed publish-check output:

```text
✔ ../robo-storage-aegis
    robo-storage-aegis 0.1.0: Robo Storage for Aegis · platforms burrow
    update card: teal, glow, 3 highlights
```

Zero errors. Shared helper equality is also checked independently byte-for-byte. Python source compilation and JavaScript syntax checks were run. Manifest/README credit block retained.

## Full Weft lifecycle — Burrow

Ran install → status → update → status → uninstall with `node tools/weft-run.mjs … --host burrow`. This host emulator provides no live Burrow socket; base lifecycle does not require domain access to start.

Initial observed run:

```text
install: exit 0; progress 100 Ready
status: {"state":"running","url":"http://127.0.0.1:8798/","port":8798,"version":"0.1.0","detail":"on port 8798, its own service"}
update: exit 0; progress 100 Ready
status: {"state":"running","url":"http://127.0.0.1:8798/","port":8798,"version":"0.1.0","detail":"on port 8798, its own service"}
uninstall: exit 0; stopped and removed Robo Storage for Aegis; remote files and agents were left intact
```

The expanded acceptance script repeated this on isolated port **18898**:

```text
python3 tests/lifecycle_acceptance.py /path/to/weft-checkout
```

Observed additional checks:

```text
Idempotent second install: one current service, running
Detect: read-only filesystem check passed
Update: data-retention sentinel preserved
Adopted link: no second process; linked uninstall left owner running
Foreign port: installation refused; other application still answering
Stale PID: unrelated process was not signalled
Lifecycle/linking/idempotence/ownership acceptance: passed
```

Full output: [`lifecycle-output.txt`](lifecycle-output.txt). The install refusal on the foreign port is an **expected negative test**, not a suppressed failure.

`WEFT_NO_SYSTEMD=1` exercised the helper's background-process fallback. The sandbox has no usable systemd user session; a running systemd user unit was **not** tested. Selkies Forge lifecycle was not run because the addon does not allow that platform.

## Core/security tests

```text
python3 -m unittest discover -s tests -p 'test_*.py' -v
Ran 44 tests
OK
```

Covers private state permissions, persistence/corruption behavior, names/paths, fake-key parsing, secret removal from API views, scrypt, most-specific ACLs/default denial, password rotation and username changes, inventory totals, server/partition/ancestor budgets, overwrite accounting, full/draining/read-only states, interrupted-job handling, agent I/O, no-follow symlink confinement, metadata exclusion, task ownership, socket realpath, endpoint restrictions and S3 signing shape. Fake credentials in test fixtures are clearly synthetic, not the uploaded example.

Full output: [`unit-test-output.txt`](unit-test-output.txt).

## Burrow extension tests

```text
node --test tests/test_extension.mjs
# tests 1
# pass 1
# fail 0
```

Uses a simulated supported Burrow context, a real test Unix HTTP socket and real local HTTP listeners. Verifies mounted secret injection, naming discovery, nested-base rejection, group-scoped public proxying, stripping spoofed administration headers and cleanup limited to addon-owned tunnels. **The test's example HTTPS hostname is synthetic; this is not a live DNS test.**

Full output: [`extension-test-output.txt`](extension-test-output.txt).

## Actual Aegis host acceptance

Started the checked-out **Aegis × Burrow 2.24.2** in a separate disposable home. Disabled default addon installation, external shield feeds and serveo to avoid installing unrelated apps or opening real public routes. Used its real browser setup/login flow, not a bypass of dashboard authentication.

On **Burrow → Addons**, actually pasted the local addon folder path, added it, and installed it through the real page. Observed:

```text
Add: HTTP 200
addon robo-storage-aegis: install done
robo-storage-aegis: running inside Burrow
Home tile href: /__gate/robo-storage/
Mounted page: http://127.0.0.1:4310/__gate/robo-storage/
Host environment: HTTP 200, connected=true, domains=[], domain=null
Direct anonymous admin access: HTTP 401
Mounted group/user creation: passed
Group unauthenticated response: HTTP 401, WWW-Authenticate: Basic realm="Robo Storage group …", charset="UTF-8"
Browser page errors: []
```

The installed dashboard started empty, without demo data. Screenshots: [`aegis-home.png`](aegis-home.png), [`aegis-mounted.png`](aegis-mounted.png).

A local **test-only HTTPS proxy with a trusted disposable localhost certificate** then routed agent endpoints to the actual installed addon. Two workers were enrolled into disposable local directories. The generated curl command was actually run; no real remote/customer directory was targeted.

Observed:

```text
Actual host update from local addon folder: done
Actual host reinstall with TLS enrollment URL: done
Disposable source: HTTPS enrollment and local write/read/delete probe succeeded
Disposable destination: HTTPS enrollment and local write/read/delete probe succeeded
Both Linux agents Verified only after authenticated heartbeat: passed
Test button backend: real inventory usage matched file size
Real Linux writes: hidden/read-only ACLs denied; server/partition quotas enforced; allowed upload verified
Copy -> read-back checksum -> source-change check -> source delete -> empty disconnect: passed
Removed source no longer accepts uploads: passed
Explicit erasure -> empty inventory -> disconnect; agent metadata retained: passed
External E2, CloudGate and public DNS/TLS acceptance: NOT RUN
Actual Aegis host uninstall: done
stopped and removed Robo Storage for Aegis; remote files and agents were left intact
```

Reproducible host/TLS fixture scripts are included under `tests/`. Full storage acceptance output: [`host-test-output.txt`](host-test-output.txt). The local host, workers and TLS fixture were stopped after the checks. Only the labeled demo remains running for the preview.

## Browser smoke checks

Headless Chromium via Playwright, desktop 1440×1100 and mobile 390×844:

- Dashboard renders with the supplied logo and provider badges.
- Navigation, group details and server settings/partition tabs work.
- E2 launch is disabled without a key upload; uploading a synthetic text fixture unlocks the local form gate without making a provider call.
- Linux command is absent before the enter button; Launch is disabled while unverified.
- Group distribution bar and server usage bars render.
- Redistribution controls and draggable-share UI render; unchecking redistribution opens the separate permanent-erasure confirmation.
- New migration confirmation uses an explicit application modal, not a browser prompt.
- Mobile page has no horizontal overflow.
- No JavaScript page errors in the observed final smoke run.

Demo screenshots: [`dashboard.png`](dashboard.png), [`group-settings.png`](group-settings.png), [`linux-setup.png`](linux-setup.png), [`mobile.png`](mobile.png). They show **illustrative usage**, not evidence of cloud connectivity.

## Problems encountered and resolved

- The first Chromium launch failed because sandbox OS browser libraries were missing (`libnspr4.so`). Installed the browser test dependencies and reran successfully.
- A first real-host add attempt returned `burrow.ui (burrow/ui.js) does not exist`. The static Weft checker had not caught that path. Implemented the UI module; real-host add/install subsequently succeeded.
- Early smoke assertions selected a server without a partition and expected a progress directive inside the host's plain-log widget. Corrected those test selectors/assertions; these were not claimed as passing runs.
- The initial programmatic host acceptance request omitted `X-Robo-Request` and correctly received HTTP 403. Added the required header; rerun succeeded.
- Nested quota validation originally double-counted descendants on a server-limit change. Centralized tree-budget validation and added regression tests.

## Not tested / release gates still open

- Real IDrive E2 authentication, permissions, object operations, large inventories, versioned buckets and provider-specific errors.
- A real deployed CloudGate/Wasmer account, category setup and refresh-token expiration/recovery.
- A publicly reachable Linux machine/network, live Burrow DNS updates, certificates, actual root/nested subdomains, wildcard naming transitions or extra linked zones.
- Real systemd user-service operation and reboot recovery. Remote workers currently require supervision/restart after reboot.
- Large-file/multipart/resumable transfers; this release intentionally caps files at **16 MiB**.
- Independent security audit, adversarial load testing, multi-process state access or transactional safety against unrelated concurrent provider writers.

Before production use, back up data, use dedicated disposable provider prefixes/categories, complete these acceptance gates, and only then migrate real files. Do not infer cloud readiness from the functioning demo or localhost tests.
