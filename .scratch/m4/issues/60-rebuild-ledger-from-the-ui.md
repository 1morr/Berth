# 60 — 重裝之後在畫面上把帳本找回來

**Status:** done

**Blocked by:** None — can start immediately

**讀:** `docs/research/usability-audit-2026-10-07.md` §2 E6、§3 S4（重裝那兩列）、§8 P1-5、P2-8；截圖 s4-31～s4-36；README〈帳本重建（`berth rebuild-ledger`）〉；plan 中 Reconciler 與 `rebuild-ledger` 的章節；CONTEXT.md 的 Ledger Entry、Unmanaged、Claim

## 為什麼（審計實跑）

- 搬走 Berth 的 DB 再跑精靈（或 DB 遺失）之後：
  - 作品頁同時寫「在 Jellyfin 看」和「還沒有任何檔案入庫」，下載頁全空；使用者很可能重複下載同一部。
  - 唯一的提示是待處理裡一件「無主 torrent」，按鈕「認領並建立下載」沒說會做什麼。
  - 完成頁寫「跳過：沒有」，沒有任何地方提 `rebuild-ledger`。
- 精靈完成後打開 `/setup` 會靜默導向設定頁；「怎麼重跑精靈」沒有任何文件寫。
- 使用者拍板 E6：偵測到媒體庫裡有 Berth 不認得的檔案時，在畫面上給「從媒體庫重建帳本」。它就是 `rebuild-ledger`：只加不刪、可以重跑。

## 做什麼

1. **先 `/impeccable shape`**：決定提示出現在哪裡。候選位置是完成頁、待處理、作品頁。要寫出「為什麼會這樣」：重裝或 DB 遺失。
2. 偵測：Route 的寫入目標底下有 Berth 帳本不認得的媒體檔時，給出提示與一顆「從媒體庫重建帳本」。
   - 按下去跑與 CLI 同一個命令（`@command`，標成可重跑、不刪任何東西），完成後說找回了幾個、有幾個變成 Unmanaged。
3. 作品頁的「檔案與版本」在帳本空、但 Jellyfin 有這部時，說「Jellyfin 有，Berth 的紀錄裡沒有」，並連到重建。不要寫「還沒有任何檔案入庫」。
4. 「無主 torrent」的按鈕說清楚會做什麼（認領成一筆下載、之後照常入庫或對帳）。
5. 精靈完成後打開 `/setup`：導向設定頁時說一句「精靈已經完成，之後的修改在這裡」；README 寫明重跑精靈的方法與後果（要重貼 TMDB key、帳本靠重建）。

## 驗收

- [x] 整合測試：帳本空、媒體庫有 Berth 命名的檔案時偵測得到；重建之後作品頁的檔案列回來；再按一次不重複（冪等）
- [x] vitest：提示、作品頁的新文案、無主 torrent 的說明（zh-Hant 與 en）
- [x] 實跑：入庫一部 → 搬走 DB → 重跑精靈 → 按重建 → 作品頁與下載頁的樣子，附截圖
- [x] 全部檢查、test、前端 e2e 綠燈；README、plan、CHANGELOG 同步；progress.md 記一行

## Comments

- 2026-10-08 shape：`.scratch/m4/ledger-rebuild-shape.md`（使用者不在場，照審計 E6 與既有文件自己拍板，理由寫在每一條）。
- 2026-10-08 實跑（**演練伺服器，不是真的四個容器**）：沒有真的 TMDB key，而入庫與重建都要 TMDB 的作品資料，真容器走不到
  「入庫一部」；協調者給的「頁 5 在 DB 標成已驗證」只過得了精靈。改用 `scripts/fake_setup_server.py` 的兩個新情境，
  `--config-root C:/Users/Roxy/berth-t60/fake`、port 48383（repo 外，跑完已停）。DB 真的搬走、磁碟上的硬鏈接與 complete
  的來源是真的、精靈與重建走的是產品程式碼；TMDB、Jellyfin、qBittorrent 是替身。截圖在 `C:/Users/Roxy/berth-t60/t60-*.png`。
  - `reinstall-before`：作品頁送單到 Anime，入庫 5 個檔案（t60-1）。停掉、把 `berth.db*` 搬走。
  - `reinstall`：精靈從頁 1 起（Jellyfin 已初始化 → 用管理員登入；頁 3「3 個已建立」要自己按；TMDB key 重貼）。
    完成頁 Route 卡片之後出現「媒體庫裡有 5 個檔案不在 Berth 的帳本上…」與按鈕（t60-2）；按下「找回 5 個檔案」（t60-3）。
  - 第二輪（同樣搬走 DB 再起）完成精靈但先不按：作品頁「檔案與版本」說「Jellyfin 有這部，Berth 的紀錄裡沒有」並連到待處理
    （t60-7）；待處理最上面是提示、下面是無主 torrent 與那一行說明（t60-8）；按重建「找回 5 個檔案」，偵測變 0，
    `POST` 再按一次 `known 5、claimed 0`（t60-9）。下載頁是空的——重建只長帳本、不造 Job；認領那個 torrent（選 SPY×FAMILY）
    之後下載頁 1 筆「已入庫」（t60-10），作品頁仍是 5 個檔案、磁碟上仍是 5 個（沒有另鏈一份），待處理清空（t60-11）。
  - 390 寬的提示沒有橫向捲動（t60-13）；精靈跑完打開 `/setup` → `/settings/jellyfin?from=setup` 多一句（t60-14）。
  - 替身的限制：TMDB 收任何 key；`LibraryJellyfin` 照磁碟列出作品（真的 Jellyfin 靠自己的掃描）；無主 torrent 是重啟時
    照 complete 底下的東西掛回去的；只演了劇集（審計重現的是電影，電影那條路徑沒有實跑）。截圖裡作品頁的文案是
    code-review 改寫之前的版本（「多半是重裝過…」），改寫後的文案由 vitest 守著。
- 2026-10-08 code-review（兩軸 opus）處理掉的：作品頁那一句原本寫「多半是重裝過」——Berth 之前就在 Jellyfin 的作品也長這樣，
  改成說兩種可能、不推測；有 Route 讀不到時結果仍說「帳本已經認得每一個檔案」；`read_ledger_gap` 在迴圈裡每個檔案重算一次
  聯集；`said` 改名 `earlier_detail`；shape 的「lede 下」對齊實作（lede 之前）；補後端 409 `reconcile_running` 的測試與
  英文 vitest（一般使用者那一句、讀不到時不說「每一個都認得」）。
- 未處理（判斷題，留著）：
  - 偵測在 async 端點裡同步走訪媒體庫（`fs.files_under`），與對帳、CLI 同一個做法；待處理頁每次清單失效都會再走一次。
    大媒體庫上真的慢了再換成 `to_thread` 或快取，現在沒有量測。
  - `POST` 只在開始時看對帳有沒有在跑，重建途中 04:00 那一輪仍可能開始；兩邊替同一個檔案各開一件會撞鍵。要做得等
    `ReconcileRunner` 有一把能讓重建一起拿的鎖，超出這張票。
  - `_library_files` 與 `reconcile._ask_library` 走的是同一種走訪，但對帳要分「沒掛上」與「讀到一半」兩種說法與 log，
    沒有收成一支。
  - `rebuild_ledger` 標 `Effect.REVERSIBLE` 而沒有反向命令：它只加帳本列與 Issue、冪等，與其他「可逆但回去不是單一命令」
    的同一類；M5 做登錄表時若要分出「冪等的寫入」再改。
  - `LedgerGapOut.unknown` 是計數、名字不像；演練腳本 `_restore_services` 的 slug 清單寫了兩次。
