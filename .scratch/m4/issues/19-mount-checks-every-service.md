# 19 — 掛載檢查涵蓋每一台：qBittorrent 看不看得到、補法指對容器、404 說出原因

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** `docs/research/wizard-review-2026-09-30.md`；brief §16.4（同主機、同容器路徑、不做 remote path mapping）、
§4.4、§20.2；plan §9.5〈媒體庫與路徑〉；票 08 的 `## Comments`

## 為什麼（2026-09-30 精靈審查，接 `berth-existing/broken` 實測）

- **既有 qBittorrent 沒掛 `/data` 看不出來。** `bad-qbittorrent`（只掛 `/downloads`）接上後，頁 3 選 Movies 時
  `download_path`「qBittorrent 的路徑 Berth 看得到 `/data/torrent/complete/movies`」綠燈——那個目錄是 category
  那一步 Berth 自己先 `mkdir` 的（`berth/services/routes.py:885`），檢查只在 Berth 容器裡 `stat`（`:910-913`），
  既有那一台必過，正是同一段註解（`:869-871`）警告的「什麼都沒驗到」。硬鏈接測試也只在 Berth 裡做。實際下載會寫進
  qBittorrent 容器自己的檔案層，要到入庫才出事。
- **補法指錯容器。** 既有 Jellyfin 的媒體庫在 `/movies`（`bad-jellyfin-elsewhere`）：`library_path` 紅，原文
  `/movies is not visible from the Berth container ([Errno 2] …)`，手動步驟開頭「berth 容器少了這條路徑的掛載」並附
  `berth: volumes: - ${DATA_ROOT}:/data`（`web/src/components/routeChecks.ts:62-63` 對兩條檢查固定給 berth）。Berth 早就有
  `/data`，照做沒用；該改的是 Jellyfin。
- **「新的 Berth 路徑」失敗時說不出原因。** Berth 先在自己容器 `mkdir /data/library/movies`，再請 Jellyfin
  `POST /Library/VirtualFolders/Paths`；Jellyfin 沒掛 `/data` → 404，Jellyfin log 寫 `The path does not exist`，Berth 只留
  `POST /Library/VirtualFolders/Paths: 404`（`berth/adapters/http.py:149-150`）。補法還建議「在 Jellyfin 自己的媒體庫設定裡
  手動加這一條」（同樣會失敗），連結用的是 `http://host.docker.internal:58097/...`，瀏覽器開不了。只試了 Movies 就停，沒說
  TV Shows 沒做；失敗後留下空目錄。
- **頁 3 的媒體庫清單是頁 1 的快照**（`routes.py:179-204` 不現查，只有加 Berth 路徑會刷新 `jellyfin.py:428`）：使用者在
  Jellyfin 改了掛載或路徑，精靈裡看不到。
- **既有模式的寫入目標預設選「你既有的資料夾」**，與旁邊「不想讓它寫進你既有的資料夾…」的說明方向相反。
- **`library_path` 要求媒體庫的每一條路徑 Berth 都看得到**（`routes.py:922-938`）：brief §16.4 的做法是舊路徑不動、
  加一條 Berth 路徑，但寫入目標選了新的 Berth 路徑時，舊的 `/movies` 仍讓這一項紅。要定：只驗寫入目標，還是全部都驗
  （Berth 讀 Inventory 需不需要看得到舊路徑——查 `services/inventory.py` 的用法再定）。

## 做什麼

1. **qBittorrent 那一側的探針**（先 `mattpocock-skills:prototype`，腳本留 `scripts/experiments/`，結論寫 brief §20.2）：
   候選是 Berth 在分類的 save path 寫一個小檔、做成 .torrent、以 `skip_checking=false`＋該 save path 加進 qBittorrent，
   看它校驗後的進度是不是 100%，再連同 torrent 移除（不刪檔以外的東西）；不可行再退到「全域 `save_path` 與分類路徑在
   不在 qBittorrent 回報的同一棵 `/data` 底下」的推斷。選定後加成 Route 檢查的一項（或併進 `download_path`），既有與
   套件內都跑。
2. **補法依失敗的那一台給**：`library_path`、`probe_visible` 失敗 → Jellyfin 的 volumes 片段；qBittorrent 探針失敗 →
   qBittorrent 的；`hardlink` 的 `EXDEV` 才是 berth 自己。套件內與既有分開寫（既有的片段是「你的那份 compose」）。
   說法沿用 TRaSH：單一 `/data` 掛載，別分開掛 `/downloads`、`/movies`。
3. **加 Berth 路徑失敗**：轉述 Jellyfin 回的原因（`The path does not exist` → 「Jellyfin 看不到 `<路徑>`：它沒掛 `/data`」）；
   拿掉「手動加」建議；連結改用瀏覽器開得了的位址（既有 Jellyfin 的 `base_url` 裡的 `host.docker.internal` 換成頁面自己的
   hostname，或不給連結）；多個媒體庫逐個試、逐個回報；失敗時把剛建的空目錄刪掉。
4. **頁 3 進頁時重讀 Jellyfin 媒體庫**（或加一顆重新讀取），不再只靠頁 1 的快照。
5. **既有模式的寫入目標預設「新的 Berth 路徑」**；使用者要寫進既有資料夾要自己選。
6. **定 `library_path` 的範圍**（上面最後一條），把決定寫進 plan §9.5；若改成只驗寫入目標，同一 commit 改 brief。

## 驗收

- [ ] 探針的 prototype 腳本在 `scripts/experiments/`，結論（含 qBittorrent 4.4.5 與 5.2.3 各自的行為）寫進 brief §20.2
- [ ] 整合測試：qBittorrent 看不到分類路徑時 Route 紅、理由指名 qBittorrent；看得到時綠（雙向）
- [ ] 前端測試：`library_path` 紅而 Jellyfin 是既有 → 片段是 Jellyfin 的；探針紅 → qBittorrent 的；`EXDEV` → berth 的
- [ ] 整合測試：加 Berth 路徑 404 時錯誤帶 Jellyfin 的原因、剛建的目錄被刪；兩個媒體庫都回報
- [ ] playwright 對 `berth-existing` 實跑：`bad-qbittorrent`（`:58081`）接上後頁 3 紅在 qBittorrent 那一項、說出它少了
      `/data`；`bad-jellyfin-elsewhere`（`:58097`）的補法指名 Jellyfin；`good/` 一路綠。附截圖或文字結果
- [ ] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈
