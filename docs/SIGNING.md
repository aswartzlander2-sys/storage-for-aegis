# Robo Universal — installer branding and signing preparation (1.3.3)

## Current status: UNSIGNED

The user selected **branding and workflow preparation first**, without an existing production signing certificate. Windows `CompanyName` and native developer text now say **Robo Universal**. Linux enrollment headers and installation messages also identify **Robo Universal**. Product/application name remains **Robo Cloud Enrollment**; the dashboard remains **Robo Cloud**.

**These labels are not cryptographic proof. No public signing certificate, private key, trust-store change, warning bypass or verified-publisher claim is included.** Windows can still show **Unknown publisher**, and SmartScreen can still warn. Its verified publisher is derived from an actually trusted signing certificate, not the CompanyName/author fields. A certificate authority must validate the real identity and permitted display name; the branding does not establish eligibility for that certificate.

The built/downloaded Windows files remain unsigned; Linux's current HTTPS `curl -fsSL … | bash` flow does **not** verify a detached signature. That existing command is retained, not represented as a signature-verifying installer. No DEB/RPM/MSI packaging or repository signing is implemented.

## Why signing order matters

Every Windows download contains a one-use enrollment capability, appended after the generic PE. Each Linux shell script likewise embeds its individual enrollment data. **Sign each final personalized artifact, not the generic base.** Appending enrollment to a signed EXE would invalidate its signature. The addon now rejects a PE template with a nonempty certificate directory instead of silently doing this.

Windows signing appends a `WIN_CERTIFICATE` table and may insert up to seven zero padding bytes. The worker now locates the enrollment trailer immediately **before** that table/padding. It never takes an enrollment URL/token from certificate bytes, because Authenticode excludes certificate data from its digest. Its layout parser is **not** an Authenticode trust verifier; Windows/SignTool perform that separate verification. Unsigned downloads still use the unchanged EOF trailer.

## Windows developer workflow — prepared, not connected to downloads

Prerequisites: a Windows signing machine, Windows SDK `signtool.exe`, and a **trusted Code Signing certificate for Robo Universal** already installed in `CurrentUser\My` or `LocalMachine\My`, with access to its private-key/HSM provider. Prefer a managed or hardware-backed signing key. Do not export/upload a PFX, private key, token PIN or password into this addon or conversation.

1. Build/review the worker using `python3 tools/build_windows.py --go /path/to/go`. Preserve the trusted `docs/WINDOWS-BUILD.json` approval record with its exact generic-binary hash.
2. Generate a new Windows one-use enrollment through your installed addon and download its final EXE over verified HTTPS. Treat this file as a short-lived secret capability; keep it in a private directory. Do not publish personalized EXEs as general releases.
3. Run the prepared helper on the signing machine:

```powershell
$thumbprint = Read-Host 'Full certificate thumbprint from your Windows certificate store'
$gateway = Read-Host 'Exact approved HTTPS gateway origin, without enrollment token'
$timestamp = Read-Host 'Trusted HTTPS RFC3161 timestamp service URL'
.\tools\sign_windows_enrollment.ps1 `
  -InputFile '.\private\unsigned-enrollment.exe' `
  -OutputFile '.\private\signed-enrollment.exe' `
  -Thumbprint $thumbprint `
  -GatewayOrigin $gateway `
  -TimestampUrl $timestamp
```

The helper validates the **approved binary-prefix SHA-256**, final trailer bounds, requested gateway origin, certificate's actual `Robo Universal` name, Code Signing EKU, dates and private-key availability. It signs a private staged copy with SHA-256 plus an HTTPS RFC3161 timestamp, then requires both `signtool verify /pa /all` and `Get-AuthenticodeSignature` to accept it for the requested certificate. Only then is a new output file published. It does not overwrite the input, export keys, auto-select a certificate, change trust roots, or suppress warnings. The `/sha1` option selects the certificate by its Windows thumbprint; **the signature digest is SHA-256**, not SHA-1.

4. Transfer only the final verified artifact to its intended user through a secure channel, within the enrollment's 15-minute validity window. Do not append data, alter resources, compress/patch its PE contents or replace its enrollment after signing. Consumed installers remain single-use.
5. On disposable real Windows machines, independently check the displayed publisher, chain, timestamp, SmartScreen behavior, native UI, enrollment, DPAPI, NTFS and sign-in startup. A valid signature is not a guarantee of SmartScreen reputation or a malware-free application.

**This helper has been syntax-checked only, not run with a real Windows certificate or native SignTool.** It is not an automatic per-download signing service. Production deployment still needs a secured signing service/queue or equivalent operational integration, key-access controls, artifact verification, latency/cost/rate limits and an explicit fail-closed rollout. No certificate/private-key host settings or shell-command hooks have been added to the addon.

## Linux detached-signature workflow — prepared, not automatic

Linux shell scripts do not have Windows' Verified Publisher dialog. A GnuPG key may be labeled Robo Universal, but identity is established by independently authenticating and pinning its **full fingerprint**, not by trusting a key's display name.

On a dedicated signing machine with an existing private signing key/agent:

```bash
bash tools/sign_linux_enrollment.sh /private/enrollment.sh FULL_KEY_FINGERPRINT
```

The helper requires the original Robo Universal developer header, a full key fingerprint, a regular readable file and a new output path. It creates `enrollment.sh.asc`, verifies it against the exact script bytes, and refuses to overwrite an existing signature. It never accepts a private key or password as a command argument or installs a trust root. Distribute the **matching** script/signature securely; obtain the public key and confirm its full fingerprint through a separate trusted channel.

The recipient must download both files **without executing the script**, verify the pinned key identity and detached signature, and only then run:

```bash
gpg --verify enrollment.sh.asc enrollment.sh
# Proceed only after successful verification AND independent fingerprint/identity checking.
bash enrollment.sh
```

A successful `gpg --verify` alone does not prove the key belongs to Robo Universal. The script does not infer whether the caller performed detached verification; its embedded unsigned/default-distribution notice is not changed into a self-asserted trusted status. The addon does not currently publish `.asc` endpoints or operate an online signing service. Each changing personalized script needs its own matching signature. Enrollment tokens expire and must not be committed or embedded in general release archives.

## Validation boundaries

Portable Go tests cover unsigned trailers, real PE certificate-table layout, all alignment lengths, malformed/overlapping tables and certificate-data confusion. A separate temporary test identity named **LAYOUT TEST ONLY - NOT TRUSTED** exercised an actual osslsigncode signature and SHA-256 payload-tamper rejection; verification explicitly used its test certificate, not the system's trusted publisher store. A separate disposable GnuPG test identity exercised the Linux helper and tamper rejection. These temporary keys/artifacts are not distributed and establish **no** public trust or Robo Universal identity.

Native Windows execution, actual CA-issued publisher display and production signing-service integration remain **NOT RUN / NOT CONFIGURED**.
