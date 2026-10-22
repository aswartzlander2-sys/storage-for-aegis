# Robo Cloud for Aegis

**1.3.2 — Original Linux Tux artwork and removable unverified servers, including failed draining setups.**

Management uses the original pre-Robo Aegis layout. Only the file explorers use the supplied Robo UI; the unnecessary management button is removed. Earlier real Linux-worker and actual Aegis-host checks passed; see the versioned evidence. The Windows x64 GUI EXE is cross-compiled and protocol/filesystem safeguards are tested, but native Windows execution/sign-in/SmartScreen acceptance is **not** claimed. Real E2/CloudGate/custom-domain/systemd/reboot acceptance is not claimed. See the validation report.

A Weft addon with its own Aegis dashboard, home-screen tile and storage groups spanning **IDrive E2**, a deployed **CloudGate client**, **Linux directories**, and **Windows folder workers**. Windows is a remote worker platform; the addon host still runs on Linux/Burrow. Uses the user-supplied Robo logo. The uploaded access-key example and the credentials/configuration in the supplied reference dashboards are **not included or used**.

## Compatibility and specification note

**Aegis × Burrow only.** Uses `BURROW_SOCKET` for domain discovery and routing, and the real Burrow extension context for addon-owned tunnels. `platforms` is therefore `["burrow"]`. Selkies Forge is credited as required by Weft, but is not a supported runtime for this addon.

The supplied prompt suggests `requires.burrow: ">=2.0.0"`; the normative SPEC permits the actual required minimum. Burrow extensions need 2.8+, and this addon also uses the dashboard `mount()` hook used by Bulwark. The manifest conservatively requires **2.24.2+**, the host release inspected and exercised here, instead of guessing compatibility with earlier releases. Local host acceptance is performed against the checked-out host version documented in `docs/TEST-REPORT.md`.

## Features

- Create named groups, then add servers through IDrive E2 / CloudGate / Linux / Windows provider tabs, using native Aegis-style tab treatment.
- E2 requires importing an access-key text export. No import, no launch. Select an existing bucket and optional dedicated prefix.
- CloudGate connection guidance follows `alexd-aero/cloudgate-wasmer`; use the deployed client's HTTPS URL and its Basic username/password. The permanent reauthentication key is **not** a general API credential.
- Linux directory accepts `~/…` and `/…`. Press the square enter button before any enrollment command is shown. The directory is created if missing. Verification requires a successful storage probe plus an authenticated worker heartbeat.
- Server cards, real inventory tests, capacity contributions, 150 px group distribution bars, 75 px server usage bars, and file-type color legends.
- Server and nested-directory quota budgets; child partitions display with a 15% indent. **Logical quotas only**: no loopback images, disks, placeholder files or fake reservations.
- The actual supplied file explorer, with its original viewers/editor/dialogs and safely integrated storage operations. The addon opens the original Aegis management dashboard. Public group/server links use the actual supplied explorer; an authenticated standalone explorer remains at `/cloud`.
- Aegis top navigation remains unchanged. All browser dependencies are self-hosted; no embedded reference credentials or direct S3 browser signing is distributed.
- Multiple users per group; enable/disable accounts, change usernames and rotate passwords. File/directory rules support read/write, view-only and hidden. The most-specific rule wins; unmatched paths are denied.
- Browser-native HTTP Basic login on storage links; scrypt password hashes; passwords never appear in links. Use HTTPS.
- Verified server removal: drain first, choose redistribution or strongly confirmed erasure. Shares are adjustable with draggable boundaries and percentage inputs. Whole-file placement approximates requested byte shares.
- Copy/read-back verification, source-change check, conflict refusal, explicit errors and persistent job history. Verified source entries remain draining on failure; interrupted jobs do not automatically resume deletion.
- Group activity log, read-only mode, provider status and responsive layout.

## What changed in 1.3.2

