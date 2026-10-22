# Robo Cloud 1.2.0 — actual-reference integration

Date: **2026-10-21** (America/New_York). Stable addon ID: `robo-storage-aegis`; mount `robo-storage`; persistent schema/data/settings retained. The prior 1.1.0 inspired redesign was rejected and is superseded. Its historical report is preserved as `TEST-REPORT-1.1.0.md`, not presented as this release's acceptance.

## What is actually retained

The source is the user's **actual** `freecandy5-drive (46).html` (SHA256 `1a645b823fb1af92c072ef8349751c4c34e5c15b905c88b6d6b81853555959bd`). This is not a new approximation of its appearance.

- All **19 original custom style blocks are byte-identical**. All original control IDs, including dynamically generated viewer/editor controls, are retained. Assertions and individual hashes: `REFERENCE-FIDELITY.json`.
- Original markup/layout, dialogs, categories, grid/list/selection views, allocation page, Ace/viewer/media controls and embedded instrument samples are retained. The 4.18 MB MIDI instrument sample script has unchanged SHA256 `9f8723b99cf3b244437bf469b2b3fcf50dc5e5dcb502de56ddb4f8924fbf95ae`.
- CSS/scripts are externalized for CSP and self-hosting. Tailwind 3.4.17 is built from the source palette/config/classes. The custom-style/utility cascade was checked against a safely sanitized browser rendering of the actual source, fixing an initial utility-order mismatch; desktop/mobile visibility is not a guessed redesign. The existing user-supplied primary logo is local, with no external logo request.
- Only three new control IDs: `cloudStoragePicker`, `cloudManageLink`, `cloudSourceLabel`. The first two are together in the original lower Storage widget, not distributed through/replacing the sidebar layout.
- Display name is **Robo Cloud**. Signed-in addon `/` retains Aegis navigation above an iframe of the actual application; `/cloud` is that document. Group and server Basic-authenticated links use the same document. `/manage` retains the provider/group/user/allocation configuration forms. Those forms did not exist in the uploaded file and are not claimed to be original reference controls.

## Necessary integration and safety changes

The raw file contained live-looking provider credentials. It was inspected without using its credentials, left untouched, never served as-is, and is not included in the package. Its signing/configuration block is replaced, not carried into browsers. The generated package is scanned against the source's literal credential values.

Original `s3*` calls use authenticated same-origin gateway endpoints, not direct S3 credentials. Source selection is explicit and locked during lists/writes; server-switch editor cache is cleared. ACL/server read-only states disable mutation controls, with authoritative enforcement on the server. Real inventory and effective **decimal allocation** replace the hard-coded 10 GB quota. Actual hidden names never enter public client inventory. Empty folders use real zero-byte `.keep` objects.

Rename is server-side verified copy/read-back/source-change-check/delete with collision refusal, source/destination ACL checks, quota checks and the existing 16 MiB bound. **It requires temporary copy headroom and is not atomic.** A failure can leave destination copies or partially deleted sources; rollback is not promised. Single/bulk deletes retain original confirmation dialogs; bulk deletion is sequential, not atomic. Hidden descendants are not silently deleted.

HTML Render View is an **empty-sandbox iframe, with scripts disabled**; plain source previews remain inert. Filename text/attributes are escaped. Safe MIME and byte-range downloads support the original viewers. Inline HTML downloads are text/plain and responses are sandboxed. Browser CSP does not permit JavaScript unsafe-eval/unsafe-inline; local inline styles are allowed for the supplied UI/Ace. PDF.js evaluation is disabled. Exported Cloudflare challenge scripts are removed, not part of the app.

## Observed results

