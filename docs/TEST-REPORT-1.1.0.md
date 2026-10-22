# Robo Storage for Aegis 1.1.0 — FreeCandy design adaptation

Date: **2026-10-21**. The user uploaded `freecandy5-drive (46).html` and explicitly selected **both Robo interfaces**: the public file browser and the storage-management panels, while preserving Aegis's surrounding navigation. This supersedes the earlier Aegis-only appearance requirement inside addon surfaces.

## What was adapted

- Both interfaces now use self-hosted Robo glass surfaces, blue/purple ambient color, white pill actions, rounded controls and light/dark themes. Theme preference is shared on the same origin and saved locally. Aegis's navigation retains its own stylesheet and colors.
- The public explorer has a floating glass header, search, storage selector, category sidebar, allocation/type breakdown, folder breadcrumbs, grid/list modes, name/size sorting, visible counts, empty states and a file-preview drawer. Mobile uses a slide-out sidebar and bottom-sheet preview layout.
- Folder entries are derived only from paths already visible to the authenticated user. Empty remote directories are not represented independently. Search/category views span visible files. **Recent** means files previewed in this tab, not fabricated modification dates.
- Supported operations use the existing Basic-authenticated gateway: download, upload, create text file, and exact-path-confirmed deletion. Read-only servers disable mutation controls; per-path permissions and logical quotas remain authoritative on the server.
- Text/code/HTML preview is inert `textContent`. Image/audio/video/PDF preview paths use bounded authenticated reads and local blob URLs. Media codec and native PDF support are browser-dependent; unfamiliar formats are download-only. No external preview service is contacted. PDF/video code paths exist, but playback/rendering of every codec/PDF was not certified.
- Existing root-only unchecked routing, inherited group/server addresses, saved allocation ceilings, users, ACLs and draining semantics remain unchanged.

This is an adaptation over the existing gateway, **not deployment of the uploaded direct-S3 application**. The reference's embedded S3 credentials were detected but not used, executed, or copied. The HTML, its embedded payloads and CDN dependencies are not bundled. Its full Ace/PDF.js/media-player suite, bulk selection/actions, folder upload, rename/move and independent empty-folder operations are not claimed or presented as working controls.

## Results

| Check | Observed result | Evidence |
|---|---|---|
| Normative Weft `--publish` checker | **Zero errors** | `check-1.1.0.txt` |
| Python regressions | **75 passed** | `python-1.1.0.log` |
| Node extension regressions | **9 passed, 0 failed** | `extension-1.1.0.log` |
| Weft lifecycle/linking/idempotence/ownership | **Passed** | `lifecycle-1.1.0.log` |
| Management UI desktop/mobile and existing dialogs | **Passed**, JS errors `[]` | `ui-1.1.0.log` |
| Management glass/theme scoping/persistence | **Passed**, Aegis colors unchanged | `ui-theme-1.1.0.log` |
| Synthetic 512 GB disk / 1 GB allocation UI | **Passed** | `ui-quota-1.1.0.log` |
| Actual Linux file-browser operations and security controls | **Passed**, JS errors `[]`, no external requests | `ui-files-1.1.0.log` |
| Local CA-trusted HTTPS enrollment, two-worker migration/erase | **Passed** | `local-https-1.1.0.log` |
| Actual Aegis 2.24.2 add/install/update/uninstall | **DONE** | `host-1.1.0.log` |
| Static syntax/helper/CSS/license/packaging checks | Recorded before archive creation | `static-1.1.0.log` |
| New public-network / real E2 / CloudGate / custom-domain acceptance | **Not run** | Historical results remain separate |

## Browser and real-worker acceptance

`tests/ui_files_acceptance.py` runs against a real Python service and real outbound Linux worker. Enrollment and callback requests use `https://localhost:9443` with a test CA explicitly trusted by the installer, worker and Node fixture; normal TLS identity/nonce validation is not disabled. The Burrow context is a **supported-context fixture**, not a real Cloudflare/custom-domain deployment. The browser talks to the real group routes over local HTTP and native Basic credentials.

The test created disposable files and exercised:

