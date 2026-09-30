# 22 — 未完成目錄只開在 Berth 的分類上：不動使用者的全域設定、磁碟門檻量對位置

**Status:** done

**Blocked by:** 19（兩張都改 `routes.py` 的 category 那一步；19 先把 qBittorrent 的探針放進 Route 檢查）

**讀:** `docs/research/wizard-review-2026-09-30.md`；brief §16.4（既有 qBittorrent 不寫全域）、§20.2（`createCategory` 的
`downloadPath`，4.4.0 起）、§4.1；plan §8.1、§9.3〈qBittorrent〉；票 03（磁碟門檻算在途量）、05 的 `## Comments`

## 為什麼（2026-09-30 精靈審查，使用者回報）

- 接既有 qBittorrent 時出現「這台 qBittorrent 沒有啟用未完成目錄。不阻擋——但下載中的檔案會直接寫在完成目錄裡，Berth 比較難
  分辨哪些已經下載完」，唯一的按鈕是「確認，不改任何設定」。使用者問：為什麼不讓人選擇要不要開？
- 不改全域是對的（票 05、brief §16.4；*arr 也只建自己的分類、全域只讀）。但**這句警告的理由不成立**：Berth 判斷下載完成看的是
  qBittorrent 回報的 progress / completion_on / state（`berth/services/downloads.py:17`），與未完成目錄無關。**真正的影響**是：
  - 下載中的半成品出現在 Berth 的分類目錄（complete 那一側）裡。
  - 送單前的磁碟門檻量的是 `/data/torrent/incomplete`（`berth/services/jobs.py:984`），既有 qBittorrent 根本不寫那裡——量錯目錄。
- qBittorrent 的分類可以帶自己的 `downloadPath`（Web API 2.8.4 / 4.4.0 起，brief §20.2 已查證），目前註明不用
  （`berth/adapters/qbittorrent/client.py:123`）。用它就能**只替 Berth 的分類開未完成目錄**，不必問使用者要不要改全域。
- 偏好表的「套件內的建議值」`/data/torrent/incomplete` 對沒掛 `/data` 的那一台是錯的建議（19 會先把沒掛 `/data` 的擋下來）。
- brief §16.4 寫「incomplete / complete 根目錄可設定」，但 `PathSettings`（`berth/models/setting.py:102-111`）沒有任何 API、UI 或
  環境變數能改，實際寫死 `/data/torrent/...`——文件與程式不符。

## 做什麼

1. **實測 `downloadPath`**：對 qBittorrent 4.4.5 與 5.2.3（`scripts/experiments/compose.yml` 已有這兩版）確認：建分類時帶
   `downloadPathEnabled`＋`downloadPath`、autoTMM 開著的 torrent 下載中落在 `downloadPath`、完成後搬到 `savePath`；全域
   `temp_path_enabled=false` 時也成立。腳本留 `scripts/experiments/`，結論補 brief §20.2。
2. **Berth 的分類一律帶 `downloadPath = /data/torrent/incomplete/<slug>`**：既有與套件內同一條路（套件內是否還需要寫全域
   `temp_path`，依第 1 點的結果決定；能不寫就不寫，少一條偏好差異）。已存在的 Berth 分類：`downloadPath` 不同時照
   現在的 category 衝突規則處理，不覆寫。
3. **磁碟門檻**：量 Berth 分類實際寫入的那個檔案系統（`downloadPath` 所在），在途量照票 03。
4. **警告**：刪掉「未完成目錄」那句；既有 qBittorrent 的偏好表只留真正影響 Berth 的鍵（或整張收起），不再列套件內建議值。
5. **brief §16.4**：改成「根目錄固定在 `/data/torrent/{incomplete,complete}`」，與程式一致；progress.md「偏差與決定」記一行。

## 驗收

