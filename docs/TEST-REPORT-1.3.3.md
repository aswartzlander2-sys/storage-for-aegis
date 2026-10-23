# Robo Cloud 1.3.3 — Robo Universal branding and signing preparation

Date: **2026-10-22** (America/New_York). Stable addon ID `robo-storage-aegis`; existing storage, worker identities and group routes retained.

## User decision and actual scope

The user selected **branding/signing workflow preparation first**, with **no production certificate supplied**. Windows and Linux enrollment installers now identify their developer/company as **Robo Universal**. The application name remains **Robo Cloud Enrollment**, the server logo and original Linux Tux remain, and the main dashboard remains **Robo Cloud**. Original copyright/license ownership is not rewritten.

**Distributed artifacts are UNSIGNED.** Windows CompanyName/author text does not create a verified publisher. Unknown publisher/SmartScreen warnings may remain. Linux has no Windows Verified Publisher dialog. No private production key, PFX, password, online signing endpoint, trust-root modification or warning bypass is included. See `SIGNING.md` for requirements and explicit limitations.

## Changes

- Actual Windows PE `CompanyName`: **Robo Universal**; native confirmation developer line and source constant use the same label. Product resources/build version: **1.3.3**. Windows template rebuilt with pinned go-winres and official checksum-verified Go 1.27.3.
- Linux enrollment shell header and bootstrap messages identify **Robo Universal** and explicitly state the default unsigned/developer-label status. The exact `curl -fsSL … | bash` command remains; it is not claimed to verify signatures.
- New `app/installers.py` bounds/validates the unsigned Windows PE template and refuses a nonempty certificate directory. It never appends a token to a signed base while pretending its signature remains valid.
- Windows payload parsing supports final Authenticode certificate-table placement and 0–7 alignment padding bytes. It reads only the covered enrollment trailer before the certificate table, never arbitrary certificate bytes or a forged EOF trailer inside that excluded data. Parsing layout does **not** verify a signature or publisher.
- Prepared developer-only Windows helper checks the approved worker-prefix SHA-256, final trailer/gateway, actual certificate name **Robo Universal**, Code Signing EKU, private-key availability and dates. It stages exact inspected bytes, signs SHA-256 with an HTTPS RFC3161 timestamp, then requires SignTool and Get-AuthenticodeSignature trust verification for the selected certificate before publishing a new output file.
- Prepared Linux helper signs a final personalized shell script using an existing full-fingerprint-selected GnuPG key, verifies the detached signature and refuses replacement of an existing output. Recipients must independently authenticate/pin the key; a display name is not proof of identity.
- Helpers are not called by the addon/download endpoint. A secured production per-download signing integration and a genuine certificate/service still need to be provisioned. General release archives contain only the unsigned generic template, never valid personalized enrollment capabilities.

## Validation actually run

| Check | Actual result | Evidence |
|---|---|---|
| Full Python suite, including PE CompanyName and icon, unsigned/build status, malformed/signed template rejection and real HTTP Linux developer/unsigned headers | **127 tests passed** | `python-1.3.3.log` |
| Portable Go worker and payload tests | **11 cases passed on Linux**, including optional real certificate-layout fixture | `go-1.3.3.log` |
| Actual PE signing-layout fixture, cryptographic digest verification and same-length payload-tamper rejection | **PASS with a disposable test certificate only** | `signing-workflow-1.3.3.log` |
| Actual Linux signing helper, matching script/signature verification and tamper rejection | **PASS with a disposable test key only** | `signing-workflow-1.3.3.log` |
| Windows helper parser/syntax check with PowerShell 7.6.8 | **PASS; not native Windows/SignTool execution** | `signing-workflow-1.3.3.log` |
| Windows/amd64 GUI build, cross-target Go vet, source/resource/binary hashes and repeated-build reproducibility | **PASS; unsigned cross-build only** | `WINDOWS-BUILD.json`, `windows-build-1.3.3.log` |
| Node extension routing/ownership regressions | **9 passed** | `extension-1.3.3.log` |
| Actual Weft lifecycle install/update/uninstall, data retention, adopt/link, idempotence, read-only detection and port/stale-PID ownership | **PASS** | `lifecycle-1.3.3.log` |
| Normative publish checker | **Zero errors** | `check-1.3.3.log` |
| Original source/style/helper fidelity, literal original-key exclusion, license/credit and archive provenance audit | **PASS** | `static-1.3.3.log` |

The Windows cryptographic test certificate's name was **LAYOUT TEST ONLY - NOT TRUSTED**; its chain was checked explicitly against that temporary test certificate, not against Windows/public trust roots. The Linux test identity was likewise **SIGNING TEST ONLY (NOT TRUSTED)** in an isolated temporary GnuPG home. No test key/certificate/personalized artifact is distributed. Neither test establishes Robo Universal's real identity or verified-publisher status.

## Still not performed

**Native Windows execution/visual layout, genuine CA-issued Robo Universal publisher display, native SignTool/helper execution, real HSM/service integration, DPAPI/NTFS/sign-in/SmartScreen acceptance: NOT RUN / NOT CONFIGURED.** Cross-build and portable certificate-layout tests are not substitutes. Production key custody, CA identity validation, secure signing-service access controls and per-download operations remain future work.

No real E2/CloudGate/public-domain TLS/systemd/reboot acceptance was run. The 1.3.2 targeted Chromium removal/logo/mobile checks and the broader 1.3.0 explorer/planner/actual-host/TLS checks were not rerun for this metadata/signing-preparation patch. Their versioned evidence remains historical; `TEST-REPORT-1.3.2.md` describes the preserved unverified-removal behavior. Historical release-file manifests apply only to their original immutable ZIPs. Historical generated screenshots remain byte-for-byte in the original 1.3.1 archive as indexed by `HISTORICAL-SCREENSHOTS.json`.
