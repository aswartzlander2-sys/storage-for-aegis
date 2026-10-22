# Robo Cloud 1.3.0 — explorer audit, native tabs and Windows folder-worker preview

Date: **2026-10-22** (America/New_York). Stable addon ID `robo-storage-aegis`, mount `robo-storage`, existing ADDON_DATA and routes retained. This release addresses reproducible audit findings; the user reported several unspecified failures without reproductions. **This is not certification that every UI bug has been eliminated.**

## Changes and evidence

- **Explorer races:** directory loads carry a generation/path/source epoch; stale responses and retries cannot repaint another folder. Background refresh checks its original source/path. Full-bucket statistics use the current authenticated metadata snapshot instead of a competing second listing. Preview downloads/paint boundaries, information-panel completion and audio/art updates carry identity guards. Source changes clear stale editors, selection, modals, caches and MIDI state, and confirm unsaved changes. Recent history is source/login-context scoped.
- **Editing:** a save captures the selected file and content snapshot; edits typed while saving remain dirty, duplicate saves are blocked, and a dirty sibling editor is not overwritten. Fallback editors honor permissions and preview/edit state. Failed HTTP downloads are not presented as editable file contents. HTML/HTM previews retain an empty sandbox; PDF evaluation stays disabled.
- **Create/delete:** New File/New Folder send a create-only flag, checked server-side after a fresh inventory. Ordinary folder context deletion expands confirmed descendants instead of filtering its only folder marker and falsely reporting success. List failures stop confirmation. Registered partition folders/ancestors remain protected. Bulk deletion remains sequential, not atomic; earlier deletions can have completed if a later operation fails.
- **Bars/layout:** accurate allocated-capacity segments without label padding/flex dilution; group map 150px, server bar 75px, zero/unknown contributions do not receive invented width. Unknown explorer capacity produces no fabricated percentage; unlisted usage is included in the used share, without revealing hidden paths. Inherited partition ceilings are reflected in detail bars. General dialog bodies scroll while actions remain visible; mobile server headings wrap onto a readable row.
- **Enrollment UI:** exact short `curl -fsSL 'https://…/enroll.sh?token=…' | bash`; GitHub-style copy/check glyph, accessible Copied feedback and manual-selection fallback. Native Aegis-style provider/local tabs and arrow-key navigation; provider drafts retain generated identity. A never-enrolled worker can be cancelled with confirmation, revoking only unused links and metadata, without scanning/deleting remote storage.
- **Windows:** personalized, platform-gated GUI EXE downloads; read-only token preflight; native Cancel/Continue dialog, folder picker and error/OK message. Atomic consumption follows a successful folder probe/inventory. Exact consumed error is **`This Installer was already used on another system.`**, including reuse on the same PC. Consumed SHA-256 token tombstones survive link regeneration/expiry; unused expired/revoked links are distinct. First heartbeat is required for Verified/Launch; full/draining status is retained. Settings can generate a replacement for the same server/folder; an invalid replacement probe does not revoke the running worker, and successful registration rotates its credential.

The Windows implementation uses Go standard library plus Win32 APIs: confined os.Root operations, bounded verified writes/reads, exact-path spelling and alias/reparse rejection, safe local roots, System32-only DLL loading, protected per-user DPAPI credentials, and explicitly consented HKCU Run startup. The installation tree and its ancestors cannot become a storage root. It opens no listening port, requires no administrator elevation, and is not a Windows service. The user-selected folder is not deleted by uninstalling the worker/addon. See README for cleanup and root/path restrictions.

## Validation actually run

| Suite | Result | Evidence |
|---|---|---|
| Python core/cloud/quota/planner/routing/enrollment/Windows HTTP | **106 tests passed** | `python-1.3.0.log` |
| Actual extension context/ownership/proxy/routing regressions | **9 tests passed** | `extension-1.3.0.log` |
| Portable Go worker safety/TLS/payload tests | **7 tests passed on Linux** | `go-1.3.0.log` |
| Windows/amd64 build, GUI PE header, source/binary hash record; cross-target Go vet | **PASS (cross-compile only)** | `WINDOWS-BUILD.json`, `windows-build-1.3.0.log` |
| Real source explorer + real Linux worker, Basic/ACLs, upload/edit/create/rename/delete, sandbox, media range, local-only assets | **PASS; JS errors []** | `cloud-ui-1.3.0.log` |
| Forced out-of-order real directory/preview responses, edit during a held save, real folder context delete, source reset, unknown/hidden usage | **PASS; JS errors []** | `ui-audit-1.3.0.log` |
| Real clipboard/copy feedback, short command, native tab treatment/keyboard, retained drafts, personalized EXE browser download, confirmed unused cancellation, 390px visible footer | **PASS; downloaded EXE not executed** | `enrollment-ui-1.3.0.log` |
| Planner queue/undo/resize/review/apply, retain files, concurrent 409, metadata-order labels, mobile footer | **PASS** | `planner-1.3.0.log` |
| Synthetic 512GB physical/1GB allocation; measured 25% server fill, 25/75/0% group widths at desktop/mobile, 150/75px heights | **PASS** | `quota-1.3.0.log` |
| Management desktop/mobile/native layout and modal smoke | **PASS** | `management-1.3.0.log`, `layout-1.3.0.log` |
| Local CA-verified automatic HTTPS, two actual Python workers, heartbeat gate, real quota/ACL writes, verified migration and second-confirmed erase | **PASS** | `tls-1.3.0.log` |
| Weft install/update/uninstall, adoption/linking, read-only detect, idempotence, stale PID and foreign-port ownership | **PASS** | `lifecycle-1.3.0.log` |
| Actual Aegis 2.24.2 add/install/mount/update/data+route identity retention/uninstall | **PASS; JS errors []** | `host-1.3.0.log` |
| Normative publish checker | **Zero errors** | `check-1.3.0.log` |
| Secret/source/helper/style/license/path/archive audit | **PASS** | `static-1.3.0.log` |

Windows HTTP tests use a simulated Windows probe payload against the real Python service. They test binary personalization/platform gating, concurrent token consumption (one 200, one exact 409), preflight non-consumption, invalid-probe rejection, persisted consumed hashes, heartbeat/full status and safe unused cancellation. They **do not prove native Win32/NTFS/DPAPI/startup behavior**. Go tests run portable filesystem/TLS logic on Linux; cross-target vet and PE integrity do not execute the binary.

## Native Windows acceptance still required

**NOT RUN:** native Windows EXE launch, confirmation/cancel UI, folder picker, high-DPI/accessibility layout, DPAPI on real Windows accounts, NTFS case/8.3/reparse/junction behavior, Windows atomic replacement, logoff/sign-in startup, authorization revocation/cleanup, antivirus/SmartScreen, real Windows broker file operations, and Windows-to-other-provider migration. No native Windows runtime or signing certificate was available. The executable is **unsigned** and may trigger SmartScreen/unknown-publisher warnings. Treat Windows support as a testable preview until this matrix passes on a disposable Windows PC.

**Also NOT RUN for this release:** real IDrive E2/CloudGate accounts, public DNS/custom-domain TLS and actual public Quick Tunnel connectivity, systemd/reboot acceptance or a full OS/browser matrix. Actual-host route readiness stayed pending in this sandbox and command generation correctly returned 503; the separate local-CA fixture supplied real TLS transport for worker acceptance. Earlier public-network evidence remains historical, not a new acceptance claim.

## Fidelity and packaging

The supplied raw explorer remains untouched and is never bundled. Its **19 original custom CSS blocks and original control IDs** remain preserved; patches are reproducible through `tools/integrate_freecandy.py` and `tools/cloud_runtime_fixes.py`. Management retains original Aegis markup/layout and byte-identical original `style.css`, with additive native-tab/bar/dialog fixes in `dashboard-controls.css`. The upstream Aegis stylesheet and immutable Weft helpers remain byte-identical. No original provider keys, live configs, private runtime, certificate/key, browser session, toolchain/cache or personalized executable is included.

The bundled `app/windows/robo-cloud-worker.exe` is a generic unsigned template. It intentionally refuses ordinary installation without a valid personalized enrollment trailer; obtain the usable one-use EXE from the Windows server tab on the installed addon. No compilation is required on the host. Developer build command: `python3 tools/build_windows.py --go /path/to/go` with Go >=1.25; recorded compiler Go 1.27.3. Runtime license notices and copy glyph MIT notice are retained. A command screenshot uses a deliberately redacted capability, not a live enrollment link. Other screenshots identify disposable local tests or the clearly labeled management demo.

Existing release reports/archives remain historical and unchanged. The final archive and checksum are delivered alongside this source. Remaining user-specific UI failures should be reproduced with exact steps/screenshots rather than assuming this audit covered them.