1. Visible-only folder construction, breadcrumb navigation, grid/list switching and reload persistence.
2. Global search, category filters and in-tab recent previews.
3. Text/code preview, real PNG image decode and native audio controls. Uploaded HTML source was shown literally; its script did not execute.
4. Actual UI text-file creation and upload, followed by reads from the worker filesystem to confirm content.
5. A wrong deletion confirmation was rejected and the file retained; the exact path then deleted successfully.
6. Hidden/read-only write attempts were rejected server-side with HTTP 403. An over-budget UI write displayed the quota error and created no file.
7. A 1 GB allocated contribution, read-only storage selection, empty state and server-scoped selector isolation/403.
8. Light/dark persistence, 390px mobile navigation, no horizontal overflow, no JavaScript exceptions and **no CDN or provider-origin browser requests**.

The first UI run found a real mobile issue: the sidebar's ancestor stacking context placed it beneath its backdrop. `ui-mobile-debug-1.1.0.log` preserves that failure. The ancestor stacking context was removed; the subsequent full browser test passed without force-clicking or bypassing visibility checks.

The separate local HTTPS acceptance then enrolled two additional real workers, checked inventory, enforced hidden/read-only ACLs plus server/partition quotas, migrated with read-back verification and source deletion, and explicitly erased the destination. This was local CA acceptance, not a new public-network pass.

## Actual Aegis host

`tests/host_refresh.py` used a newly disposable **actual Aegis 2.24.2** instance and authenticated host API jobs. It confirmed:

- Manifest version 1.1.0 accepted; install, update and uninstall finished **DONE**.
- The actual management mount loads the unmodified Aegis stylesheet/navigation with the scoped Robo panels and white controls.
- Direct administration stays unauthorized without its internal key; the agent-only proxy rejects dashboard/admin paths.
- The standalone browser works through native Basic login, with Robo header/sidebar, server selector and mobile sizing.
- Update retains group data and the same owned agent tunnel identity without duplication.
- Uninstall removes owned routes and does not recreate them.

No Cloudflare connector was installed for this host run. Public enrollment readiness remained pending, and command generation correctly returned 503 rather than inventing a URL. Real provider/custom-domain/public-network claims are therefore **not** made for 1.1.0.

## Screenshots

Management screenshots use the explicitly labeled demo, not provider inventory:

- `robo-management-light-1.1.0.png`
- `robo-management-dark-1.1.0.png`
- `robo-management-mobile-1.1.0.png`

File-browser screenshots use a disposable local real Linux worker and synthetic test files:

- `robo-files-light-1.1.0.png`
- `robo-files-dark-1.1.0.png`
- `robo-files-mobile-1.1.0.png`

`quota-regression-1.1.0.png` is deliberately synthetic: a 512 GB physical capacity with a 1 GB allocation, showing separate labels and contribution/usage calculations. It is not evidence of an actual 512 GB disk.

## Security, attribution and limits

- The dashboard CSP remains unchanged. Only the authenticated file-browser HTML adds local blob image/media/frame sources for preview; script/connect remain same-origin and object embedding remains disabled. Python regressions check there is one CSP header, no CDN references, self-hosted assets and explicit read-only/effective-capacity API fields.
- No change to Basic authentication, ACL enforcement, server scope, quotas, migration ownership or host routing APIs is needed for the design adaptation. The host limitation on per-tunnel primary-root overrides remains documented in README and the historical 1.0.1 report.
- The addon originally copied hello-weft and reviewed the normative SPEC, all skeleton files, closest references and helpers. Weft reference remains `f4f14b14bf3dabbbddfee2834bd9f46ee1315452`; Aegis remains `3f48e0dbeda3628c33e3c005a9fe19b04816f3bc` (2.24.2).
- `weft/lib.sh` and `weft/mesh.py` remain byte-identical. `app/static/aegis.css` remains byte-identical to Aegis `public/ui.css`; licenses and mandatory ending README Credits are retained. New Robo styles are separate and scoped.
- Runtime certificates, private state, worker/browser sessions, all user uploads, caches and symlinks are excluded from the release. Supplied credential values are checked for absence before packaging.
- Existing limits remain: 16 MiB/file, 100,000 inventory files, logical rather than reserved allocation, whole-file migration, detached workers without automatic reboot persistence and unencrypted-at-rest mode-600 state secrets. Native browser credentials can remain cached; merely closing a tab does not guarantee logout.
- No real E2/CloudGate/custom-domain account, independent-machine, systemd/reboot or endurance acceptance was run. Historical 1.0.0 full public acceptance and 1.0.1 interrupted public runs are preserved in their own reports, not substituted for new results.
