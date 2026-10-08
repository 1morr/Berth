# 72 — 精靈認得 rootless Docker：位址提示與寫不進去的補法

**Status:** ready-for-agent

**Blocked by:** None — can start immediately（只改文案；與 68 同一批文案，先做哪張都可以，後做的那張合併）

**讀:** `docs/research/linux-trial-2026-10-09.md` §4.2、§5.1；截圖 `m-01-page3-berth-cannot-write.jpeg`、`s2-01-page1-host-docker-internal-refused.jpeg`；brief §16.4（容器裡的 `localhost` 那一條）、§20.14「原生 Linux、rootless Docker 實跑」；`docs/guide/requirements.md`〈Rootless Docker〉、`docs/guide/existing-services.md`〈Addresses〉；`PRODUCT.md`

## 為什麼

票 42 在 rootless Docker 上實跑，精靈有兩個地方會把人帶錯：

- **位址填 `localhost` 的就地提示與測不過時的補法**（同一句，`web/src/i18n/resources.ts` 裡提到 `host.docker.internal` 的那一句，zh-Hant 與 en）先推 `host.docker.internal`。rootless 上它解得到但連不到宿主上任何東西（connection refused），只有區網 IP 會通。照第一個建議做的人會得到「Nothing answers at this address」，不知道為什麼。
- **頁 3 `berth_cannot_write` 的補法**說「讓 berth 與 qBittorrent、Jellyfin 同一組 PUID / PGID，或在宿主上把那個資料夾 chown 給那組 PUID / PGID」。rootless 上後者要 chown 成 subuid（100999），沒有 sudo 做不到，做了宿主上的帳號又寫不進去；rootless 的補法是 `PUID=0`、`PGID=0`。

Berth 在容器裡分不出自己是不是 rootless（不加 Docker socket），所以是文案問題：把 rootless 的那一條說法加進去。

## 做什麼

1. `localhost` 提示與測不過的補法：區網 IP 與 `host.docker.internal` 並列，並說 rootless Docker 上只有區網 IP 會通。
2. `berth_cannot_write` 的補法多一句：rootless Docker 填 `PUID=0`、`PGID=0`（指到 guide〈Rootless Docker〉的說法，不在畫面上貼 `docker run … chown` 那一條）。
3. zh-Hant 與 en 並列；文案照 `PRODUCT.md` 的語氣，句子不要變長到換行比原本多一行以上。

## 驗收

- [ ] 兩處文案 zh-Hant 與 en 都提到 rootless 的做法；vitest 斷言新句子出現在對應的情境（`localhost` 提示、`berth_cannot_write` 補法），未引用 i18n 鍵的閘門照樣綠
- [ ] playwright 實跑截圖：頁 1 位址填 `http://localhost:8096` 的提示、頁 3 `berth_cannot_write`（可用 `scripts/fake_setup_server.py` 的情境或本機 Docker Desktop 造一個寫不進去的 `DATA_ROOT`）
- [ ] 全部檢查（`pre-commit run --all-files`）、test 綠燈
