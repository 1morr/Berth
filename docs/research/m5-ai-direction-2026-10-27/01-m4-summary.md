# M4 盤點（唯讀，2026-10-27）

資料來源：`docs/progress.md`（前 20 行與 Session 紀錄）、`.scratch/m4/issues/` 全部 140 張 .md 票、`docs/plan.md` §11.5、`git log`。狀態：`v0.3.0`（2026-10-24）已發，`main` 乾淨。票 01–120 是修補段（`v0.2.9` 結案），121–133 是 M4 本體（巡檢與通知）。

## 1. M4 做了什麼

**資料完整性與下載管線（修補段早期）**
- SQLite 寫鎖順序、不握寫交易打網路（交易紀律進 plan §3.3）— 票 01
- Jellyfin 回驗：「還在認」不算不一致、版本重排只推同一集 — 票 02
- 大批送單防護：磁碟門檻扣在途量、`submit_failed` 暫時失敗有限重試 — 票 03
- `GET /jobs` 分頁與四組篩選、SSE 失效合併 — 票 04
- 第一批審核證據夠強時跳過 — 票 11；自動綁定重試與季名不進搜尋詞 — 票 14
- 刪除進行中的單留下 incomplete 的處理 — 票 74；log 不出現 URL 上的秘密 — 票 76；搜尋結果不交出 Prowlarr key — 票 79

**精靈與既有服務接入（票數最多，約 05–10、15–47、59–68、72、73、80、81、101–104、118–119）**
- 既有服務不被改動（判定規則、qBittorrent 全域偏好）— 票 05
- 精靈 Jellyfin 優先、每個服務手動選「套件內 / 既有」、一服務一頁 — 票 06、15、43
- 套件內 qBittorrent / Prowlarr 的介面登入、帳密只問一次 — 票 07、26、27、40
- 媒體庫與路徑頁、掛載檢查涵蓋每一台、補法照原因給且可照抄 — 票 08、19、25、46、63
- 擁有者鎖定、擁有者成立前空窗、接管只管 Berth 擁有的物件（寫入白名單閘門）— 票 18、28、33、66
- 不寫全域鍵、未完成目錄只開在 Berth 分類 — 票 22、32；設定不再互相蓋掉 — 票 23
- Prowlarr：只支援 Prowlarr、可不用、推薦站一鍵加入 — 票 37、44、61、67、73
- 錯誤分層（人話在上、原文收進細節）、只存驗過的憑證 — 票 21、45
- 換台時列出留下的東西與說明 — 票 47、65、102；換台後 Route 自動重查 — 票 59
- 既有 Jellyfin 新建媒體庫、掃描只刷新 Berth 的庫 — 票 62、64；rootless Docker 提示 — 票 72
- 導覽、文案與跨頁一致性收尾 — 票 30、31、35、68、80、103、104、118、119

**部署與發版**
- compose 容器名前綴與 host-gateway — 票 16；第一個可拉的 image — 票 41
- 原生 Linux / Unraid 實跑 — 票 42、55；`v0.2.0` 公開 beta — 票 56–58
- 只用 compose 檔加 `.env` 部署（`v0.2.1`）— 票 71；部署連結指最新 Release — 票 97
- README 英文為主、中文另一份、「為什麼有 Berth」— 票 57、75
- 真服務 e2e 與試跑環境並存 — 票 34；從 UI 重建帳本 — 票 60

**搜尋**
- 年份與類型篩、「片名＋年份」搜得到 — 票 49、69；探索搜尋年份不拆 — 票 85
- 結果說出被收起來的原因並可篩選 — 票 83；自己打關鍵字分對得上 / 對不上 — 票 83b、83c
- 搜尋前選名字與季、記住選擇 — 票 84、84b
- 逾時不算整台連不上、略過預算用完的站 — 票 114、77；刪除站點請求預算 — 票 107

