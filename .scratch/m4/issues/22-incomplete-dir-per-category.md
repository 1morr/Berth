# 22 — 未完成目錄只開在 Berth 的分類上：不動使用者的全域設定、磁碟門檻量對位置

**Status:** ready-for-agent

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

- [ ] 實測腳本在 `scripts/experiments/`，4.4.5 與 5.2.3 的結果寫進 brief §20.2
- [ ] 整合測試：Berth 建的分類帶 `downloadPath`；既有 qBittorrent 的全域偏好一個都沒被寫（雙向：套件內若仍寫全域，測試寫明哪幾個鍵）
- [ ] 整合測試：磁碟門檻量的是 `downloadPath` 所在的位置
- [ ] vitest：既有 qBittorrent 頁不再出現未完成目錄的警告
- [ ] 對 `berth-existing/good` 的 `ok-qbittorrent`（`:48080`）實跑：頁 3 建分類後，qBittorrent 的分類設定看得到下載路徑；全域
      「Keep incomplete torrents in」維持原樣
- [ ] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈
