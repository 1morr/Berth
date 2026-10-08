#!/bin/sh
# rootless Docker 上 Berth 碰到的兩件事（M4 票 42，docs/research/linux-trial-2026-10-09.md §4、§5）：
#
# 1. 容器裡的 uid 落到宿主上是誰：容器 root 與容器 uid 1000 各寫一個檔，看宿主上的擁有者。
#    rootful 是 0 與 1000；rootless 是跑 dockerd 的帳號與 subuid（例如 100999）。
# 2. 從 `berth` 容器連得到宿主上的哪些位址：`host.docker.internal`（compose 的 host-gateway）與
#    宿主的區網 IP，各打一個監聽 0.0.0.0 與一個只監聽 127.0.0.1 的程式，加上你給的既有服務 port。
#
# 用法（宿主上、Berth 那一套已經 `up -d`，容器名照預設 `berth`）：
#   sh scripts/experiments/rootless_host_probe.sh 192.168.50.99 18096 18080
# 第一個參數是宿主的區網 IP，其餘是要多打的 port（既有 Jellyfin、qBittorrent……）。
# 需要宿主上有 python3（起兩個暫時的 http 服務）；只讀，結束時收掉自己起的東西。
set -eu

LAN_IP="${1:?usage: rootless_host_probe.sh <host LAN IP> [port...]}"
shift
PROBE_ANY=18901
PROBE_LOOPBACK=18902

WORK="$(mktemp -d)"
cleanup() {
    [ -n "${PID_ANY:-}" ] && kill "$PID_ANY" 2>/dev/null || true
    [ -n "${PID_LOOPBACK:-}" ] && kill "$PID_LOOPBACK" 2>/dev/null || true
    docker run --rm -v "$WORK":/w alpine rm -rf /w/owner-check >/dev/null 2>&1 || true
    rm -rf "$WORK"
}
trap cleanup EXIT

echo "== docker"
echo "context: $(docker context show)"
docker info --format 'security options: {{.SecurityOptions}}'

echo "== 1. who owns what a container writes"
docker run --rm -v "$WORK":/w alpine sh -c \
    'mkdir /w/owner-check && touch /w/owner-check/as-root && touch /w/owner-check/as-1000 && chown 1000:1000 /w/owner-check/as-1000'
ls -ln "$WORK/owner-check" | sed 1d

echo "== 2. what the berth container can reach"
(cd "$WORK" && exec python3 -m http.server "$PROBE_ANY" --bind 0.0.0.0 >/dev/null 2>&1) &
PID_ANY=$!
(cd "$WORK" && exec python3 -m http.server "$PROBE_LOOPBACK" --bind 127.0.0.1 >/dev/null 2>&1) &
PID_LOOPBACK=$!
sleep 1

docker exec berth getent hosts host.docker.internal || echo "host.docker.internal: not resolvable"
docker exec berth python -c '
import sys, urllib.error, urllib.request
lan_ip, ports = sys.argv[1], sys.argv[2:]
for host in ("host.docker.internal", lan_ip):
    for port in ports:
        url = f"http://{host}:{port}/"
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                print(f"{url:45} {response.status}")
        except urllib.error.HTTPError as error:
            print(f"{url:45} HTTP {error.code} (reached)")
        except Exception as error:
            print(f"{url:45} {type(error).__name__}: {error}")
' "$LAN_IP" "$PROBE_ANY" "$PROBE_LOOPBACK" "$@"
echo "($PROBE_ANY listens on 0.0.0.0, $PROBE_LOOPBACK on 127.0.0.1 only)"