**RSS**
- RSS 頁以作品呈現 Series、完結自動收起 — 票 13；預覽首輪與 CI 衛生 — 票 13b、13c、121b
- Feed 的 Route 必填、被 RSS 綁著的 Route 放行要擋刪除要拒 — 票 105、115
- 每個 Feed 可設輪詢間隔、新增時設排除條件、被排除的 Item 可「仍然下載」— 票 109、110、111
- 排除條件分清全域與內建、說「標題規則」— 票 113、117
- 作品頁 Mikan「只下載現有的」、作品頁下載段 — 票 112、12
- 完結停止每日補漏並補最後一次、補漏看得見 — 票 108、116；Bangumi 頁每輪只讀一次 — 票 82
- 季號明寫集號跨季累計、「拒絕」改叫「重新規劃」— 票 106；多季包標題 — 票 48；括號標題 — 票 98

**健康檢查與頁面一致性**
- 健康頁 Route 探測講真話 — 票 50；作品頁 Jellyfin 狀態與媒體庫頁一致 — 票 51
- 錯誤訊息說對原因（500 / 401 / 逾時）— 票 89、90、99

**簡化審計與清理**
- 審計清單 — 票 86；分岔小修 — 票 87；後端 / 前端「同一件事一份」— 票 91、92
- 清死碼並加 knip 閘門 — 票 93；刪前端沒讀的 API 欄位 — 票 94；刪沒用途的 DB 欄位 — 票 95
- 文件與註解偏差、文件與實作不符 — 票 96、53；code-review 遺留 — 票 54、99–100、71b

**通知（M4 本體）**
- Discord bot 私訊實測（brief 定案不做 webhook）— 票 121
- `notifications` 待送表、`adapters/notify/`、「可以看了」tracer — 票 123
- Berth 對外網址（`BerthSettings.public_url`）與深連結 — 票 124
- 每人通知設定（`users.notify_kinds_json`）、照媒體庫權限送、同作品 5 分鐘合併 — 票 125
- 「正在下載」每輪每部作品一則，人按的不通知本人 — 票 126
- 「有 N 件等你處理」（含 Issue 新增，只送管理員）— 票 127；忽略的 Issue 條件持續不重開 — 票 122
- 管道故障：24 小時放棄、401 / 429 / 5xx 退避、收件人不可達、健康頁「通知」卡 — 票 128

**巡檢與週報**
- `sweeper` 迴圈：卡住的 Job、放太久的提醒 — 票 129
- RSS 巡檢：缺集、同一集意外多份、一直失敗的 Feed（`rss_feeds.last_error` 拆欄）— 票 130
- 週報 `services.weekly`（每週一筆、`/weekly/{id}`、摘要推給訂閱的管理員）— 票 131

**收尾與驗收**
- M4 UI 收尾（七條遺留逐條重現）— 票 132
- 驗收：`tests/e2e/test_5_m4_notify.py` + 假 Discord 容器，CI e2e 28 passed — 票 133

## 2. 票的狀態異常

比對方式：用 shell 掃 140 張票的 `Status:` 行與 `- [ ]` / `- [x]`；再逐票以 `git log -- <票檔>` 查歷史（每張都至少有「開票」與「完成」兩個 commit，且完成 commit 的日期、主題與 progress.md 的 session 紀錄對得上），並比對 `merge: ticket NN` 與 `ticket NN` 字樣。M4 修補段多半直接在 main 上提交，沒有 merge commit（66 個 `merge: ticket` 橫跨 M0–M4，M4 本體 121–133 幾乎都有），所以無 merge 不算異常。

- (a) `Status:` 不是 `done`：**無**，140 張全是 `done`。
- (c) 與 git log 對不上：**無**。票 01–133 每個號碼都有票檔（含 b/c 變體）；沒有「標 done 但無 commit」或「有 commit 但沒標 done」。

(b) 有未勾的驗收條件（3 條，2 張票）：

