# Robo Storage for Aegis

**1.0.0 — group-inherited routing and live-tested public HTTPS Linux storage.**

Linux enrollment, file access, permissions, quotas, migration and erasure were exercised over actual Burrow/Cloudflare public tunnels. Real IDrive E2 and CloudGate accounts remain untested; see the validation report and limits below.

A Weft addon with its own Aegis dashboard, home-screen tile and storage groups spanning **IDrive E2**, a deployed **CloudGate client**, and **Linux directories**. Uses the supplied Robo Storage logo. The uploaded access-key example and the credentials/configuration in the supplied reference dashboards are **not included or used**.

## Compatibility and specification note

**Aegis × Burrow only.** Uses `BURROW_SOCKET` for domain discovery and routing, and the real Burrow extension context for addon-owned tunnels. `platforms` is therefore `["burrow"]`. Selkies Forge is credited as required by Weft, but is not a supported runtime for this addon.

The supplied prompt suggests `requires.burrow: ">=2.0.0"`; the normative SPEC permits the actual required minimum. Burrow extensions need 2.8+, and this addon also uses the dashboard `mount()` hook used by Bulwark. The manifest conservatively requires **2.24.2+**, the host release inspected and exercised here, instead of guessing compatibility with earlier releases. Local host acceptance is performed against the checked-out host version documented in `docs/TEST-REPORT.md`.

## Features

- Create named groups, then add servers through IDrive E2 / CloudGate / Linux provider tabs.
- E2 requires importing an access-key text export. No import, no launch. Select an existing bucket and optional dedicated prefix.
- CloudGate connection guidance follows `alexd-aero/cloudgate-wasmer`; use the deployed client's HTTPS URL and its Basic username/password. The permanent reauthentication key is **not** a general API credential.
- Linux directory accepts `~/…` and `/…`. Press the square enter button before any enrollment command is shown. The directory is created if missing. Verification requires a successful storage probe plus an authenticated worker heartbeat.
- Server cards, real inventory tests, capacity contributions, 150 px group distribution bars, 75 px server usage bars, and file-type color legends.
- Server and nested-directory quota budgets; child partitions display with a 15% indent. **Logical quotas only**: no loopback images, disks, placeholder files or fake reservations.
- Separate storage website with a storage-server selector next to the group name; upload, download, search and confirmed file deletion.
- Multiple users per group; enable/disable accounts, change usernames and rotate passwords. File/directory rules support read/write, view-only and hidden. The most-specific rule wins; unmatched paths are denied.
- Browser-native HTTP Basic login on storage links; scrypt password hashes; passwords never appear in links. Use HTTPS.
- Server removal: drain first, choose redistribution or strongly confirmed erasure. Shares are adjustable with draggable boundaries and percentage inputs. Whole-file placement approximates requested byte shares.
- Copy/read-back verification, source-change check, conflict refusal, explicit errors and persistent job history. Source entries remain draining on failure; interrupted jobs do not automatically resume deletion.
- Group activity log, read-only mode, provider status and responsive layout.

## What changed in 1.0.0

- **One group address.** Adding a server no longer asks for a domain, subdomain or tunneling settings. A server link is `<group HTTPS URL>/s/<server-id>/`, served through the group tunnel. No extra per-server tunnel is created.
- **Use default Burrow tunnel** is checked below the group address by default. It inherits Burrow’s existing domain and active naming base automatically. Stale manual nested-domain values are ignored in default mode. With no linked domain, Burrow can assign a temporary Quick Tunnel when cloudflared is available.
- Unchecking the box offers only tunnel domains/aliases already configured in Burrow. There is no arbitrary nested-domain input, no global naming change and no invented DNS/TLS coverage.
- Group route status refreshes automatically as Burrow assigns its URL. A proposed address is not marked ready until a certificate-validated HTTPS nonce/identity check reaches the correct group.
- Actual public-network Linux and UI acceptance passed, in addition to 69 Python and 7 extension tests.

### Retained from 0.1.1

- Removed the manual enrollment base-URL setting. Burrow provisions and checks the agent route automatically; Connections displays its current readiness. Each generated command pins its verified callback URL, rather than depending on a later setting change.
- Replaced the custom sidebar/teal theme with Aegis’s actual shared stylesheet: black grid backdrop, raised neutral cards, white primary buttons, the host-style top bar and horizontal storage navigation. The file browser and dialogs use the same visual language. The unmodified upstream stylesheet and MIT license are included; see `THIRD-PARTY.md`.
- Upgrades preserve groups, users and storage data. The obsolete manual setting is ignored. Regenerate unused 0.1.0 enrollment links. Already-enrolled workers retain their own callback configuration, so do not remove an old user-created route while workers still use it.

