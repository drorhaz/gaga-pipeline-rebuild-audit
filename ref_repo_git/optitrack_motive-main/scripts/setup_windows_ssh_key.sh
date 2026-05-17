#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/setup_windows_ssh_key.sh <username> <host>

Creates a fresh OptiTrack Motive SSH key for this computer and installs the
public key on a Windows OpenSSH host.

Arguments:
  username  Windows SSH username, for example Admin
  host      Windows SSH host or IP, for example kyushu

Environment:
  SSH_PASSWORD         Password for non-interactive setup; requires expect
  SSH_KEY_DIR          Directory for the generated key, default ~/.ssh
  SSH_CONFIG_PATH      Config file to update, default ~/.ssh/config
  WIN_AUTH_KEYS_PATH   Windows authorized_keys path override

Example:
  bash scripts/setup_windows_ssh_key.sh Admin kyushu
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -ne 2 ]]; then
  usage >&2
  exit 2
fi

USER_NAME="$1"
HOST="$2"

if [[ "${USER_NAME}${HOST}" =~ [[:space:]] ]]; then
  echo "Username and host must not contain whitespace." >&2
  exit 2
fi

TARGET="${USER_NAME}@${HOST}"
SSH_DIR="${SSH_KEY_DIR:-${HOME}/.ssh}"
CONFIG_PATH="${SSH_CONFIG_PATH:-${SSH_DIR}/config}"
AUTH_PATH="${WIN_AUTH_KEYS_PATH:-}"
PASSWORD="${SSH_PASSWORD:-}"

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

need_cmd awk
need_cmd base64
need_cmd hostname
need_cmd iconv
need_cmd ssh
need_cmd ssh-keygen
need_cmd tr

mkdir -p "${SSH_DIR}"
chmod 700 "${SSH_DIR}" 2>/dev/null || true

STAMP="$(date -u '+%Y%m%dT%H%M%SZ')"
LOCAL_HOST="$(hostname -s 2>/dev/null || hostname || echo unknown)"
SAFE_USER="$(printf '%s' "${USER_NAME}" | tr -c '[:alnum:]._-' '_')"
SAFE_HOST="$(printf '%s' "${HOST}" | tr -c '[:alnum:]._-' '_')"
KEY_PATH="${SSH_DIR}/optitrack_motive_${SAFE_USER}_${SAFE_HOST}_${STAMP}_$$_ed25519"
KEY_COMMENT="optitrack_motive:${TARGET}:${LOCAL_HOST}:${STAMP}"

echo "Generating fresh SSH key at ${KEY_PATH}"
ssh-keygen -t ed25519 -a 64 -f "${KEY_PATH}" -N "" -C "${KEY_COMMENT}" >/dev/null

PUBKEY_PATH="${KEY_PATH}.pub"
PUBKEY_CONTENT="$(<"${PUBKEY_PATH}")"
if [[ -z "${PUBKEY_CONTENT}" ]]; then
  echo "Public key is empty: ${PUBKEY_PATH}" >&2
  exit 1
fi

AUTH_PATH_ESCAPED="${AUTH_PATH//\'/\'\'}"
PUBKEY_ESCAPED="${PUBKEY_CONTENT//\'/\'\'}"

PS_SCRIPT=$(cat <<PS
\$ErrorActionPreference = 'Stop'
\$ProgressPreference = 'SilentlyContinue'
\$overrideAuth = '${AUTH_PATH_ESCAPED}'
\$currentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
\$principal = [Security.Principal.WindowsPrincipal]::new(\$currentIdentity)
\$isAdmin = \$principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
\$userSid = \$currentIdentity.User.Value
\$auth = \$overrideAuth
if ([string]::IsNullOrWhiteSpace(\$auth)) {
  if (\$isAdmin) {
    \$auth = 'C:\\ProgramData\\ssh\\administrators_authorized_keys'
  } else {
    \$auth = Join-Path \$HOME '.ssh\\authorized_keys'
  }
}
\$dir = Split-Path \$auth
if (!(Test-Path \$dir)) { New-Item -ItemType Directory -Force -Path \$dir | Out-Null }
if (!(Test-Path \$auth)) { New-Item -ItemType File -Force -Path \$auth | Out-Null }
\$null = icacls \$dir /inheritance:r
\$null = icacls \$auth /inheritance:r
if (\$isAdmin) {
  \$null = icacls \$auth /grant "*S-1-5-32-544:F"
  \$null = icacls \$auth /grant "*S-1-5-18:F"
} else {
  \$null = icacls \$dir /grant "*\$userSid:F"
  \$null = icacls \$dir /grant "*S-1-5-18:F"
  \$null = icacls \$auth /grant "*\$userSid:F"
  \$null = icacls \$auth /grant "*S-1-5-18:F"
}
\$key = '${PUBKEY_ESCAPED}'
if (-not (Select-String -SimpleMatch -Quiet -Path \$auth -Pattern \$key)) {
  Add-Content -Path \$auth -Value \$key
}
Write-Output \$auth
PS
)