- The Linux badge is the **original Tux artwork by Larry Ewing, created with The GIMP**, not a hand-drawn approximation. It is self-hosted, with unchanged original PNG pixels inside the SVG and attribution in `docs/licenses/TUX-NOTICE.txt`.
- **Unverified servers can be removed without contacting storage**, for Linux, Windows, IDrive E2 and CloudGate. In server settings → **Remove server**, use **Remove unverified server…**, type the exact name, and acknowledge that remote files are kept. Never-enrolled workers retain the simpler confirmed **Cancel unenrolled server…** action.
- This also recovers unverified setup entries already stuck **Draining** after a failed attempt. They no longer require an unreachable worker/provider to return an empty scan. The group/shared tunnel stays in place, outstanding enrollment links and worker credentials are revoked, stored credentials are removed, and an inventory/history tombstone remains. Files are **not** scanned, moved, erased or claimed to be empty.
- Unverified `/drain` requests are rejected before creating a job. Verified sources still require the established Move/Erase workflow and separate erasure confirmation. An actually running storage operation must finish before disconnection; a busy operation returns a prompt error instead of blocking the request. Failed/interrupted jobs are marked cancelled with their prior error details retained. Service restart never resumes erasure automatically.
- No Windows worker source/binary changes: this addon release reuses the validated **1.3.1 Robo Cloud Enrollment** binary/resources, preserving its build provenance and unsigned/native-acceptance limitations.

## Retained from 1.3.1

- The Windows executable is named **Robo Cloud Enrollment** in its source constant, native dialog titles and embedded ProductName/FileDescription/InternalName metadata. Downloaded and installed files are **`Robo Cloud Enrollment.exe`**. The main dashboard remains **Robo Cloud**.
- The existing **Robo server logo** is embedded as a multiresolution APP icon (16/32/48/64/256px) for Windows Explorer, the confirmation dialog and native window icons. Standard error/OK content and Cancel/Continue buttons remain unchanged.
- A non-elevating manifest enables standard Windows common-control theming. One-use enrollment, storage confinement and persisted identity are unchanged. Cross-compilation/resource inspection is not native Windows execution; the unsigned/SmartScreen caveat still applies.

## Retained from 1.3.0

- Fixed reproducible directory/preview response races, source-switch stale state and caches, save-in-flight edit loss/duplicate saves, and context-menu folder deletion falsely succeeding without deleting descendants. Folder-list failures now stop destructive confirmation. Recent-file history is scoped by source and login context.
- New File/New Folder use a server-enforced create-only guard after a fresh inventory scan, rather than silently truncating existing files. Provider drafts survive tab switches; never-enrolled worker entries can be cancelled with confirmation, revoking only their links and touching no remote files.
- Storage bars now measure allocated capacity, not padded/flex-growing labels. Group distribution is 150px high, server usage 75px. Unknown capacity has no fabricated fraction; unlisted/hidden usage remains part of total usage without revealing hidden paths. Inherited partition ceilings are reflected in detail bars.
- Linux enrollment is exactly the requested short form **`curl -fsSL 'https://…/enroll.sh?token=…' | bash`**. The command block has a GitHub-style copy icon, accessible feedback and a manual-selection fallback. Native Aegis-style tabs have keyboard support.
- Windows adds a personalized **one-use EXE** download with native Win32 Cancel / Continue confirmation, local folder picker and ordinary error/OK dialogs. It installs a per-user outbound worker with DPAPI-protected credentials and Windows-sign-in startup. Used installers show exactly **“This Installer was already used on another system.”** Their consumed-token hashes survive link regeneration and expiry.
- **Windows is not native-runtime certified here.** The bundled Windows GUI PE was cross-compiled, not executed on Windows. It is unsigned; SmartScreen may warn. See the Windows section and `docs/WINDOWS-BUILD.json`.
- The actual supplied explorer, its original 19 CSS blocks/control IDs, original Aegis management, stable addon ID, data, logical planner, ACLs and migration safeguards remain. This is a targeted audit, **not a claim that every possible UI bug has been eliminated**; unreported failures still need reproduction details.

## Retained from 1.2.1

