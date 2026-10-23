# Robo Cloud 1.3.4 — original transparent Robo logo

Date: **2026-10-22** (America/New_York). Logo-only application change plus release version/resources. Existing addon ID, storage state, routing, unverified-server removal and signing behavior are retained.

## Exact artwork preservation

The supplied **Robo Storage Logo.png**, 500×500 with an RGBA alpha channel, is copied **byte-for-byte** to `logo.png` and `app/static/cloud-logo.png`. The PNG was not re-encoded, flattened, recolored, cropped or given any added background. Its SHA-256 is:

`17765d5e8824bedface16ba8f24ffd7df22761f89ea302084da9b5c2b76c27e8`

The dashboard, favicon and explorer consume these self-hosted files. Real HTTP tests verify both served asset routes return exactly these original bytes. Existing UI/layout backgrounds and styling are unchanged; the transparent image naturally shows the surrounding UI underneath it.

Windows APP icon resources were regenerated from the same PNG at 16/32/48/64/256px. Actual embedded PNG/DIB pixel alpha was decoded in tests: **every size has transparent corners, fully transparent pixels and fully opaque artwork pixels**. Native icon derivatives are necessarily resized, but are not composited against black, white or another matte. `LOGO-PROVENANCE.json` and `WINDOWS-BUILD.json` record the input and binary/source hashes.

The product remains **Robo Cloud Enrollment**, company/developer **Robo Universal**, dashboard **Robo Cloud**. The installer is still **unsigned**; developer metadata does not create a verified publisher.

## Validation actually run

| Check | Actual result | Evidence |
|---|---|---|
| Full Python suite, including original PNG byte hashes, HTTP asset identity and alpha of all actual embedded Windows icons | **130 tests passed** | `python-1.3.4.log`, `tests/test_logo.py`, `tests/test_signing.py` |
| Portable Go worker/payload regressions | **10 passed, 1 optional real signing fixture skipped** | `go-1.3.4.log` |
| Windows/amd64 GUI cross-build, cross-target Go vet, pinned resource generation, repeated-build reproducibility | **PASS; unsigned cross-build only** | `windows-build-1.3.4.log`, `WINDOWS-BUILD.json` |
| Node extension routing/ownership regressions | **9 passed** | `extension-1.3.4.log` |
| Real Weft lifecycle, data retention, adopt/link, idempotence, read-only detection and foreign-port/stale-PID ownership | **PASS** | `lifecycle-1.3.4.log` |
| Normative publish checker | **Zero errors** | `check-1.3.4.log` |
| Immutable helper/style/source fidelity, secret exclusion, license/credit and package audit | **PASS** | `static-1.3.4.log` |

## Limits / historical evidence

Native Windows icon appearance, native dialog layout, DPAPI/NTFS/sign-in/SmartScreen and trusted-publisher verification remain **NOT RUN**. Pixel/resource inspection is not a real Windows display test. No production signing certificate, key or service was configured; the 1.3.3 signing helpers and explicit unsigned notices are unchanged. The optional real certificate-layout fixture was not regenerated for this logo-only patch; its prior disposable-test-identity results remain historical.

Browser visual acceptance and real provider/public-domain TLS/systemd/reboot tests were not run for this artwork-only patch. Prior targeted browser checks (1.3.2) and wider explorer/planner/local-CA/actual-host checks (1.3.0) remain versioned historical evidence, not fresh execution claims.

Older immutable 1.3.0 and 1.3.1 ZIPs were preserved **losslessly, with original member hashes verified**, inside `Robo-Cloud-1.3.0-and-1.3.1-history.tar.xz` in the workspace. Their original ZIP bytes and checksums are retained; no user artwork, source work or release content was discarded. `HISTORICAL-SCREENSHOTS.json` records how to locate the matching historical ZIP/evidence. More recent release ZIPs remain separately available. Historical file manifests apply only to their matching original releases.
