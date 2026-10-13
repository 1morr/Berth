# 61 — 「不用 Prowlarr」：沒有索引站也是一個正常狀態

**Status:** done

**Blocked by:** None — can start immediately

**讀:** `docs/research/usability-audit-2026-10-07.md` §2 E3、§3 S4（移除 Prowlarr 那一列）、§8 P1-2、P2-7；截圖 s4-19、s4-20、s4-21；brief §16.3 Prowlarr 列、§16.4；plan §9.3 頁 4 的「之後再說」；M4 票 20

## 為什麼（審計實跑）

- 照 README 移除 Prowlarr（拿掉 profile、`docker compose stop prowlarr`）之後：
  - 健康頁 BTH 4 一直「阻擋」，修正只教你把它起回來。
  - 設定頁同時顯示舊的綠色「連線測試通過」與紅色「讀不到站清單」。
  - 作品頁搜尋露出原始字串 `GET /api/v1/indexer: host does not resolve`。
- Prowlarr 回來之後，要等到下一輪 5 分鐘的健康檢查才恢復。
- 精靈頁 4 的「之後再說」只在精靈裡有；精靈完成後，沒有「我不用它了」的出口。
- 使用者拍板 E3：設定 → Prowlarr 加「不用 Prowlarr」；健康不再檢查；搜尋改說明可以走 RSS。Seerr 的 Radarr / Sonarr 也是可以不加的。

## 做什麼

1. **先 `/impeccable shape`** 設定頁的這個開關與它關掉時各頁的樣子。
2. 設定 → Prowlarr 可以選「不用 Prowlarr」（與精靈頁 4 的「之後再說」是同一個狀態，`@command`、可逆）。選了之後：
   - 健康頁 BTH 4 顯示「沒有使用」，不算阻擋；
   - 作品頁的搜尋區說「沒有接索引站：可以接 Prowlarr，或用 RSS 訂閱」，附連結；
   - 精靈完成照頁序再驗時，這一格算完成。
3. 設定頁的連線狀態列帶上測試時間，連線失敗時不再顯示舊的綠色「通過」。
4. 搜尋失敗的訊息用人話，原始字串收進技術細節（照票 21 的分層）。
5. 健康檢查連不上 Prowlarr 時，下一輪提早重試（例如 30 秒），不要等滿 5 分鐘；套件內 Qbittorrent、Jellyfin 是否套用同一規則，在票的 Comments 寫明理由。

## 驗收

- [x] 整合測試（雙向）：不用 Prowlarr 時健康不阻擋、搜尋回「沒有接索引站」；接回去之後恢復；完成再驗算這一格完成
- [x] vitest：設定頁開關、作品頁的說明、錯誤分層（zh-Hant 與 en）
- [x] 實跑：停掉 Prowlarr → 選不用 → 健康頁、作品頁截圖；再接回來
- [x] 全部檢查、test、前端 e2e 綠燈；brief §16.3、plan §9.3、README、CHANGELOG 同步；progress.md 記一行

## Comments

- **提早重測只給 Prowlarr**（做什麼第 5 點要寫明的理由）：Jellyfin 與 qBittorrent 牽動 Route 那一項——單獨重測讓服務那一格
  先轉綠、Route 卻要等下一整輪才跟上，畫面自相矛盾；要一致就得每 30 秒重跑整輪，Route 檢查每次都在媒體庫寫探測檔。
  qBittorrent 另有硬傷：帳密不對時每 30 秒重試登入，會把它的 IP 封鎖時間一直重算（brief §20.2）；它停掉時下載迴圈本來就
  每 5–30 秒在問、健康頁的「下載迴圈」那一格先看得到。Prowlarr 沒有其他項依賴它，重測只是 `/ping` 與讀站數。
- code-review 未處理的發現：
  - Standards（判斷題）：`JellyfinConnection` 與 `ServiceChoice.TestLine` 的「過時」與「測試於」各寫一次——兩者本來就各畫各的狀態列
    （票 78 起 Jellyfin 是唯讀摘要），合併要先把兩種版面收成一個元件，不在本票範圍。`IndexerNotice` 對 `problem` 的分支越來越多，
    可改對照表，留給下一個碰它的票。
  - Spec：`skip_indexers` 回傳前照舊 `read_indexer_status`，選「不用」那一下仍會問 Prowlarr 一次（錯誤吞掉、DNS 解不到時立刻回）；
    改它會動到精靈頁 4「之後再說」之後的畫面，沒有 repro 說它慢，不改。演練 server 的 `/demo/prowlarr/stop` 讓搜尋一併失敗
    （`degraded` 情境的搜尋也跟著變），是刻意的：停掉的 Prowlarr 搜不到東西。