- **Original Aegis management restored.** `/` and `/manage` use the original 1.0.1 management markup/layout and stylesheet (with the Robo Cloud display name and new partition tool). No Robo glass stylesheet, theme switch or explorer-shell landing is applied to the editor/settings. Aegis navigation is unchanged.
- **Explorer only:** the actual supplied `freecandy5-drive (46).html` remains the file explorer. Its 19 original CSS blocks and all original controls are retained. The added Manage Robo Cloud button is removed. A small separate stylesheet fixes overlay tiers rather than redesigning the source.
- **Partitions are folders**, including empty and nested registered budgets with no files or physical directory yet. This uses ACL-filtered partition metadata, not invented marker files or fake usage. Nested writes use the same directory path and inherited quota. Hidden partition names/paths are not sent to public clients. Normal user-created empty folders still use `.keep` objects as before.
- **Graphical partition manager:** allocation map with unallocated budget, folder/label/usage/budget table, exact unit sizing and keyboard-accessible size slider, queue, undo/discard, review and explicit Apply. Changes are committed atomically as metadata only. Existing paths are fixed; the tool does not format disks, move files or erase data. Removing a budget leaves all files in place.
- Plans enforce effective allocation, inherited ceilings, sibling totals (including legacy inherited/no-ceiling parents), existing usage and path/file collisions. A stale plan or changed server ceiling returns **409**, rather than overwriting another administrator's edits. Usage is a last-inventory snapshot; use Test before planning. New plans support up to 256 entries.
- Registered partition folders cannot be renamed or bulk-deleted through the explorer; their contents can be managed normally. This prevents stale budget paths and accidental destructive partition removal.
- **Preview three-dot information panel** is portaled above the glass preview at body level and restored on close. Dialogs remain above the information panel. Desktop light/dark and mobile click-through are tested; the planner footer is always visible while its body scrolls.
- Gateway Basic/admin authentication, hidden/read-only ACLs, safe HTML sandbox, local assets, decimal quotas, original Ace/media controls and the **16 MiB/file** limit are retained. Rename remains verified copy/delete, needs temporary quota space, and is not atomic. Bulk file deletion remains sequential: earlier confirmed deletions can already have completed if a later file fails; refresh before retrying.
- Prior root-domain routing, 1 GB-versus-physical allocation and save-after-Generate fixes are retained. Real E2/CloudGate/custom-domain/systemd/reboot acceptance is still not claimed.

`docs/REFERENCE-FIDELITY.json` records original source/style/sample hashes. The raw reference's credentials are never used or bundled. Full current results: `docs/TEST-REPORT.md`; previous release reports remain historical.

## Retained corrections from 1.0.1

- **Unchecked means the root domain directly:** checked `studio.apps.example.com`, unchecked `studio.example.com`. Only root zones are offered in unchecked mode; a wildcard/prefix base is not treated as the root. A saved legacy unchecked/prefixed route is blocked in the UI rather than advertised as a verified root address.
- **Host limitation, not a hidden fallback:** Aegis 2.24.2 does not expose a per-tunnel primary-root override when its global primary naming prefix is active. In that configuration, root publication is explicitly unavailable. The addon never changes global naming or substitutes the prefixed/Quick address. Root publication works only when Burrow actually offers the root-level base or a matching configured root alias; HTTPS identity verification still applies. Custom-domain account acceptance has not been run.
- **Quota edits after generating a Linux command are saved before Launch,** including the server name. A 1 GB quota is 1,000,000,000 bytes, even on a 512 GB physical disk. Contributions, bars and the file browser use effective allocated capacity; physical disk size is separately labeled.
- **Existing installations:** update without deleting `ADDON_DATA`. If 1.0.0 previously lost a quota edit, open that server’s Settings, explicitly save the intended ceiling and run Test. The missing value cannot be reconstructed automatically. Legacy unchecked groups may need their root domain reselected and relaunched; unavailable root routing is shown explicitly. Existing tunnel resources are not silently deleted merely because a legacy route is blocked in the dashboard.
- Current regression/lifecycle/host and partial public-network results, including interrupted runs, are recorded in `docs/TEST-REPORT.md`.

## Retained from 1.0.0

- **One group address.** Adding a server no longer asks for a domain, subdomain or tunneling settings. A server link is `<group HTTPS URL>/s/<server-id>/`, served through the group tunnel. No extra per-server tunnel is created.
- **Use default Burrow tunnel** is checked below the group address by default. It inherits Burrow’s existing domain and active naming base automatically. Stale manual nested-domain values are ignored in default mode. With no linked domain, Burrow can assign a temporary Quick Tunnel when cloudflared is available.
- Unchecked behavior was corrected in 1.0.1 as described above; the original 1.0.0 interpretation is superseded.
- Group route status refreshes automatically as Burrow assigns its URL. A proposed address is not marked ready until a certificate-validated HTTPS nonce/identity check reaches the correct group.
- Actual public-network Linux and UI acceptance passed, in addition to 69 Python and 7 extension tests.

### Retained from 0.1.1

