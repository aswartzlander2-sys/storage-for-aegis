# Robo Cloud 1.2.1 — Aegis restoration, partition planner and explorer patches

Date: **2026-10-21** (America/New_York). Addon ID/mount remain `robo-storage-aegis` / `robo-storage`. This release follows the user's explicit choices: original Aegis management layout, Robo styling only for file explorers, logical—not physical—partitions. Earlier reports are historical (`TEST-REPORT-1.2.0.md`, `TEST-REPORT-1.1.0.md`).

## Changes actually made

### Original editor / management

`/` and `/manage` serve the original 1.0.1 Aegis management markup/layout and stylesheet, with the Robo Cloud display name and the new partition tool. The old management application was compared against the 1.0.1 archive: outside branding, the modifications are the partition-manager entry/old partition-form removal and dialog-class reset. The original `style.css` is byte-identical to 1.0.1. No Robo glass stylesheet, theme control or explorer iframe is applied to the editor/settings. Aegis's upstream `aegis.css` is still byte-identical.

### File explorers

The actual supplied FreeCandy document remains the public group/server explorer and optional authenticated `/cloud` browser. Its original **19 custom CSS blocks and original control IDs** remain preserved; hashes are in `REFERENCE-FIDELITY.json`. The extra **Manage Robo Cloud button is removed**. Storage selection stays because multiple connected sources need an explicit target. Credentials/direct-S3 signing from the raw source remain excluded. Original editor/media controls remain, not an approximation or simplified rewrite.

Registered logical partitions are returned as **ACL-filtered metadata** and merged into directory rendering as folders, even when empty or nested and no physical directory exists yet. No fake files, marker writes or usage are created by partition registration. Root/intermediate paths are deduplicated with real file-derived folders. Nested file writes use the real path and inherited quotas. Hidden partition names/paths are absent from the public metadata response. Ordinary New Folder still uses its existing zero-byte `.keep` object.

Registered partition folders/ancestors cannot be renamed or selected for destructive folder deletion in the explorer. Individual files can still be managed. Budget changes/removal belong to the Aegis partition tool; removing a budget does not erase data. Server-side rename also checks registered paths under its server lock, preventing stale quota registrations.

### Professional logical partition maker

The former name/path/budget form is replaced with a graphical allocation map and unallocated-budget segment, folder/label/budget/usage table, nested hierarchy, exact units and keyboard-accessible resize slider. Changes are queued; undo/discard and a review/acknowledgment precede Apply. The header/footer remain visible while the planner body scrolls, including 390px mobile.

The new admin endpoint validates the complete plan before a single metadata replacement, using the server lock and store lock. It preserves existing partition identity by directory path; new IDs are server-generated. It checks review confirmation, expected original partitions/server ceiling, entry count (up to 256), duplicate/unsafe paths, labels, integer budgets, inherited/effective allocation, sibling totals, existing usage and file/path collisions. A stale snapshot or concurrently edited server ceiling returns **409**, without overwriting changes. Legacy zero-ceiling parents correctly inherit their ancestor/server ceiling for sibling-total validation.

This is **not disk repartitioning**: no formatting, filesystem selection, reserved blocks, file relocation or erasure. Existing paths cannot be changed in the planner. Removing a budget leaves its files intact. Usage comes from the latest inventory snapshot; Test refreshes it. External writes outside the gateway are not blocked by logical quotas.

### Preview three-dot / glass stacking

The original information drawer was trapped inside a backdrop-filter stacking context. While the expanded preview's information panel is open, it is portaled to body level, above the glass overlay; closing restores its original DOM location. A small separate `cloud-fixes.css` defines overlay tiers: preview, information panel, mutation dialogs/context menu, toast. The 19 original style blocks are untouched. Rename/delete dialogs remain clickable above the panel.

## Final observed results

