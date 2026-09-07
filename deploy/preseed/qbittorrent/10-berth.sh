#!/usr/bin/env bash
# linuxserver 的 custom-cont-init.d：在 qBittorrent 服務啟動前執行（plan §9.2）。
#
# 只補「沒有它 Berth 就進不去」的東西：4.6.1 起首次啟動的隨機密碼只印在容器 log，
# Berth 沒有 docker socket 讀不到，只能靠免密白名單進 API。密碼、save path、temp path、
# autoTMM 一律不預置，那些由精靈用 API 設定，看得到差異也可重按。
#
# 為什麼是「缺鍵才補」而不是 plan 原本寫的「檔案不存在才寫」：image 自己的
# init-qbittorrent-config 先跑，已經把 /defaults/qBittorrent.conf 複製進 /config，
# 所以「不存在」永遠不成立。已經有值的鍵一律不動，使用者在 WebUI 改過的設定不會被覆蓋。
set -euo pipefail

CONF="${BERTH_QBITTORRENT_CONF:-/config/qBittorrent/qBittorrent.conf}"

# 白名單只放 Berth 那一台，不是整個 compose 網段：Docker Desktop 把發佈 port 進來的
# 流量的來源位址改寫成閘道（172.28.0.1），而閘道也在網段內，開放整段等於 LAN 上任何人
# 都能免密打 qBittorrent 的 API。位址由 compose 的 BERTH_IP 傳進來，不在這裡寫死。
if [[ -z "${BERTH_IP:-}" ]]; then
    echo "[berth-preseed] BERTH_IP is not set; it comes from the compose file" >&2
    exit 1
fi

# `WebUI\ServerDomains` 不在這裡：image 的預設值是 `*`，Host 檢查本來就過得了；
# 照 plan 寫死成 `qbittorrent` 反而會讓使用者從 localhost:8080 進不了 WebUI。
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

# 鍵要在行首完整比對：`WebUI\AuthSubnetWhitelist` 是 `…WhitelistEnabled` 的前綴。
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

# 值裡有反斜線，awk 的 -v 會把它當跳脫序列，所以走 ENVIRON。
BERTH_PRESEED_LINES="$(printf '%s\n' "${missing[@]}")" awk '
    { print }
    !inserted && /^\[Preferences\]/ { print ENVIRON["BERTH_PRESEED_LINES"]; inserted = 1 }
    END { if (!inserted) { print "[Preferences]"; print ENVIRON["BERTH_PRESEED_LINES"] } }
' "${CONF}" >"${tmp}"

# 覆寫而不是 mv：保留原本的 inode、擁有者與權限（image 的 init 已經 chown 過）。
cat "${tmp}" >"${CONF}"

log "added to ${CONF}: ${missing[*]}"