- Removed the manual enrollment base-URL setting. Burrow provisions and checks the agent route automatically; Connections displays its current readiness. Each generated command pins its verified callback URL, rather than depending on a later setting change.
- Introduced Aegis’s actual shared stylesheet and host navigation. In 1.2.1 the original Aegis configuration layout is restored; the actual supplied application is retained only at file-browser entry points. See `THIRD-PARTY.md`.
- Upgrades preserve groups, users and storage data. The obsolete manual setting is ignored. Regenerate unused 0.1.0 enrollment links. Already-enrolled workers retain their own callback configuration, so do not remove an old user-created route while workers still use it.

## Install

**Updating an existing local-folder install:** extract this release over the source folder you originally added to Burrow, then choose **Update** for Robo Cloud. Keep `ADDON_DATA`; do not uninstall or delete your groups/users to upgrade. If your source is an archive URL instead, update that source to the new archive using your host’s source controls.

1. Copy/extract this folder onto the Aegis host. Open **Burrow → Addons**, paste the **absolute path on that host** to this folder, and add it. A path on this sandbox is not a path on your computer.
2. Install. Default service port is `8798`. The Aegis home screen gets a **Robo Cloud** tile; its signed-in page is `/__gate/robo-storage/`.
3. Link your domain in Aegis first. Create a group and its first user, connect storage, then launch. DNS and TLS must be verified on the resulting public address before sharing it.
4. For Linux, **no enrollment URL setting is needed**. The extension automatically creates an addon-owned HTTPS route using Burrow’s existing tunnel configuration. It exposes only `/enroll.sh` and `/agent/*`, not the dashboard. Wait for **Connections → Agent enrollment address** to become ready, then generate the curl command. Commands are withheld until an HTTPS request reaches this service and passes its identity/nonce check. If pending, check Burrow’s tunnel status, DNS and internet access; do not enter a guessed URL.
5. Set direct dashboard credentials only if you need access outside the Aegis mount. Otherwise direct administration is denied. The mount injects an internal random secret after the host's sign-in.

### Group address and the default-tunnel checkbox

Create the group once: enter its name and subdomain, then leave **Use default Burrow tunnel** checked. If Burrow uses `apps.example.com`, a group named `studio` resolves through Burrow as `studio.apps.example.com` without asking you to manually repeat `apps` or match a root domain. Without a linked domain, the public URL is assigned by Burrow’s Quick Tunnel engine; the group label is not a promise of a custom hostname.

Servers added to this group inherit that address. Use the group link for the multi-server browser, or its `/s/<server-id>/` links for a server-scoped browser. Creating a server never asks for a second domain. Existing group users and path rules apply; a server-scoped URL cannot select another server.

If you uncheck the box, the dropdown contains root zones, not Burrow’s prefixed naming bases. `studio` plus `example.com` requests exactly `https://studio.example.com`. If Burrow cannot expose that exact address, Launch reports the limitation before creating/changing a tunnel. It does not fall back to `studio.apps.example.com` or a temporary tunnel. A configured extra root alias is enabled only on this addon’s own group tunnel, not globally. On Aegis 2.24.2, an active primary naming prefix cannot be overridden for just one tunnel through its supported API.

The addon does not configure your Cloudflare account, replace your host’s connector, change global naming, or manufacture certificates. If Burrow reports `cloudflared is not installed`, install/repair the host’s tunnel engine or use its existing linked-domain connector. Connections and group routing show pending/verified status rather than guessing an address.

### IDrive E2

Export a new, scoped access-key file from your own account. Expected labels are `Endpoint`, `Region Code`, `Access key ID`, `Secret Access Key`. Import it in the modal, select an existing bucket and preferably a dedicated prefix. The adapter uses S3 Signature V4 and paginated object listing. No buckets or provider credentials are created automatically. Object inventory determines used bytes; provider-wide free capacity is unknown unless you set a quota.

### CloudGate

Deploy your own copy of <https://github.com/alexd-aero/cloudgate-wasmer>. Its `/setup` helper generates a `CGSETUP1:` code containing an account email, refresh token and reauthentication secret. Follow its setup instructions with **your own account**, and put the generated values into deployment environment variables rather than committing secrets to `app.yaml`.

