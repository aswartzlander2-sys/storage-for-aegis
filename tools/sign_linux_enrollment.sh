#!/usr/bin/env bash
# Developer-only detached signing; does not install keys, trust roots or packages.
set -euo pipefail
if [[ $# != 2 ]]; then
  printf '%s\n' 'Usage: sign_linux_enrollment.sh /private/path/enrollment.sh FULL_SIGNING_KEY_FINGERPRINT' >&2
  exit 2
fi
input=$1
fingerprint=$2
[[ $fingerprint =~ ^([A-Fa-f0-9]{40}|[A-Fa-f0-9]{64})$ ]] || { echo 'Use a full pinned signing-key fingerprint, not a developer name or short key ID.' >&2; exit 2; }
[[ -f $input && ! -L $input && -r $input ]] || { echo 'Input must be a readable regular file, not a symlink.' >&2; exit 2; }
[[ $(head -n 1 -- "$input") == '#!/usr/bin/env bash' ]] || { echo 'Select the final Linux shell enrollment download.' >&2; exit 2; }
grep -Fxq -- '# Developer: Robo Universal' "$input" || { echo 'Missing Robo Universal developer header.' >&2; exit 2; }
[[ ! -e $input.asc && ! -L $input.asc ]] || { echo 'Refusing to replace an existing signature.' >&2; exit 2; }
command -v gpg >/dev/null || { echo 'Install GnuPG on your signing machine first.' >&2; exit 2; }
umask 077
signature=$(mktemp "${input}.signing.XXXXXX")
trap 'rm -f -- "$signature"' EXIT
# A fingerprint selects an existing private signing key/agent. No secret key or
# password is accepted as a command argument, copied into the addon, or exported.
gpg --batch --yes --local-user "$fingerprint" --armor --detach-sign --output "$signature" -- "$input"
gpg --batch --verify "$signature" "$input"
# Hard-link commit is atomic and refuses a concurrently created output file.
ln -- "$signature" "$input.asc"
printf '%s\n' 'Detached signature created. Verify it with a separately trusted full key fingerprint before executing the script.'