| Check | Result | Evidence |
|---|---|---|
| Normative Weft publish checker | **Zero errors** | `check-1.2.1.txt` |
| Python regressions | **99 passed** | `python-1.2.1.log` |
| Node/Burrow extension regressions | **9 passed** | `extension-1.2.1.log` |
| Real Weft lifecycle/link/adopt/idempotence/read-only detect/data retention/foreign-port/stale-PID checks | **Passed** | `lifecycle-1.2.1.log` |
| Real Linux worker + original explorer operations/security + new partition folders/preview stacking | **Passed**, JS errors `[]`, no external requests | `ui-cloud-1.2.1.log` |
| Planner queue/slider/undo/resize/removal/concurrent-edit rejection/mobile footer | **Passed**, JS errors `[]` | `ui-partitions-1.2.1.log` |
| Restored Aegis layout, no Robo/theme/explorer-shell management, mobile containment | **Passed** | `ui-layout-1.2.1.log` |
| Existing management controls, E2 import gate, root routing, Linux gating, migrations/erase dialogs | **Passed** | `ui-configuration-1.2.1.log` |
| Synthetic 512 GB physical / 1 GB allocation regression | **Passed** | `ui-quota-1.2.1.log` |
| Local CA-trusted HTTPS enrollment, two real Linux workers, verified migration and confirmed erase | **Passed** | `local-https-1.2.1.log` |
| Actual Aegis/Burrow 2.24.2 add/install/mount/update/retention/uninstall | **Passed** | `host-1.2.1.log` |
| Syntax, old-style/source fidelity, helper/license/credential/package checks | Recorded before ZIP creation | `static-1.2.1.log` |
| Real E2/CloudGate accounts, public custom-domain, systemd/reboot | **Not run / not claimed** | Limitations below |

The expanded real-worker test uses the actual original explorer and real gateway, not mocked file-operation responses. It covers grid/list, directory navigation, thumbnail/preview, Ace edit/save, sandboxed HTML, file rename, new file/folder, upload, confirmed single/bulk delete, filename HTML escaping, read-only controls, source switching, Basic/admin isolation, hidden ACLs, range 206 and quota 507. It creates a reviewed three-partition plan, verifies no inventory/physical-directory side effects, browses empty/nested partition folders, writes a real nested file and verifies inherited quota denial. The information drawer is hit-tested above glass on desktop light/dark and 390px mobile, with a nested rename dialog above it.

The focused planner browser test verifies queue without immediate server mutation, native slider keyboard behavior, below-usage rejection, undo, resize, removal retaining real files, concurrent HTTP-409 refusal and visible mobile footer. Unit regressions cover atomic failure (including an invalid later row), sibling/nested/effective limits, legacy inherited ceilings, conflicts, IDs, metadata visibility and registered-folder rename refusal.

Screenshots: `aegis-management-1.2.1.png`, `aegis-original-dashboard-1.2.1.png`, `partition-planner-1.2.1.png`, `partition-mobile-1.2.1.png`, and `preview-info-*-1.2.1.png`. Demo screenshots are labeled as sample data; real-worker screenshots are disposable local fixtures, not provider-account evidence.

## Retained limits and safety boundaries

- Logical quotas only; **16 MiB per file** gateway bound remains. Range delivery currently follows a bounded full backend read, not unrestricted streaming.
- Rename remains verified copy/read-back/source-change-check/delete, requires temporary copy headroom and is **not atomic**. Failure may leave copies or partly removed sources. Bulk file deletion is sequential, not atomic. Budget-plan application is metadata-atomic and does not promise file-operation transactions.
- HTML Render uses an empty sandbox with scripts disabled; text/filename escaping, local fonts/dependencies, safe MIME, authenticated URLs and restrictive browser CSP remain. Retaining original viewers/MIDI samples does not certify every codec/PDF/MIDI-export combination.
- Root-only unchecked routing, no global naming mutation/fallback, inherited group addresses, decimal allocation and save-after-Generate changes are retained.
- HTTPS acceptance uses a **local CA-trusted localhost fixture**, not public DNS/provider credentials. TLS identity verification is not disabled. Actual host acceptance separately uses real Aegis/Burrow APIs; its unverified public enrollment route correctly returns 503. The disposable host's Serveo dashboard exposure was disabled.
- Real E2/CloudGate account integration, custom-domain ownership, systemd/reboot and broad concurrency/provider-failure acceptance were not performed. These tests cover the reported patches and listed regressions, not a guarantee that every possible issue is eliminated.
- Linux workers remain detached outbound processes. Updates preserve `ADDON_DATA`; uninstall does not erase remote data or seize unrelated resources. Disposable test workers/services/certificates/sessions are outside the package and cleaned up after validation. Historical archives are not overwritten.
- User-supplied logo/UI/audio rights are unchanged; confirm public redistribution rights. Third-party notices remain in `THIRD-PARTY.md` and vendor license texts.

## Reproduce

```sh
python3 tools/integrate_freecandy.py '/path/to/freecandy5-drive (46).html'
python3 -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/test_extension.mjs
node /path/to/weft/tools/weft-check.mjs . --publish
python3 tests/lifecycle_acceptance.py /path/to/weft
```

The original HTML is required only for regeneration and is never bundled raw. Browser fixtures document disposable private-service setup requirements in their headers; run `cloud_ui_acceptance.py` before `partition_ui_acceptance.py`. Never point acceptance fixtures at production storage. Runtime assets/Tailwind are already bundled; no CDN is required at runtime.