Set `CLOUDGATE_EMAIL`, `CLOUDGATE_REFRESH_TOKEN`, `CREDENTIALS` and `REAUTH_ACCESS_TOKEN` on the deployment. `CREDENTIALS` uses the upstream format `"username","password"`. In Robo Cloud, enter the deployment URL plus that username/password and a category. The addon calls the actual `/api/all-files`, `/api/upload`, `/api/download` and `/api/files` routes. It does not install a Wasmer deployment or pretend a reauthentication key is an API token. Data access is limited to the selected category. CloudGate capacity is not inferred from unrelated account-wide usage.

### Linux agent

A stable linked Burrow domain is recommended. Without one, Burrow can supply a temporary Quick Tunnel **if its tunnel engine is available and can reach the network**. The addon configures the route, not your Cloudflare account or host network. If that temporary public address changes, existing remote workers cannot discover the new address: generate a fresh command and re-enroll them. Never treat a pending/proposed address as verified public connectivity.

Run the generated command as the user who should own the directory, without sudo. Requires Python 3.9+, curl, base64, bash and standard Linux utilities on the agent machine. The user-requested command pipes curl output to bash. Only paste the command generated by your trusted, verified HTTPS host; do not substitute an untrusted URL. The bootstrap script stages its embedded Python worker in a temporary file and uses `set -euo pipefail`. A shell pipeline can mask curl’s exit status; check the printed probe result and the authenticated Verified status in Aegis rather than treating a shell exit code alone as success. Links expire after 15 minutes, are single-use at registration, and contain a sensitive enrollment token: **do not share or log them**.

The worker makes outbound HTTPS requests; it exposes no inbound port. It creates `<selected directory>/.robo-agent/{agent.py,config.json,agent.log,agent.pid}`. Normal files remain under the selected directory. Agent metadata is private and excluded from inventories. Symlink roots/parents and file-path escapes are refused; file operations use no-follow directory descriptors. Storage probe files are created and removed during setup.

The agent is currently a detached user process, **not an automatically enabled reboot service**. Its config persists; after reboot start it with your Python executable and the absolute paths to `.robo-agent/agent.py run .robo-agent/config.json`, or explicitly supervise it yourself. Re-enrollment rotates its token. Stop its PID before manually removing `.robo-agent`; never remove the storage root to uninstall the agent. Disconnection revokes its token and the worker exits when it next polls.

### Robo Cloud Enrollment — Windows folder worker (Windows 10/11 x64)

1. Add a **Windows** server, name it and set its logical allocation. **Generate one-use Windows installer**, then **Download Windows EXE**. No Go/Python/compiler/admin installation is required on that PC. There is no separate tunnel or manual callback URL.
2. Open the personalized EXE. After a read-only HTTPS token check it shows standard Windows **Cancel / Continue** buttons. Cancel or cancelling the folder picker does not register/install a worker or consume the token.
3. Continue, then choose a **dedicated local storage folder**. Do not choose a folder containing unrelated applications, executable startup scripts, private credentials or files you do not intend to share. System/program folders, drive roots, network shares, reparse roots and the worker’s own installation tree/ancestors are refused.
4. A write/read-back/remove probe and inventory must succeed. Registration consumes the installer atomically; downloading or preflighting it does not. A duplicate/consumed installer shows **`This Installer was already used on another system.`** with **OK**, including when opened again on the original PC. An unused expired/revoked installer instead asks for a fresh download. Links expire after 15 minutes; consumed hashes are retained in addon state.
5. The worker runs in the background, makes certificate-verified outbound HTTPS requests and starts at this Windows user’s sign-in through `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`. It is not a service, needs no UAC elevation and does not run while the user is signed out. Aegis enables Launch only after an authenticated heartbeat; allocation/name edits are still saved before Launch.

