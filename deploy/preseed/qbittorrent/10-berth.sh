#!/usr/bin/env bash
# A linuxserver custom-cont-init.d script: runs before the qBittorrent service starts.
#
# It only adds what Berth cannot get in without: since 4.6.1 the random first-start password is
# printed only to the container log, which Berth cannot read (it has no docker socket), so Berth
# reaches the API through a no-password whitelist. The password, save path, temp path and autoTMM
# are never preset here; the wizard sets the web UI login through the API and leaves the rest alone.
#
# Why "add missing keys" rather than "write the file if it does not exist": the image's own
# init-qbittorrent-config runs first and has already copied /defaults/qBittorrent.conf into /config,
# so the file always exists. Keys that already have a value are never touched, so settings changed
# in the web UI are not overwritten.
set -euo pipefail

CONF="${BERTH_QBITTORRENT_CONF:-/config/qBittorrent/qBittorrent.conf}"

# The whitelist holds only berth's address, not the whole compose subnet: Docker Desktop rewrites
# the source address of traffic coming in through published ports to the gateway (172.28.0.1),
# which is inside the subnet, so whitelisting the subnet would let anyone on the LAN use
# qBittorrent's API without a password. The address comes from BERTH_IP in the compose file.
if [[ -z "${BERTH_IP:-}" ]]; then
    echo "[berth-preseed] BERTH_IP is not set; it comes from the compose file" >&2
    exit 1
fi

# `WebUI\ServerDomains` is not set here: the image defaults to `*`, which already passes the Host
# check; pinning it to `qbittorrent` would lock users out of the web UI at localhost:8080.
KEYS=(
    'WebUI\AuthSubnetWhitelistEnabled=true'
    "WebUI\\AuthSubnetWhitelist=${BERTH_IP}/32"
)

log() {
    echo "[berth-preseed] $*"
}

if [[ ! -f "${CONF}" ]]; then
    echo "[berth-preseed] ${CONF} not found; the image init should have copied it" >&2
    exit 1
fi

# Match the whole key at the start of the line: `WebUI\AuthSubnetWhitelist` is a prefix of
# `…WhitelistEnabled`.
has_key() {
    BERTH_PRESEED_KEY="$1" awk '
        index($0, ENVIRON["BERTH_PRESEED_KEY"] "=") == 1 { found = 1; exit }
        END { exit !found }
    ' "${CONF}"
}

missing=()
for entry in "${KEYS[@]}"; do
    has_key "${entry%%=*}" || missing+=("${entry}")
done

if [[ ${#missing[@]} -eq 0 ]]; then
    log "already configured, leaving ${CONF} untouched"
    exit 0
fi

tmp="$(mktemp)"
trap 'rm -f "${tmp}"' EXIT

# The values contain backslashes, which awk -v would read as escapes, so pass them via ENVIRON.
BERTH_PRESEED_LINES="$(printf '%s\n' "${missing[@]}")" awk '
    { print }
    !inserted && /^\[Preferences\]/ { print ENVIRON["BERTH_PRESEED_LINES"]; inserted = 1 }
    END { if (!inserted) { print "[Preferences]"; print ENVIRON["BERTH_PRESEED_LINES"] } }
' "${CONF}" >"${tmp}"

# Overwrite rather than mv, keeping the inode, owner and mode (the image's init already chowned it).
cat "${tmp}" >"${CONF}"

log "added to ${CONF}: ${missing[*]}"