## Install

**Updating an existing local-folder install:** extract this release over the source folder you originally added to Burrow, then choose **Update** for Robo Storage. Keep `ADDON_DATA`; do not uninstall or delete your groups/users to upgrade. If your source is an archive URL instead, update that source to the new archive using your host’s source controls.

1. Copy/extract this folder onto the Aegis host. Open **Burrow → Addons**, paste the **absolute path on that host** to this folder, and add it. A path on this sandbox is not a path on your computer.
2. Install. Default service port is `8798`. The Aegis home screen gets a **Robo Storage for Aegis** tile; its signed-in page is `/__gate/robo-storage/`.
3. Link your domain in Aegis first. Create a group and its first user, connect storage, then launch. DNS and TLS must be verified on the resulting public address before sharing it.
4. For Linux, **no enrollment URL setting is needed**. The extension automatically creates an addon-owned HTTPS route using Burrow’s existing tunnel configuration. It exposes only `/enroll.sh` and `/agent/*`, not the dashboard. Wait for **Connections → Agent enrollment address** to become ready, then generate the curl command. Commands are withheld until an HTTPS request reaches this service and passes its identity/nonce check. If pending, check Burrow’s tunnel status, DNS and internet access; do not enter a guessed URL.
5. Set direct dashboard credentials only if you need access outside the Aegis mount. Otherwise direct administration is denied. The mount injects an internal random secret after the host's sign-in.

### Group address and the default-tunnel checkbox

Create the group once: enter its name and subdomain, then leave **Use default Burrow tunnel** checked. If Burrow uses `apps.example.com`, a group named `studio` resolves through Burrow as `studio.apps.example.com` without asking you to manually repeat `apps` or match a root domain. Without a linked domain, the public URL is assigned by Burrow’s Quick Tunnel engine; the group label is not a promise of a custom hostname.

Servers added to this group inherit that address. Use the group link for the multi-server browser, or its `/s/<server-id>/` links for a server-scoped browser. Creating a server never asks for a second domain. Existing group users and path rules apply; a server-scoped URL cannot select another server.

If you uncheck the box, the dropdown contains Burrow’s configured primary tunnel base plus generic extra/wildcard aliases or selectable zones offered by the actual tunnel registry. Hidden/conflicting fixed-port aliases and arbitrary DNS records are not treated as usable tunnel bases. A selected extra domain is enabled only for this addon’s own group tunnel, not globally.

The addon does not configure your Cloudflare account, replace your host’s connector, change global naming, or manufacture certificates. If Burrow reports `cloudflared is not installed`, install/repair the host’s tunnel engine or use its existing linked-domain connector. Connections and group routing show pending/verified status rather than guessing an address.

### IDrive E2

Export a new, scoped access-key file from your own account. Expected labels are `Endpoint`, `Region Code`, `Access key ID`, `Secret Access Key`. Import it in the modal, select an existing bucket and preferably a dedicated prefix. The adapter uses S3 Signature V4 and paginated object listing. No buckets or provider credentials are created automatically. Object inventory determines used bytes; provider-wide free capacity is unknown unless you set a quota.

### CloudGate

Deploy your own copy of <https://github.com/alexd-aero/cloudgate-wasmer>. Its `/setup` helper generates a `CGSETUP1:` code containing an account email, refresh token and reauthentication secret. Follow its setup instructions with **your own account**, and put the generated values into deployment environment variables rather than committing secrets to `app.yaml`.

Set `CLOUDGATE_EMAIL`, `CLOUDGATE_REFRESH_TOKEN`, `CREDENTIALS` and `REAUTH_ACCESS_TOKEN` on the deployment. `CREDENTIALS` uses the upstream format `"username","password"`. In Robo Storage, enter the deployment URL plus that username/password and a category. The addon calls the actual `/api/all-files`, `/api/upload`, `/api/download` and `/api/files` routes. It does not install a Wasmer deployment or pretend a reauthentication key is an API token. Data access is limited to the selected category. CloudGate capacity is not inferred from unrelated account-wide usage.

### Linux agent

A stable linked Burrow domain is recommended. Without one, Burrow can supply a temporary Quick Tunnel **if its tunnel engine is available and can reach the network**. The addon configures the route, not your Cloudflare account or host network. If that temporary public address changes, existing remote workers cannot discover the new address: generate a fresh command and re-enroll them. Never treat a pending/proposed address as verified public connectivity.

