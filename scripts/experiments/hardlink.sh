#!/bin/sh
# Berth 硬鏈接能力檢查（brief §4.4、§20.6；plan §9.5）。
#
# 在單一掛載根底下真的做一次 link()，因為 st_dev 相同只是必要條件：
# 同一個檔案系統掛兩次，link() 仍會回 EXDEV（brief §20.2）。
#
# 用法（宿主上）：
#   docker run --rm -v /srv/berth/data:/data -v "$PWD/scripts/experiments:/exp:ro" \
#       alpine:3 sh /exp/hardlink.sh /data
# 用法（NAS 上，直接跑）：
#   sh hardlink.sh /volume1/berth/data
#
# 成功回 0 並印出 dev / inode / nlink；失敗回 1。
set -eu

ROOT="${1:-/data}"
SRC_DIR="$ROOT/torrent/complete/berth-hardlink-check"
DST_DIR="$ROOT/library/berth-hardlink-check"
SRC="$SRC_DIR/probe.bin"
DST="$DST_DIR/probe.bin"

cleanup() {
    rm -rf "$SRC_DIR" "$DST_DIR"
}
trap cleanup EXIT

mkdir -p "$SRC_DIR" "$DST_DIR"
date > "$SRC"

echo "root:       $ROOT"
echo "filesystem: $(awk -v r="$ROOT" '$2 == r {print $3, $4}' /proc/mounts 2>/dev/null || echo unknown)"
echo "mount line: $(df -P "$ROOT" | tail -1)"

if ! ln "$SRC" "$DST" 2>/tmp/berth-ln-err; then
    echo "FAIL: ln 失敗 -> $(cat /tmp/berth-ln-err)"
    echo "      單一掛載根是硬鏈接的前提；/data 底下不可以再掛第二個 volume。"
    exit 1
fi

src_stat=$(stat -c '%d %i %h' "$SRC")
dst_stat=$(stat -c '%d %i %h' "$DST")
echo "src:        dev/ino/nlink = $src_stat"
echo "dst:        dev/ino/nlink = $dst_stat"

if [ "$src_stat" != "$dst_stat" ]; then
    echo "FAIL: 兩端的 dev/ino/nlink 不一致，不是真的硬鏈接"
    exit 1
fi

nlink=$(stat -c '%h' "$SRC")
if [ "$nlink" -lt 2 ]; then
    echo "FAIL: nlink=$nlink，link() 沒有真的建立第二個名字"
    exit 1
fi

echo "PASS: 同一個 inode、nlink=$nlink"
