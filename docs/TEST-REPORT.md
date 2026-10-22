# Robo Cloud 1.3.2 — original Linux artwork and removable unverified setups

Date: **2026-10-22** (America/New_York). Addon ID `robo-storage-aegis`, existing persistent state and group routes unchanged.

## Root cause and fix

The previous removal flow could mark an **unverified** source draining and then wait for a remote scan that could never succeed. Its management gate also blocked cancellation while draining. The old cancellation endpoint accepted only never-enrolled, empty **pending** folder workers, leaving failed providers and probed-but-not-heartbeating workers without a safe metadata-only removal path.

- Unverified `/drain` requests now fail **before** a job is created or status changes.
- **Remove unverified server…** disconnects a setup entry without any backend scan, migration, write or erasure. It requires the exact server name and an explicit keep-remote-files acknowledgment. This supports Linux, Windows, E2 and CloudGate, including already-draining unverified entries.
- Never-enrolled workers retain their existing confirmed cancellation action, now also usable for failed draining setups. Existing clients using `/cancel-enrollment` remain compatible.
- Removal revokes outstanding enrollment links and active worker credentials, clears stored provider credentials, leaves the group/shared route untouched, and preserves a tombstone/inventory. Failed/interrupted jobs become cancelled with their original state/error detail retained. Permanent consumed Windows installer hashes remain permanent.
- A real in-flight storage operation cannot be hidden or raced: it must finish before disconnection. Busy locks fail promptly with an explicit retry message. A legacy per-server published route must be explicitly unpublished first; the new operation never guesses ownership or mutates a shared group route.
- Heartbeat authentication and state update are atomic with disconnection. Enrollment-link creation rechecks status under the state lock, registration/removal races cannot resurrect a server, and removed entries cannot be rescanned into active storage.
- Verified sources still use safe Move/Erase, retain source records on failure and require the separate destructive erasure confirmation. An offline-but-previously-verified server is not treated as an empty failed setup.

## Linux artwork

The simplified approximation is replaced by the **original Tux PNG by Larry Ewing, created with The GIMP**, embedded losslessly in the existing self-contained `linux.svg` path. Original dimensions 265×314; embedded PNG SHA-256 `e4f4c8010312078a37ca1797a8c9eaa5156d0fec407d7875522ca31a3d78c586`. Attribution, permission quote and source URLs are in `licenses/TUX-NOTICE.txt`. No AI redraw, pixel modification, CDN or runtime remote fetch.

## Validation run for this patch

| Suite | Actual result | Evidence |
|---|---|---|
| Full Python suite | **121 tests passed** | `python-1.3.2.log` |
| Real HTTP removal: four provider types, pending and legacy draining, known inventory preserved, no provider transport calls, confirmation/auth gates, unverified drain blocked, probed worker revocation, spent Windows replay retained | **PASS** | `tests/test_unverified_removal.py` |
| Registration, first-heartbeat and replacement-link races; busy lock/running job/legacy-route protection | **PASS** | `tests/test_unverified_removal.py` |
| Actual Chromium clicks: stuck-draining removal for all four providers; unchecked/wrong-name rejection; old Cancel enrollment recovery; verified Move/Erase second confirmation; original Tux decoded in setup and server cards; 390px footer; escaped untrusted names; local-only assets | **PASS; JS errors []** | `unverified-ui-1.3.2.log`, `unverified-removal-1.3.2.jpg`, `unverified-removal-mobile-1.3.2.jpg` |
| Node extension routing/ownership regressions | **9 passed** | `extension-1.3.2.log` |
| Actual Weft install/update/uninstall, retained data, adopt/link, idempotence, read-only detect, foreign-port/stale-PID ownership | **PASS** | `lifecycle-1.3.2.log` |
| Normative publish checker | **Zero errors** | `check-1.3.2.log` |
| Source/helper/style/secret/archive audit | **PASS** | `static-1.3.2.log` |

All removal acceptance used disposable local state and synthetic credentials. Provider transport was deliberately disabled in the HTTP/Chromium fixture: metadata-only removal still succeeded. No real provider account or user storage was used. A file sentinel remained unchanged. Temporary test servers and fixture directories were cleaned up by test teardown.

## Retained evidence and limits

The Windows source, resources, logo and binary are **unchanged from 1.3.1**. `WINDOWS-BUILD.json` still correctly describes that binary (PE product version 1.3.1), not a newly compiled worker. Its source/binary hashes and PE branding tests were checked in this patch. Go build/vet/portable execution were **not rerun**; their historical results remain in `TEST-REPORT-1.3.1.md` and versioned logs.

**Native Windows execution remains NOT RUN; the EXE remains unsigned.** Cross-build/resource/protocol tests are not Windows rendering, DPAPI/NTFS/sign-in or SmartScreen acceptance. Real E2/CloudGate/public-domain TLS/systemd/reboot tests also remain unperformed. The wider explorer/planner/local-CA TLS/actual-Aegis-host acceptance from 1.3.0 was not rerun for this targeted patch; see `TEST-REPORT-1.3.0.md`.

Older generated screenshots are retained byte-for-byte in the unchanged original **1.3.1 release ZIP**, rather than duplicated in each current runtime/source package. `HISTORICAL-SCREENSHOTS.json` records each path/hash and the immutable archive hash. No unique user-uploaded artwork or runtime asset was removed. All current source, runtime assets, licenses, new tests/screenshots and versioned text evidence are in this release. Historical release-file manifests apply only to their matching original ZIPs.