Run the generated command as the user who should own the directory, without sudo. Requires Python 3.9+, curl, base64, bash and standard Linux utilities on the agent machine. The command downloads to a temporary file before executing; it does not blindly pipe a failed curl response into a shell. Links expire after 15 minutes, are single-use at registration, and contain a sensitive enrollment token: **do not share or log them**.

The worker makes outbound HTTPS requests; it exposes no inbound port. It creates `<selected directory>/.robo-agent/{agent.py,config.json,agent.log,agent.pid}`. Normal files remain under the selected directory. Agent metadata is private and excluded from inventories. Symlink roots/parents and file-path escapes are refused; file operations use no-follow directory descriptors. Storage probe files are created and removed during setup.

The agent is currently a detached user process, **not an automatically enabled reboot service**. Its config persists; after reboot start it with your Python executable and the absolute paths to `.robo-agent/agent.py run .robo-agent/config.json`, or explicitly supervise it yourself. Re-enrollment rotates its token. Stop its PID before manually removing `.robo-agent`; never remove the storage root to uninstall the agent. Disconnection revokes its token and the worker exits when it next polls.

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
- Storage operations intentionally write to the configured remote bucket prefix/category/Linux directory. This is the addon's purpose, and the explicit exception to keeping all runtime writes in `ADDON_DATA`.
- Uninstall removes owned tunnels, service and mesh entry. If Burrow cannot remove recorded routes, uninstall fails visibly instead of pretending cleanup succeeded. Linked copies are left running. Any old manually created enrollment tunnels remain user-owned and are not removed. Remote agents/data are **never erased by addon uninstall**. The host handles deleting `ADDON_DATA` when asked.

## Safety boundaries and release limits

This is a substantial first implementation, not a claim that every requested workflow has passed production acceptance.

- Files up to **16 MiB**; at most **100,000 inventory files** per backend. No large-file streaming/multipart/resumable migration yet. Oversized files stop removal without being deleted.
- Quotas protect writes **through this gateway**. External writers can change usage; refresh before uploads and on Test. Use dedicated prefixes/directories, exclusive ownership during migration, and provider-side retention/backups. No software here can make an uncoordinated external writer transactional.
- Removal handles managed files, not deletion of bucket resources, Linux directories, unrelated categories, backups, object versions or provider recycle bins. Empty Linux directories and agent metadata remain. Removed servers retain a history tombstone; credentials/tokens are revoked after an empty final inventory.
- Redistribution never overwrites a destination conflict. A verified copy may remain at the destination if the subsequent source-change check fails; the source is retained. Investigate duplicates explicitly rather than silently deleting them.
- Accounts/ACLs do not currently restrict users to individual servers within a group: path rules apply to every server in that group. Use separate groups for isolation.
- Basic login uses browser credential caching. Logout behavior is browser-dependent; disabling users or rotating passwords revokes future authorization.
- Endpoint validation rejects non-HTTPS, credentials-in-URLs, redirects and private-address destinations. This is not an independently audited SSRF boundary; do not offer administration to untrusted users.
- No scheduled scan scheduler, alerts delivery, provider credential-rotation UI, large-file editor, full preview/media suite, automatic service setup on remote Linux, or automatic cross-provider failover in this release.
- **Real E2/CloudGate accounts and custom-domain DNS/TLS were not tested here. Actual public Quick Tunnel HTTPS was tested.** Your sample credentials were deliberately not used. See `docs/TEST-REPORT.md` for actual results and remaining acceptance steps.

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

Tests: `python3 -m unittest discover -s tests -p 'test_*.py' -v` and `node --test tests/test_extension.mjs`. Optional browser smoke checks use Playwright: `python3 tests/ui_smoke.py` against the running demo.

Additional disposable-host, actual public-network and local CA-trusted HTTPS acceptance fixtures are described in `docs/TEST-REPORT.md`. Their test data, certificates and browser sessions must never be bundled.

Optional isolated demo: `python3 tests/preview.py /absolute/path/to/demo-data` (binds port 8080). Its clearly marked sample data is **never created by installation**, and live provider tests, tunnel launch, migrations and erasure are disabled. Demo data must not be used as production state.

Before a public published change, bump the manifest version, re-run all checks and lifecycle tests, keep the credit block, and finish real-provider/custom-domain acceptance using disposable storage. Screenshots in `docs/` show the labeled demo, not evidence of provider connectivity.

## Credits

Powered by the [Weft Architecture](https://github.com/alexd-aero/weft). Runs on [Selkies Forge](https://github.com/adatskov-wcpss/animated-fiesta) and [Aegis × Burrow](https://github.com/alexd-aero/aegis-burrow).