Installation files are under **`%LOCALAPPDATA%\RoboCloud\workers\<installer-id>\`** (`Robo Cloud Enrollment.exe`, `config.json`). The active token is encrypted for the Windows user using DPAPI, never stored in plaintext configuration. The downloaded installer contains a sensitive enrollment capability, not provider keys: keep it private and delete that download after successful registration. Use **Settings → Generate replacement installer/command** to reconnect an existing worker after a failed setup or address change; provider and server identity stay fixed. A Windows replacement must choose the same canonical folder; add a separate server for a different folder. New installers may be generated if setup fails; old active worker credentials rotate only on a successful new registration.

The worker uses `os.Root`-confined file operations, bounded reads/writes, same-directory atomic replacement/read-back, and rejects Windows device/ADS/path aliases and reparse/symlink components. Gateway paths require exact entry spelling, despite Windows’ case-insensitive filesystem; alternate case/8.3 aliases cannot bypass path ACLs. Junctions, symlinks and cloud-only reparse placeholders are not served. Existing ordinary files remain in place. Limits match Linux: 16 MiB/file, 100,000 inventory files, server-side logical quotas. Direct local filesystem writers are outside the gateway’s quotas.

**Removal:** for a connected worker, use the existing verified Move/Erase + confirmation workflow; its selected storage is not recursively removed by uninstalling the addon. After a server is disconnected, token revocation makes its worker exit on the next poll and remove its own startup value. Then the per-worker installation directory can be manually removed after the process exits; **never delete the chosen storage folder to uninstall the worker**. A never-enrolled pending entry has a confirmed **Cancel unenrolled server** option that only revokes links/removes metadata, without a remote scan or any file deletion. Addon uninstall itself leaves remote workers/data alone; disable startup/stop the process locally if retaining detached state.

**Unsigned/native-runtime caveat:** Windows may show SmartScreen/unknown-publisher warnings. No code-signing certificate or native Windows runtime was available here. Native dialog layout, cancel behavior, folder picking, DPAPI, NTFS alias/reparse cases, executable replacement and sign-in startup must still be acceptance-tested on a disposable Windows PC before production use. Cross-compilation and portable tests are not a substitute for that acceptance.

## Settings

| Key | Default | Meaning |
|---|---|---|
| `PORT` | `8798` | Service port, listening on `ADDON_BIND` like the host |
| `ADMIN_USER` | `admin` | Direct dashboard Basic username |
| `ADMIN_PASSWORD` | empty | Direct dashboard password, at least 12 characters; empty initially means no direct login |

Changes take effect on reinstall/update. A blank password on a later reinstall keeps an existing password hash; use Aegis for normal administration. Storage credentials and user accounts are maintained in the dashboard, not the manifest. Runtime provider credentials are kept in a mode-600 state file, **not encrypted at rest**; protect and back up `ADDON_DATA` and the host's settings store. The host necessarily holds password settings supplied to it.

## Actions

**Restart** restarts the service. Linked copies refuse restart and remain controlled by their owning host. Destructive storage actions are inside authenticated application dialogs, not lifecycle script names.

## What installation changes

- Saves configuration, internal secret, scrypt password hash, storage/provider credentials, users, inventory, jobs and logs in **`ADDON_DATA` only**.
- Creates the helper's systemd user service when available; otherwise runs a detached background process with a PID file in `ADDON_DATA`.
- Writes only this addon's mesh entry, refreshed every 30 seconds.
- The extension automatically creates **one addon-owned, agent-only Burrow tunnel** and scoped loopback proxy. Group tunnels are created only when Launch is requested; servers inherit them and do not create separate tunnels. Ownership is persisted in `ADDON_DATA/burrow-routes.json`; fresh enrollment status is kept in the private `agent-enrollment.json`, and read-only group URL/readiness snapshots in `published-routes.json`. It retries provisioning/health checks and reconnects proxy targets after updates; it never changes global Burrow naming or takes over another addon’s tunnel.
- Storage operations intentionally write to the configured remote bucket prefix/category/Linux or Windows folder. The Windows installer also writes its explicitly consented per-user worker/startup state on the remote PC. This is the addon's purpose, and the explicit exception to keeping all runtime writes in `ADDON_DATA`.
- Uninstall removes owned tunnels, service and mesh entry. If Burrow cannot remove recorded routes, uninstall fails visibly instead of pretending cleanup succeeded. Linked copies are left running. Any old manually created enrollment tunnels remain user-owned and are not removed. Remote agents/data are **never erased by addon uninstall**. The host handles deleting `ADDON_DATA` when asked.

## Safety boundaries and release limits

This is a substantial first implementation, not a claim that every requested workflow has passed production acceptance.

- Files up to **16 MiB**; at most **100,000 inventory files** per backend. No large-file streaming/multipart/resumable migration yet. Oversized files stop removal without being deleted.
- Quotas protect writes **through this gateway**. External writers can change usage; refresh before uploads and on Test. Use dedicated prefixes/directories, exclusive ownership during migration, and provider-side retention/backups. No software here can make an uncoordinated external writer transactional.
- Removal handles managed files, not deletion of bucket resources, Linux directories, unrelated categories, backups, object versions or provider recycle bins. Empty Linux/Windows directories and agent metadata remain. Removed servers retain a history tombstone. Verified removal revokes credentials/tokens after an empty final inventory. Unverified setup removal instead revokes access and keeps all remote files untouched, without claiming the source is empty.
- Redistribution never overwrites a destination conflict. A verified copy may remain at the destination if the subsequent source-change check fails; the source is retained. Investigate duplicates explicitly rather than silently deleting them.
- Accounts/ACLs do not currently restrict users to individual servers within a group: path rules apply to every server in that group. Use separate groups for isolation.
- Basic login uses browser credential caching. Logout behavior is browser-dependent; disabling users or rotating passwords revokes future authorization.
- Endpoint validation rejects non-HTTPS, credentials-in-URLs, redirects and private-address destinations. This is not an independently audited SSRF boundary; do not offer administration to untrusted users.
- No scheduled scan scheduler, alerts delivery, provider credential-rotation UI, large-file editor, full reference preview/media suite, automatic service setup on remote Linux, or automatic cross-provider failover in this release.
- **Real E2/CloudGate accounts and custom-domain DNS/TLS were not tested here. Actual public Quick Tunnel HTTPS was tested in earlier releases; this release reran local CA-trusted HTTPS, not public DNS.** Your sample credentials were deliberately not used. See `docs/TEST-REPORT.md` for actual results and remaining acceptance steps.

## Development and validation

The addon started by copying `examples/hello-weft/`. `weft/lib.sh` and `weft/mesh.py` remain byte-identical to Weft's shared tools. The MIT notice for copied Weft code is retained in `LICENSE`.

From a Weft checkout:

```bash
node tools/weft-check.mjs /path/to/robo-storage-aegis --publish
node tools/weft-run.mjs /path/to/robo-storage-aegis install --host burrow
node tools/weft-run.mjs /path/to/robo-storage-aegis status --host burrow
node tools/weft-run.mjs /path/to/robo-storage-aegis update --host burrow
node tools/weft-run.mjs /path/to/robo-storage-aegis status --host burrow
node tools/weft-run.mjs /path/to/robo-storage-aegis uninstall --host burrow
```

Tests: `python3 -m unittest discover -s tests -p 'test_*.py' -v` and `node --test tests/test_extension.mjs`. Optional configuration-panel browser smoke checks use Playwright: `python3 tests/ui_smoke.py` against the running demo.

Additional disposable-host, actual public-network and local CA-trusted HTTPS acceptance fixtures are described in `docs/TEST-REPORT.md`. Their test data, certificates and browser sessions must never be bundled.

Optional Windows build: Go **1.25+** and pinned go-winres v0.3.3 (build-only; downloaded by the build script), `python3 tools/build_windows.py --go /path/to/go`; tests: `cd windows-worker && go test -v ./...`, plus cross-target `GOOS=windows GOARCH=amd64 go vet ./...`. No Go modules, resource tool or compiler are needed on the addon host. The worker still links only the Go standard library; go-winres is a development-time resource generator. Build info/source hashes are recorded in `docs/WINDOWS-BUILD.json`. A personalized installer is generated by appending a bounded JSON enrollment trailer to the bundled GUI executable; it is not code-signed.

Historical generated screenshots are preserved byte-for-byte in the unchanged **1.3.1 release ZIP**, not duplicated in every newer runtime package. `docs/HISTORICAL-SCREENSHOTS.json` lists their original archive paths and SHA-256 hashes. This release includes its own current removal screenshots, tests and logs; no user-uploaded artwork or runtime assets were removed.

Optional isolated demo: `python3 tests/preview.py /absolute/path/to/demo-data` (binds port 8080). Its clearly marked sample data is **never created by installation**, and live provider tests, tunnel launch, migrations and erasure are disabled. Demo data must not be used as production state.

Before a public published change, bump the manifest version, re-run all checks and lifecycle tests, keep the credit block, and finish real-provider/custom-domain acceptance using disposable storage. Screenshots in `docs/` identify either the labeled management demo or disposable local Linux-worker acceptance; they are not evidence of real E2/CloudGate account connectivity.

## Credits

Powered by the [Weft Architecture](https://github.com/alexd-aero/weft). Runs on [Selkies Forge](https://github.com/adatskov-wcpss/animated-fiesta) and [Aegis × Burrow](https://github.com/alexd-aero/aegis-burrow).
