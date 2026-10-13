#!/bin/sh
# M4 票 63：既有服務已經把別的資料夾掛在 /data 底下（Unraid CA 的 jellyfin 模板預設 /data/tvshows、
# /data/movies），再照 Berth 的補法多掛一條 DATA_ROOT:/data，會怎樣（unraid-trial-2026-10-08 §6 U6）。
#
# 回答三件事：
#   1. 兩條都在時，容器裡 /data 與 /data/tvshows 各是哪一個宿主資料夾（-v 的先後換過來再跑一次）。
#   2. Docker 會不會在 DATA_ROOT 裡建出 tvshows 這個掛載點（宿主上多一個空資料夾）。
#   3. 子掛載蓋住的那一格裡，Berth 的資料夾原本有的東西容器裡還看不看得到。
#
# 用法（宿主上，要 docker 與 alpine image；Git Bash 要 MSYS_NO_PATHCONV=1）：
#   sh scripts/experiments/nested_data_mount.sh
#
# 只印 stdout，臨時資料夾跑完刪掉。結論在 docs/design-brief.md §20.14（M4 票 63）。
set -eu

WORK="$(mktemp -d "${TMPDIR:-/tmp}/berth-nested.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
DATA="$WORK/berth-data"
TV="$WORK/their-tv"
mkdir -p "$DATA/library" "$TV"
echo "berth" > "$DATA/library/from-berth.txt"
echo "theirs" > "$TV/episode.txt"

run() {
    docker run --rm "$@" alpine:latest sh -c \
        'echo "  /data: $(ls /data | tr "\n" " ")"; echo "  /data/tvshows: $(ls /data/tvshows | tr "\n" " ")"'
}

echo "1. -v DATA:/data first, then -v TV:/data/tvshows"
run -v "$DATA:/data" -v "$TV:/data/tvshows"
echo "   host DATA after: $(ls "$DATA" | tr '\n' ' ')"

rm -rf "$DATA/tvshows"
echo "2. -v TV:/data/tvshows first, then -v DATA:/data"
run -v "$TV:/data/tvshows" -v "$DATA:/data"
echo "   host DATA after: $(ls "$DATA" | tr '\n' ' ')"

echo "3. DATA already has a tvshows folder of its own"
rm -rf "$DATA/tvshows"
mkdir -p "$DATA/tvshows"
echo "berth" > "$DATA/tvshows/hidden.txt"
run -v "$DATA:/data" -v "$TV:/data/tvshows"
echo "   host DATA/tvshows after: $(ls "$DATA/tvshows" | tr '\n' ' ')"