- [x] 實測腳本在 `scripts/experiments/`，4.4.5 與 5.2.3 的結果寫進 brief §20.2
- [x] 整合測試：Berth 建的分類帶 `downloadPath`；既有 qBittorrent 的全域偏好一個都沒被寫（雙向：套件內若仍寫全域，測試寫明哪幾個鍵）
- [x] 整合測試：磁碟門檻量的是 `downloadPath` 所在的位置
- [x] vitest：既有 qBittorrent 頁不再出現未完成目錄的警告
- [x] 對 `berth-existing/good` 的 `ok-qbittorrent`（`:48080`）實跑：頁 3 建分類後，qBittorrent 的分類設定看得到下載路徑；全域
      「Keep incomplete torrents in」維持原樣
- [x] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈

## Comments

**2026-09-30 實作（session 紀錄在 progress.md）**

- 實測：`scripts/experiments/qbittorrent_category_download_path.py` 對 4.4.5 與 5.2.3 各跑一輪（一台做種的 5.2.3、
  private torrent、關 DHT / LSD / PeX），兩版結論相同，表在 brief §20.2：分類的 `downloadPath` 在全域關著時照樣生效、
  全域開著時分類的贏、完成後搬到 `savePath`；讀回的鍵是 `download_path`（沒設 5.2.3 是 `null`、4.4.5 缺鍵，停用是
  `false`）。**套件內因此不再寫全域 `temp_path` / `temp_path_enabled`**，建議鍵五個變三個。
- **解讀（偏差，記在 progress.md）**：已存在的 Berth 分類「`downloadPath` 不同」只算**有設而且不同**；沒設或停用的
  （票 22 之前建的）不算衝突、不改，Route 檢查那一行說「downloads follow qBittorrent's global setting」。字面讀
  「沒設也是不同」會讓升級後每一條 Route 都紅，而 4.4 的 WebUI 改不了分類的未完成目錄。代價：那種舊分類下載中仍照
  全域設定落腳，磁碟門檻量的是 Route 的未完成目錄（或 incomplete 根目錄），不是它實際寫的地方。**待使用者確認**。
- 磁碟門檻：Route 的未完成目錄還沒建（Route 檢查沒跑過）時量 incomplete 根目錄，兩者都不在才「量不到、照送」——
  完整 pytest 抓到的：原本直接量不存在的目錄，門檻在那段時間等於沒有。
- 實跑（容器裡從工作樹 build 的 Berth，`DATA_ROOT` 指 berth-trial/data，接 ok-jellyfin 與 ok-qbittorrent）：頁 2
  沒有偏好表、沒有未完成目錄警告；頁 3 TV Shows 6/6 綠，但沿用了 ok-qbittorrent 上 berth-trial 留下的舊分類
  `berth-tv-shows`（沒有 `download_path`，沒被改）；精靈跑完後在設定頁替 TV Shows 再建一條 Route，分類
  `berth-tv-shows-2` 讀回 `download_path: /data/torrent/incomplete/tv-shows-2`；全域 `temp_path_enabled` 維持
  `false`、conf 的 `TempPath` 沒變。用完已還原：刪 `berth-tv-shows-2`、移除 TV Shows 多加的 `/data/library/tv-shows`、
  刪 data 裡建出來的空目錄、容器與 image；ok-jellyfin 的 API key 沒有新增（沿用 berth-trial 的那一把，未動）。
- code-review 已處理：brief §16.4「根目錄可設定」與 §16.3 表格仍寫 temp path、CHANGELOG 的類名（`QbittorrentOut`）、
  services 層改叫 `incomplete_path_of` / `_Planned.incomplete_path`（避開 `RouteCheck.DOWNLOAD_PATH` 一詞兩義；adapter
  層照 qBittorrent 叫 `download_path`）。**未處理**：`save_path_of` 與 `incomplete_path_of` 同形（兩個一行函式，
  合併反而要多一個參數說是哪一側）；文案裡的「三個鍵」寫死在幾處（`drift.clean` 等），數量再變時要一起改；
  vitest 的「不再出現未完成目錄警告」斷言在 i18n 鍵刪掉之後不會紅，真正守著的是 API 型別少了 `temp_path_warning`
  （typecheck）與 `diffs` 為空時沒有表格那一條；對舊分類與衝突分類 `_category` 也會建未完成目錄（空目錄，影響小）。