ENCODED_PS="$(printf '%s' "${PS_SCRIPT}" | iconv -t UTF-16LE | base64 | tr -d '\n')"

echo "Installing public key to ${TARGET}"
if [[ -n "${PASSWORD}" ]]; then
  need_cmd expect
  WINDOWS_SSH_PASSWORD="${PASSWORD}" expect -f - "${TARGET}" "${ENCODED_PS}" <<'EXPECT'
set timeout -1
set password $env(WINDOWS_SSH_PASSWORD)
set target [lindex $argv 0]
set encoded_ps [lindex $argv 1]

log_user 0
spawn ssh -o StrictHostKeyChecking=accept-new -o PubkeyAuthentication=no $target powershell -NoProfile -NonInteractive -EncodedCommand $encoded_ps
expect {
  -re {(?i)are you sure you want to continue connecting} {
    send -- "yes\r"
    exp_continue
  }
  -re {(?i)password:} {
    send -- "$password\r"
    exp_continue
  }
  eof {
    set wait_status [wait]
    exit [lindex $wait_status 3]
  }
}
EXPECT
  unset PASSWORD
else
  ssh -o StrictHostKeyChecking=accept-new -o PubkeyAuthentication=no "${TARGET}" powershell -NoProfile -NonInteractive -EncodedCommand "${ENCODED_PS}"
fi

update_ssh_config() {
  local config_dir marker_start marker_end tmp

  config_dir="$(dirname "${CONFIG_PATH}")"
  marker_start="# >>> optitrack_motive ${TARGET} >>>"
  marker_end="# <<< optitrack_motive ${TARGET} <<<"

  mkdir -p "${config_dir}"
  touch "${CONFIG_PATH}"
  chmod 600 "${CONFIG_PATH}" 2>/dev/null || true

  tmp="$(mktemp "${CONFIG_PATH}.tmp.XXXXXX")"
  awk -v start="${marker_start}" -v end="${marker_end}" '
    $0 == start { skip = 1; next }
    $0 == end { skip = 0; next }
    !skip { print }
  ' "${CONFIG_PATH}" > "${tmp}"

  {
    printf '%s\n' "${marker_start}"
    printf '# Generated by optitrack_motive/scripts/setup_windows_ssh_key.sh\n'
    printf 'Host %s\n' "${HOST}"
    printf '  HostName %s\n' "${HOST}"
    printf '  User %s\n' "${USER_NAME}"
    printf '  IdentityFile %s\n' "${KEY_PATH}"
    printf '  IdentitiesOnly yes\n'
    printf '%s\n\n' "${marker_end}"
    cat "${tmp}"
  } > "${CONFIG_PATH}"

  rm -f "${tmp}"
  chmod 600 "${CONFIG_PATH}" 2>/dev/null || true
}

echo "Updating SSH config at ${CONFIG_PATH}"
update_ssh_config

echo "Verifying passwordless SSH access via ${HOST}."
if SSH_TEST_OUTPUT=$(ssh -F "${CONFIG_PATH}" -o BatchMode=yes -o PasswordAuthentication=no -o ConnectTimeout=10 "${HOST}" "whoami" 2>&1); then
  echo "Done. SSH key login is now in place as ${SSH_TEST_OUTPUT}."
  echo "Key: ${KEY_PATH}"
else
  echo "SSH key test failed: ${SSH_TEST_OUTPUT}" >&2
  exit 1
fi