| Check | Result | Evidence |
|---|---|---|
| Normative Weft publish checker | **Zero errors** | `check-1.2.0.txt` |
| Python regressions, including verified rename/folder marker/collision/quota/ACL/source-change/fidelity | **82 passed** | `python-1.2.0.log` |
| Node extension regressions | **9 passed** | `extension-1.2.0.log` |
| Real Weft lifecycle/linking/idempotence/read-only detect/update retention/foreign-port/stale-PID ownership | **Passed** | `lifecycle-1.2.0.log` |
| Actual supplied UI + real Linux worker | **Passed**, JavaScript errors `[]`, no external requests | `ui-cloud-1.2.0.log` |
| Existing configuration desktop/mobile/forms/dialogs | **Passed** | `ui-configuration-1.2.0.log` |
| Existing configuration light/dark scoping and allocation regression | **Passed** | `ui-theme-1.2.0.log`, `ui-quota-1.2.0.log` |
| Local CA-trusted HTTPS enrollment, two real workers, verified migration and erase | **Passed** | `local-https-1.2.0.log` |
| Actual Aegis 2.24.2 add/install/mount/update/data retention/uninstall | **Passed** | `host-1.2.0.log` |
| Helper/asset/license/credential/ZIP checks | Recorded before packaging | `static-1.2.0.log` |
| Real E2 / CloudGate accounts / public custom-domain / systemd / reboot | **Not run; not claimed** | Limitations below |

`tests/cloud_ui_acceptance.py` drives the original application against the real service and a real installed Linux worker: grid/list, folder navigation, thumbnail/preview, Ace edit/save, sandboxed HTML Render View, file rename, new file/folder, upload, confirmed single/bulk delete, real zero-byte folder marker, dangerous literal filename, read-only controls, source switching, 1 GB allocation, Basic/admin separation, hidden/read-only ACL denial, quota 507 and byte range 206. Original light/dark/mobile rendering and the original admin landing are captured in `cloud-original-*-1.2.0.png` and `cloud-aegis-shell-1.2.0.png`.

The HTTPS fixture uses `https://localhost:9443`, with a disposable CA explicitly trusted by installer/worker/Node; TLS identity verification is not disabled. It is a supported-context Burrow fixture, **not** a public Cloudflare/custom-domain deployment. The actual host test separately uses real Aegis/Burrow 2.24.2 and the real extension/mount APIs. Its unverified public route correctly blocks enrollment commands with 503; it does not fall back to another host or mutate global naming. Browser sessions, test keys/certificates, runtime data and detached agents are outside the archive.

## Retained backend/lifecycle constraints

- Unchecked publication means the exact root domain. Unsupported Aegis primary-root overrides explicitly fail; no prefixed/temporary substitution or global naming changes.
- A 1 GB ceiling contributes 1 GB even on a 512 GB disk; physical capacity remains separate. Linux changes made after Generate are saved before Launch.
- Logical quotas are metadata budgets, not reserved filesystem blocks. Gateway file reads/writes/moves remain bounded at **16 MiB**. Byte ranges currently follow a bounded full backend read; this is not an unbounded streaming server.
- Real E2/CloudGate credentials, existing-account/public-DNS acceptance, custom-domain ownership, systemd/reboot and every media codec/PDF/MIDI-export combination were not certified. Original controls/code were retained, not replaced with simplified substitutes, but retention alone is not end-to-end feature certification.
- Linux workers remain detached outbound processes rather than installed system services. Uninstall deliberately preserves remote data/workers and removes only owned host resources. Updates retain `ADDON_DATA` and the stable addon identity.
- Shared helpers remain byte-identical to Weft commit `f4f14b14bf3dabbbddfee2834bd9f46ee1315452`. Aegis source commit: `3f48e0dbeda3628c33e3c005a9fe19b04816f3bc`.
- User-supplied UI/logo/audio-sample rights are not changed; confirm public redistribution rights. Bundled dependency notices are in `THIRD-PARTY.md` and `app/static/vendor/*-LICENSE.txt`.

## Reproduce

```sh
python3 tools/integrate_freecandy.py '/path/to/freecandy5-drive (46).html'
npx --yes tailwindcss@3.4.17 -c tools/tailwind.config.cjs -i tools/tailwind-input.css -o app/static/vendor/tailwind.css --minify
python3 -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/test_extension.mjs
node /path/to/weft/tools/weft-check.mjs . --publish
python3 tests/lifecycle_acceptance.py /path/to/weft
```

Tailwind compilation is build-only; Python and Node unit/lifecycle fixtures need no live provider account. Browser acceptance fixtures require disposable private services/CA setup described by their headers. Do not run them against production. The original source and first-party logo must be available for regeneration; vendored dependencies are already bundled. Historical reports retain their own evidence and scope rather than being silently reinterpreted as new acceptance.
