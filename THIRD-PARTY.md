# Notices

## Weft code

The addon was copied from Weft's `examples/hello-weft/` skeleton. Its lifecycle scripts derive from that example. `weft/lib.sh` and `weft/mesh.py` are unmodified vendored copies of Weft's shared helpers. The complete upstream MIT copyright and license notice is in `LICENSE`.

Weft source: https://github.com/alexd-aero/weft

## Aegis shared stylesheet

`app/static/aegis.css` is an unmodified copy of Aegis × Burrow’s `public/ui.css` at commit `3f48e0dbeda3628c33e3c005a9fe19b04816f3bc` (2.24.2). Copyright (c) 2026 Alexd Aero. Its complete upstream MIT notice is retained in `docs/AEGIS-LICENSE.txt`. The management page retains this host shell. App-specific layout CSS and scoped `robo.css` supply the Robo surfaces; the standalone file explorer uses the self-hosted Robo stylesheet.

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

## User-supplied FreeCandy design reference

The user uploaded `freecandy5-drive (46).html` and requested its Robo glass design for both interfaces. It was inspected as a visual reference. The uploaded HTML, its embedded credentials/configuration, direct browser-to-S3 client, third-party CDN dependencies and bundled payloads are not distributed. The adapted interface uses local CSS, original inline SVG controls and existing authenticated gateway APIs. No credential values were used.
