# Notices

## Weft code

The addon was copied from Weft's `examples/hello-weft/` skeleton. Its lifecycle scripts derive from that example. `weft/lib.sh` and `weft/mesh.py` are unmodified vendored copies of Weft's shared helpers. The complete upstream MIT copyright and license notice is in `LICENSE`.

Weft source: https://github.com/alexd-aero/weft

## Aegis shared stylesheet

`app/static/aegis.css` is an unmodified copy of Aegis × Burrow’s `public/ui.css` at commit `3f48e0dbeda3628c33e3c005a9fe19b04816f3bc` (2.24.2). Copyright (c) 2026 Alexd Aero. Its complete upstream MIT notice is retained in `docs/AEGIS-LICENSE.txt`. The management page retains this host shell. The original 1.0.1 `style.css` and management layout are restored in 1.2.1; `robo.css` and the theme switch are not loaded by management; the actual supplied file explorer uses its byte-preserved custom CSS plus self-hosted generated Tailwind.

Source: https://github.com/alexd-aero/aegis-burrow

## Host and provider references

Aegis × Burrow, Bulwark and Burrow Pages were inspected to use actual extension, mount and routing APIs. CloudGate's project was inspected for its setup workflow and actual deployed-client endpoints. These services are not installed or bundled as dependencies. The Aegis stylesheet is bundled separately as noted above.

- https://github.com/alexd-aero/aegis-burrow
- https://github.com/alexd-aero/bulwark
- https://github.com/alexd-aero/burrow-pages
- https://github.com/alexd-aero/cloudgate-wasmer

## Images and marks

The Robo Storage logo was supplied by the user and included at their request. Its ownership is unchanged. Provider badges are simplified identification artwork, not a claim of endorsement or official artwork. Provider names and trademarks belong to their respective owners.

No access keys, passwords, or embedded deployment configuration from the uploaded reference files are included. The synthetic credential strings in tests are not usable credentials.

## Actual user-supplied application

The user directed use of the actual `freecandy5-drive (46).html`, not a visual recreation. The integrated application preserves its original custom CSS, markup/control IDs, application features and embedded MIDI instrument sample bank, with targeted gateway/security/quota changes. Display name: Robo Cloud. The existing supplied `logo.png` self-hosts the reference's primary logo mark. The raw uploaded HTML and its provider credentials/direct-S3 configuration are not distributed or used. Fidelity hashes and changes are recorded in `docs/REFERENCE-FIDELITY.json`.

Ownership of user-supplied UI, logo and embedded audio samples remains with their respective rights holders; these assets are **not relicensed as Weft's MIT code**. Their original file provided no independent sample-bank attribution/license. Confirm rights before public redistribution. The user's original file is untouched.

## Self-hosted browser dependencies

Local copies preserve the reference versions. Complete upstream license texts are included beside the assets:

| Component | Version / license | Local notice |
|---|---|---|
| Ace | 1.32.6, BSD-3-Clause | `app/static/vendor/ACE-LICENSE.txt` |
| PDF.js | 3.11.174, Apache-2.0 | `app/static/vendor/PDFJS-LICENSE.txt` |
| Font Awesome Free | 6.5.1, icons CC-BY-4.0 / fonts OFL-1.1 / code MIT | `app/static/vendor/FONTAWESOME-LICENSE.txt` |
| Tailwind CSS | 3.4.17, MIT; generated locally from original palette/config | `app/static/vendor/TAILWIND-LICENSE.txt` |
| Google Material Icons | Apache-2.0 | `app/static/vendor/MATERIAL-ICONS-LICENSE.txt` |
| Inter | OFL-1.1 | `app/static/vendor/INTER-LICENSE.txt` |
| JetBrains Mono | OFL-1.1 | `app/static/vendor/JETBRAINS-MONO-LICENSE.txt` |

Asset source origins: cdnjs.com, fonts.googleapis.com and fonts.gstatic.com; upstream repositories ajaxorg/ace, mozilla/pdf.js, FortAwesome/Font-Awesome, tailwindlabs/tailwindcss, google/material-design-icons, rsms/inter, JetBrains/JetBrainsMono. No CDN is contacted at runtime. Build-only Tailwind command is in `docs/TEST-REPORT.md`.
