# 05 — 既有服務不被改動：判定規則與 qBittorrent 全域偏好

**Status:** done

**Blocked by:** None — can start immediately（排在 06 之前：06 會重寫第 1 步，這張先把會毀資料的那條堵住）

**讀:** plan §9.3 第 2、4、6 步、§9.5；brief §16.3、§16.4、§19 2026-09-26「既有服務不被改動」那一列；progress.md 2026-09-26「試跑回饋」那一行

## 為什麼

2026-09-26 在 `berth-lab`（`C:\Users\Roxy\berth-lab`，模擬「另一份 compose 起的舊服務」）走精靈實測：

- **舊 Prowlarr 被判成套件內，登入被覆寫**。使用者自己的 Prowlarr（表單登入 `homeprowlarr`、還沒加索引站）在第 2 步
  填位址與 API key 按「測試連線」後判成「套件內」（理由 `no_indexers`），第 6 步加站時 Berth 以第 1 步的帳密
  `PUT config/host`，登入帳號被改成 `labgate` 並重啟——畫面一路寫著「你自己的既有服務不會被改動」。
  成因：`_verdict_prowlarr` / `_verdict_qbittorrent`（`berth/services/setup.py:447-475`）同時用在 compose 主機名
  的探測與使用者填的位址，判定只看「沒有索引站」「免密可進」。qBittorrent 同一條路：開了「本機 / 子網免驗證」的
  舊 qBittorrent 會被判成套件內、WebUI 密碼被寫（推論，這張票要 repro）。
- **舊 qBittorrent 的全域偏好被改**。既有 qBittorrent 在第 4 步「套用這 5 個鍵」把全域 `save_path` 從
  `/data/downloads` 改成 `/data/torrent/complete`、`temp_path` 也換掉——使用者之後不經 Berth 加的 torrent 全部
  跑去 Berth 的目錄。brief §16.4 寫的是「用自己的 `berth-*` category 與新的 save path」「temp path 未啟用只給警告」，
  實作對既有服務也寫全域鍵。Sonarr / Radarr 對下載器只用分類，不碰全域偏好。

## 做什麼

1. **先 repro**：整合測試兩條——使用者填的 Prowlarr 位址沒有索引站、使用者填的 qBittorrent 位址免密可進，
   都不得判成套件內，之後的步驟不得寫它們的帳密（Fake 上斷言沒有 `config/host` PUT / `setPreferences` 帶密碼）。
2. **判定規則**：只有 compose 主機名（`services.clients.bundled_targets`）上探到的才可能是套件內；使用者填的
   位址一律既有。Jellyfin 例外要想清楚並寫進 plan §9.3：使用者填的位址上是一台還沒跑過初始精靈的 Jellyfin，
   代建管理員不會蓋掉任何人的帳號——06 會重寫這一步，這裡只定規則。
3. **既有 qBittorrent 不寫全域鍵**：第 4 步對既有服務只列建議與現值、說明影響，不提供「套用」全域的
   `save_path` / `temp_path` / `temp_path_enabled`；Berth 的路徑全靠分類（建立時帶 save path）與逐個 torrent 的
   `autoTMM=true`。Route 檢查第 2 條（`download_path`）對既有服務改看分類回報的路徑，不看全域 `save_path`
   （plan §9.5 那一條原本寫「全域那一條在第 4 步就已經被設成 Berth 的 complete 根目錄」，一併改）。
   `auto_tmm_enabled`、`category_changed_tmm_enabled` 同樣只對套件內寫，既有的逐個 torrent 指定。
4. 已經被這條 bug 寫過的安裝沒有 migration：只有被判錯的那一台受影響，而判定結果存在 `settings.setup`；
   在 CHANGELOG 說明「曾把既有 Prowlarr / qBittorrent 判成套件內的安裝，請在該服務自己的介面確認登入」。

## 驗收

- [x] 兩條 repro 修前紅、修後綠（貼輸出）；雙向：compose 主機名上的空 Prowlarr / 免密 qBittorrent 仍判套件內
- [x] 既有 qBittorrent 走完第 4、5 步後全域 `save_path` / `temp_path` 不變，送單照樣落在 Berth 的分類路徑（整合測試）
- [x] `berth-lab/reset.sh existing` 之後用 playwright 走一次精靈：舊 Prowlarr 的登入帳號、舊 qBittorrent 的預設下載路徑都沒變
- [x] plan §9.3、§9.5 與 brief §16.3、§16.4 同步；CHANGELOG 一條
- [x] lint、type、test 綠燈

## Comments

- 2026-09-27 實作（session 紀錄見 progress.md）。repro 修前的輸出：`test_a_typed_prowlarr_without_indexers_is_existing_and_keeps_its_login`、`test_a_typed_password_free_qbittorrent_is_existing_and_gets_no_password` 都在判定紅——`At index 0 diff: <ServiceOrigin.BUNDLED: 'bundled'> != <ServiceOrigin.EXISTING: 'existing'>`（`2 failed, 2 passed`）；修後 `7 passed`（含 code-review 補的 `connect_indexer` 那一條與第 4、5 步、漂移兩條）。
- code-review 沒處理的：
  - `qbittorrent_target` 與 `indexer._target` 在沒有判定時預設 `BUNDLED`。正常流程裡第 4、6 步之前一定有判定，寫不出失效條件，沒改；判定缺失、位址卻已存的舊資料才會走到。
  - 測試的 `tests/integration/factories.COMPOSE` 手寫了 qBittorrent 的預設 port 8080；`verdict()` 小工具在三個測試檔各有一份。
  - `QbittorrentStep.tsx` 裡 `writes ? … : …` 出現七次；既有那一台的畫面長大時再拆成自己的元件。
- `berth-lab`：`existing/docker-compose.yml` 的 Berth image 改成這一張 build 的 `berth:m4-05`；`CREDENTIALS.md` 的 Prowlarr API key 是 reset 之前那一把（reset 之後 Prowlarr 重新產生，要到它的「設定 → 一般」抄）；精靈第 1 步的帳密記在 `.creds.env` 的 `BERTH_*`。
