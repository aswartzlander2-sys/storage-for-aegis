# Robo Cloud 1.3.1 — Robo Cloud Enrollment Windows branding

Date: **2026-10-22** (America/New_York). This patch changes Windows branding; the dashboard remains **Robo Cloud**, addon ID `robo-storage-aegis` unchanged. Existing storage, worker identities, enrollment protocol and persistent directory names are retained.

## Delivered changes

- **Robo Cloud Enrollment** is the Windows application-name constant, confirmation/message/folder-picker caption, and embedded ProductName/FileDescription/InternalName.
- The generic bundled template, browser-download filename, installed worker filename and OriginalFilename metadata are **Robo Cloud Enrollment.exe**. Template location: `app/windows/Robo Cloud Enrollment.exe`. Obtain a usable one-use installer through the Windows server tab; the generic template alone cannot enroll.
- The original **Robo server logo**, unchanged in `logo.png`, generates an embedded APP icon with 16/32/48/64/256px images. Native confirmation content and window icons use this resource. Standard Windows controls and error/info content remain; the first confirmation retains **Cancel / Continue**, and consumed installers retain exactly **“This Installer was already used on another system.”** with **OK**.
- The embedded manifest uses asInvoker (no requested elevation) and common-controls-v6. The worker remains a per-user folder worker, not a service. Existing RoboCloud storage/autorun keys are deliberately retained for compatibility.
- Developer builds regenerate resources using pinned build-only `github.com/tc-hib/go-winres@v0.3.3`. Source JSON, generated COFF, logo hash, Go source hashes and binary hash are recorded/bundled. The worker links no third-party Go runtime modules. The build tool's ISC notice is retained.

## Validation run on this patch

| Check | Actual result | Evidence |
|---|---|---|
| Python core/cloud/planner/routing/enrollment/Windows HTTP + branding | **107 passed** | `python-1.3.1.log` |
| ProductName/FileDescription/InternalName/OriginalFilename parsed from actual PE resources; APP icon dimensions; HTTP download filename; source logo provenance | **PASS** | `tests/test_windows.py`, `WINDOWS-BUILD.json` |
| Embedded 256px icon compared with the original logo rescaled to 256px | **PASS**, max-channel RMS 2.894/255 (different resamplers) | `windows-build-1.3.1.log` |
| Windows/amd64 GUI build, cross-target Go vet, non-elevating manifest and byte-identical repeated resource+binary build | **PASS; not native execution** | `windows-build-1.3.1.log` |
| Portable Go safety/TLS tests | **7 passed on Linux** | `go-1.3.1.log` |
| Extension ownership/proxy/routing regressions | **9 passed** | `extension-1.3.1.log` |
| Real Weft install/update/uninstall, data retention, adopt/link, idempotence, read-only detection, foreign-port/stale-PID ownership | **PASS** | `lifecycle-1.3.1.log` |
| Normative publish checker | **Zero errors** | `check-1.3.1.log` |
| Source/helper/style/secret/package audit | **PASS** | `static-1.3.1.log` |

## Limitations / outstanding acceptance

**Native Windows execution: NOT RUN.** Resource inspection and cross-compilation do not prove actual Windows rendering or behavior. On a disposable Windows 10/11 x64 machine, check Explorer/File Properties name and server icon, native confirmation/error/folder-picker/taskbar icons, DPI/accessibility layout, Cancel/Continue/OK and consumed-installer text, enrollment, DPAPI, NTFS case/alias/reparse behavior, atomic writes, sign-in startup, credential revocation and cleanup. No native Windows runtime or signing certificate was available.

**Unsigned executable:** Windows may display SmartScreen/unknown-publisher warnings. No bypass is supplied or claimed. Windows remains a testable preview pending native acceptance.

The broader browser/explorer/planner/actual-host/local-CA TLS tests passed for **1.3.0** and were **not rerun for this branding-only patch**. Their dated results and public/provider/native limitations remain in `TEST-REPORT-1.3.0.md` and the `*-1.3.0.log` files. Historical `RELEASE-FILES-<version>.json` manifests apply to their matching immutable release ZIP, not to later source trees. Real E2/CloudGate/public-domain TLS and native Windows acceptance remain unperformed.
