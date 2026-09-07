#!/bin/sh
# 容器入口：以 root 起，把 image 內的 berth 使用者對到 PUID / PGID，讓掛進來的目錄寫得
# 進去，再降權執行實際的指令（plan §9.1）。與 linuxserver 的三個容器共用同一組 PUID /
# PGID / UMASK，硬鏈接兩端的檔案擁有者才會一致。
set -eu

PUID="${PUID:-1000}"
PGID="${PGID:-1000}"

umask "${UMASK:-022}"

if [ "$(id -u)" -ne 0 ]; then
    # 已經被 `docker run --user` 或 compose 的 `user:` 降過權，照使用者的意思跑。
    exec "$@"
fi

if [ "$(getent group berth | cut -d: -f3)" != "${PGID}" ]; then
    # --non-unique：PUID / PGID 撞到 image 內既有的 id 時照樣套用，宿主端的擁有者才是對的。
    groupmod --non-unique --gid "${PGID}" berth
fi

if [ "$(id -u berth)" != "${PUID}" ]; then
    usermod --non-unique --uid "${PUID}" berth
fi

# $1 是目標路徑，其餘的參數原樣交給 chown。
take_ownership() {
    target="$1"
    shift
    if ! chown "$@" berth:berth "${target}" 2>/dev/null; then
        # Windows 的 bind mount 沒有 Linux 擁有者的概念，chown 失敗不影響寫入。
        echo "[berth] cannot change ownership of ${target}; continuing" >&2
    fi
}

# /config 全是 Berth 自己的檔案（資料庫、log），換過 PUID 也要跟著換，所以遞迴。
take_ownership /config -R

# /data 是使用者的媒體根，原則上不碰：可能是 NAS 上別的帳號擁有的共用目錄，改擁有者是
# 沒人要的意外。空目錄是唯一的例外 —— 那代表 Docker 剛替 bind mount 建好目錄（Linux 上
# 是 root:root），不接手的話 Berth 連第一層目錄都建不出來。
if [ -z "$(ls -A /data 2>/dev/null)" ]; then
    take_ownership berth:berth /data
fi

exec setpriv --reuid "${PUID}" --regid "${PGID}" --init-groups "$@"