| 票號 | 檔名 | 問題類型 | 細節 | 判斷 |
| --- | --- | --- | --- | --- |
| 119 | `119-wizard-page4-bundled-layout.md` | (b) 未勾 | 「1280 寬頁 4 套件內沒有一欄比另一欄高出 1.5 倍視窗高（前端 e2e 量高度）」，已劃掉 | 只是格式問題：協調者 2026-10-20 決定不採用桌機 `aside` 版面並撤回（Comments〈協調者決定〉）。順帶：其餘已勾的條目在撤回前寫成，Comments 已註明部分段落不適用 |
| 120 | `120-existing-address-prefill.md` | (b) 未勾 | 「頁 1 是既有 `http://nas.local:8096` 時，頁 2 / 頁 4 位址 placeholder…」 | 只是格式問題：已劃掉，「不做（使用者 2026-10-20）」 |
| 120 | 同上 | (b) 未勾 | 「頁 1 是套件內或沒有可用位址時，placeholder 照舊是 `EXAMPLE_ADDRESS`」 | 只是格式問題：同上，已劃掉 |

票 120 的檔名（`existing-address-prefill`）與標題內容（「Route 刪除被拒的中文排版」）不符：票被改題後沒改檔名，progress.md 也用新標題。

異常票數：真的有缺 0 張；格式／留痕 2 張（119、120）。

## 3. 其他注意到的事

- **M5 曾做過又被整個撤銷**：本機分支 `backup/m5-attempt-1-20261024`（領先 main 85 個 commit，含 `merge: ticket 16 m5-acceptance`）、`backup/main-before-reset-20261025`（領先 87）、`bk`（領先 1，2026-10-26 的 `docs(research): add agent runtime references and ai provider survey`）都沒併進 main。`main` 現在回到 `v0.3.0` 加 progress 記錄。progress.md 的 Session 紀錄與「里程碑與閱讀指引」表沒有提到 M5 嘗試被撤銷這件事（表中沒有 M5 列，最後一列是 M4）；`docs/research/m5-ai-direction-2026-10-27/` 目前只有本檔。`origin/backup/main-before-reset-20261025` 也在遠端。
- `docs/progress.md` 2026-10-21 結案審查寫「沒打勾的 4 條」，現在 M4 只有 3 條（119 一條、120 兩條）；第 4 條推測在 M0–M3 的票，本次沒查。
- `CHANGELOG.md` 底部的連結定義過期：`[Unreleased]` 指向 `compare/v0.2.1...HEAD`，且只有 `[0.2.1]`、`[0.2.0]`、`[0.1.0]` 三條連結，沒有 `[0.3.0]`、`[0.2.2]`–`[0.2.9]` 的。標題 `## [0.3.0] - 2026-10-24` 本身存在。
- progress.md 寫 `v0.3.0` 含「六個 migration」：repo 數得出 M4 本體的六個（`d5e8a2c7f914`、`f4b8d2e6a913`、`e3a9c6f1b207`、`b7d1e5a3c820`、`c5f2a8e4d917`、`a8c3f6e1d254`），對得上。`v0.2.9..v0.3.0` 是 61 個 commit（progress 寫 60），差一個無關緊要。
- progress.md 任務指示說 1640 行，實際 1627 行，不影響內容。
- 待使用者決定（plan §11.5 與 progress.md 2026-10-24 紀錄）：重試用完或永久失敗的 `submit_failed`、`import_failed`、`stalled` 沒有 Issue、不進「等你處理」（票 129）；M5 切不切、拆票時的設計題。
- 已知不排里程碑的缺陷（plan §11.5）：週報「產生於」用瀏覽器時區而週界線用容器時區，不同時會差一天（票 131 → 132，P2）；390 寬 `Notice` 被擠到約 140px（票 130 → 132，P2）；週報入庫清單前後端排序語言不一致（P3）。
- 檢查過存在、與 progress / plan 一致：`services/sweep.py`、`weekly.py`、`recipients.py`、`deeplink.py`、`waiting.py`、`downloading.py`、`notify.py`、`adapters/notify/`、`tests/e2e/test_5_m4_notify.py`、`tests/e2e/discord.py`、`scripts/experiments/sweep_loop_lag.py`、`tests/unit/test_command_marks.py`、`web/src/weekly/`、`api/weekly`、五個票內點名的 migration 檔、tag `v0.3.0`（在 main 上）。
