# M4 盤點與 M5 起的 AI 方向（2026-10-27）

開 M5 前的盤點與規劃，階段一的交付：只有報告與提案，**不改 brief / plan、不拆票**。使用者核可後才進階段二（prototype）。

原始筆記與來源在同名資料夾 [`m5-ai-direction-2026-10-27/`](m5-ai-direction-2026-10-27/)，本檔只放結論；每節標出出處。

| 檔 | 內容 |
| --- | --- |
| `00-prior-m5-attempt.md` | 上一次 M5（已撤銷）做了什麼、教訓、`bk` 分支研究的摘要 |
| `01-m4-summary.md` | M4 做了什麼、票的狀態 |
| `02-leftovers-m0-m3.md` | M0–M3 票 Comments 的遺留項（417 條） |
| `03-leftovers-m4-and-deviations.md` | M4 票 Comments 與 progress.md「偏差與決定」的遺留項（85 條） |
| `04-health.md`、`health-screens/` | 全部檢查、test、主流程實走 |
| `05-human-touchpoints.md` | 所有需要人的點、命令標記與登錄表現況、通知與前端殼 |
| `06-agent-architecture.md` | claw 類專案、agent loop SDK、MCP、串流 UI、Discord、自己做的難處 |
| `07-guardrails-injection-observability.md` | 消耗防護、prompt injection、可觀測性與價格 |
| `08-scenario-data-sources.md` | TMDB / AniList / Bangumi / 網路搜尋、Re:Zero 實例、情境可行性 |

---

## 0. 先說一件盤點時才發現的事：M5 已經做過一次又撤銷了

`progress.md` 沒記，但 git 裡有（`00-prior-m5-attempt.md`）：

- `backup/m5-attempt-1-20261024`：85 個 commit、20 張票、驗收票 16 做完。內容是把 M5–M7 重排成「接管開關 + 側面板」，實作了命令標記補齊、`Registry`、Anthropic 與 OpenAI 相容兩種 provider（httpx 直打）、`ai_calls` 用量記帳、對話核心（固定工具清單、10 輪上限）、SSE 側面板、結果卡、Proposal 確認卡、RSS 訂閱與搜尋送單兩種寫入工具、用量頁、AI 活動頁。DeepSeek 真 key 兩種格式實跑過；Anthropic 官方端點沒實測。
- 2026-10-24 兩個 revert 把 main 退回 v0.3.0（`31024a8b`「undo milestone 5 to redo it from its plan」、`64e29c23` 連規劃也退掉）。**撤銷理由沒有寫在任何地方。**
- `bk`：2026-10-26 寫的 `claw-references.md` 與 `ai-provider-and-tools.md`，傾向 pydantic-ai（deferred tools 的確認形狀）或 Anthropic SDK 薄 loop，不用 Claude Agent SDK。

這次的研究把它們當成既有資料讀過、沿用其中查證過的事實，並在結論處標出沿用了什麼。**撤銷的理由會影響這次怎麼做，列在拍板清單第 1 條。**

順帶：被撤銷的那一輪裡有三個與 AI 無關的測試修正（`69291d2d` fake-ip DNS、`70423b2f` knip 探測目錄的 symlink、`952dc733` + `a55078ae` RSS 測試的時間炸彈），跟著被退掉了——這就是第 4 節 main 現在紅燈的原因。

---

## 階段一 A：M4 盤點

### A1. M4 做了什麼

依功能分組，一行一個功能（細節與更多票號在 `01-m4-summary.md` §1）。票 01–120 是「M4 之前先做的修補」（v0.2.9 結案），121–133 是 M4 本體（v0.3.0）。

**資料完整性與下載管線**
- SQLite 寫鎖順序、不握寫交易打網路 — 票 01
- Jellyfin 回驗「還在認」不算不一致 — 票 02
- 大批送單防護（磁碟門檻扣在途量、`submit_failed` 有限重試）— 票 03
- `GET /jobs` 分頁與篩選 — 票 04；第一批審核證據夠強時跳過 — 票 11；自動綁定重試 — 票 14
- 刪除進行中的單、log 不洩秘密、搜尋結果不交出 Prowlarr key — 票 74、76、79

**精靈與既有服務接入**（票數最多）
- 既有服務不被改動、只動 Berth 擁有的物件 — 票 05、18、28、33、66
- 每個服務手動選套件內 / 既有、一服務一頁、帳密只問一次 — 票 06、07、15、26、27、40、43
- 掛載檢查涵蓋每一台、補法照原因給且可照抄 — 票 08、19、25、46、63
- Prowlarr 可不用、推薦站一鍵加 — 票 37、44、61、67、73
- 錯誤分層、只存驗過的憑證、換台說明留下什麼 — 票 21、45、47、59、65、102
- 既有 Jellyfin 新建媒體庫、掃描只刷 Berth 的庫、rootless 提示 — 票 62、64、72
- 導覽與文案收尾 — 票 30、31、35、68、80、103、104、118、119

**部署與發版**
- 容器名與 host-gateway、第一個可拉的 image — 票 16、41
- 原生 Linux / Unraid 實跑、v0.2.0 公開 beta — 票 42、55、56–58
- 只用 compose + `.env` 部署、連結指最新 Release — 票 71、97
- README 英文為主加中文版 — 票 57、75；真服務 e2e 隔離 — 票 34；UI 重建帳本 — 票 60

**搜尋**
- 年份與類型篩、片名＋年份 — 票 49、69、85
- 結果說出收起來的原因並可篩、自己打的關鍵字分對得上 / 對不上 — 票 83、83b、83c
- 搜尋前選名字與季 — 票 84、84b；逾時不算連不上 — 票 114；刪除站點請求預算 — 票 107

**RSS**
- 以作品呈現 Series、完結自動收起 — 票 13；預覽首輪 — 票 13b、13c、121b
- Feed 的 Route 必填、被 RSS 綁著的 Route 擋刪除 — 票 105、115
- 每 Feed 輪詢間隔、新增時設排除、被排除的可「仍然下載」— 票 109、110、111
- 排除條件分全域與內建 — 票 113、117；Mikan 只下載現有的 — 票 112
- 完結停每日補漏並補最後一次 — 票 108、116；季號跨季累計、多季包、括號標題 — 票 106、48、98

**健康檢查與頁面一致性**
- 健康頁 Route 探測講真話、作品頁與媒體庫頁的 Jellyfin 狀態一致 — 票 50、51
- 錯誤訊息說對原因 — 票 89、90、99

**簡化審計**
- 審計清單與分岔修正 — 票 86、87；後端 / 前端「同一件事一份」— 票 91、92
- 清死碼加 knip 閘門、刪沒讀的 API 欄位與沒用的 DB 欄 — 票 93、94、95；文件偏差 — 票 53、96

**通知（M4 本體）**
- Discord bot 私訊實測 — 票 121；待送表與「可以看了」tracer — 票 123；對外網址與深連結 — 票 124
- 每人通知設定、照媒體庫權限送、同作品合併 — 票 125；「正在下載」— 票 126
- 「有 N 件等你處理」— 票 127；忽略的 Issue 條件持續不重開 — 票 122；管道故障退避 — 票 128

**巡檢與週報**
- `sweeper` 每日巡檢：卡住的、放太久的 — 票 129；RSS 缺集 / 多份 / 一直失敗的 Feed — 票 130
- 週報每週存一筆並推摘要 — 票 131；UI 收尾 — 票 132；驗收（e2e 28 passed）— 票 133

### A2. 票的狀態

140 張票全是 `Status: done`；逐票以 `git log -- <票檔>` 比對，**沒有**「標 done 但沒 commit」或「有 commit 沒標 done」。沒勾的驗收條件只有兩張票，都是刻意劃掉、寫明理由的：

| 票 | 沒勾的 | 判斷 |
| --- | --- | --- |
| 119 | 1280 寬頁 4 兩欄高度差 | 協調者撤回桌機 `aside` 版面，條目作廢 |
| 120 | 兩條 placeholder 預填 | 使用者 2026-10-20 決定不做；另外票改題後檔名沒改（`existing-address-prefill` 內容是 Route 刪除被拒的排版） |

其他不一致（`01-m4-summary.md` §3）：progress.md 沒記 M5 嘗試與撤銷、里程碑表沒有 M5 的進度；CHANGELOG 底部的比較連結停在 `v0.2.1`、缺 `[0.3.0]` 等連結。

### A3. 遺留項追蹤

兩份審計合計 502 條（細表在 `02-…`、`03-…`，每條附判定與依據）：

| 範圍 | 條數 | 後續票已處理 | 仍未處理 | 已不適用 | 與 M5 相關 |
| --- | --- | --- | --- | --- | --- |
| M0 / M1 / M1.5 | 133 | 76 | 46 | 11 | 10 |
| M2 | 95 | 28 | 62 | 5 | 15 |
| M3 | 189 | 25 | 134 | 30 | 26 |
| M4 票 + progress「偏差與決定」 | 85 | 21 | 57 | 7 | 11 |
| **合計** | **502** | **150** | **299** | **53** | **62** |

「仍未處理」的 299 條**大多是**票上已結案的判斷題（命名、重複常數、P2/P3 UI 微項），M3 票 21 一張就歸類了約 90 條；**沒有一條是已知的資料損壞或安全問題**。驗證深度：M0–M1.5 逐條對過程式碼；M2、M3、M4 的風格判斷題依票歸類、標「未重驗」，行為缺陷與 M5 相關的逐條確認過。

與 M5 相關、需要動手的（合併兩份、去重後）：

| # | 遺留項 | 現況 | 依據 |
| --- | --- | --- | --- |
| R1 | 命令標記沒補完：`BEFORE_M3` 豁免 41 個模組，`services` 219 支公開 `async def` 有 139 支沒標；含 `plan_review`、`issues.resolve_issue`、`rematch`、`duplicates`、`deletion`、`jobs`、`reimport`、`routes`、`claims` | 仍未處理 | `tests/unit/test_command_marks.py`；M3 後全面審查 |
| R2 | `test_command_marks` 只認 `iscoroutinefunction`，`@asynccontextmanager` 包過的 `download_round` 不標也不紅 | 仍未處理 | M4 票 126 Comments |
| R3 | `confirm_audit(s)` 的 `inverse=review.undo_audit` 語意錯（它拆入庫、把整筆 Job 拉回 review、丟帳本列） | 仍未處理 | `berth/services/review.py:347,365`；M3 票 05 |
| R4 | `rss.poll_due`（背景迴圈入口）標 `REVERSIBLE`；`rss.delete_feed` 連帶刪 Feed Item 卻標可逆、inverse 是 `add_feed` | 仍未處理 | `berth/services/rss.py:844、670` |
| R5 | 會送出 torrent 的命令標可逆、沒有磁碟與數量閘：`rss.release_item`、`bind_series`、`poll_feed`、`downloading.add_manual_download` | 仍未處理 | `05-human-touchpoints.md` 觀察 4 |
| R6 | 設定類命令標可逆（`notify.set_bot_token`、`indexer.*`），與 brief §14「改設定永遠要人」不一致；`indexer.skip_indexers`、`search.remember_names` 的 inverse 指向自己 | 仍未處理 | 同上 |
| R7 | 「可逆但沒有單一反向命令」沒有規則：至少七支（`set_*exclusions`、`correct_series`、`confirm_series`、`correct_series_from_plan`、`subscribe_mikan`、`undo_audit`） | 仍未處理 | `02-…` §3 |
| R8 | `issues.resolve_issue` 一個函式吞 17 種 `IssueAction`，可逆性差很大（`delete_complete`、`replace_with_link`、`delete_orphan` 刪東西） | 仍未處理 | `berth/domain/enums.py` `ISSUE_ACTIONS`、`ACTION_DELETES` |
| R9 | 命令語意散在 API 層：`nudge()` 喚醒、`hub.publish`、`current_actor()`、角色判斷（`api/gate.py` 只看路徑）、例外轉 HTTP。AI 直接叫 service 會漏喚醒與權限 | 仍未處理 | `05-…` 觀察 7 |
| R10 | 核准被擋的列與 `held_proposal` 不再比對帳本，重複版本與 `span_clash` 會漏檢——AI 的結果走同一條核准路徑 | 仍未處理 | M3 票 14、14b |
| R11 | `submit_failed`（重試用完 / 永久失敗）、`import_failed`、`stalled` 沒有 Issue，不進「等你處理」；`stalled` 在 Job 頁連重試鍵都沒有 | 待使用者決定 | M4 票 129；progress.md:288 |
| R12 | 非 admin 能不能看所有人的 Job：brief §11 與 §13 說法不一 | 待使用者決定 | `03-…` L11 |
| R13 | AI 憑證進 `settings.ai` 後只靠 log 固定 INFO 避免 DEBUG 印整份 settings | 仍未處理 | `03-…` L07 |
| R14 | `system` actor 多份寫法、docstring 已預告 `ai` actor；沒有 `job_hash` 的帳本列確認或撤銷不寫 Event | 仍未處理 | `02-…` §3.2 |
| R15 | `berth/adapters/ai.py` 的 `AiPlanner` / `NullAiPlanner` 沒有呼叫端，簽名與「AI 任務」模型對不上 | 仍未處理（建議刪掉重設計） | `05-…` 觀察 9 |

### A4. 現況健康度

指令與完整輸出在 `04-health.md`；三個紅燈我在主對話重跑確認過。

| 項目 | 結果 |
| --- | --- |
| `uv run pre-commit run --all-files` | **全綠**（13 項） |
| 後端 pytest | **4339 passed、2 failed**（28 個 e2e 標記沒跑） |
| 前端 vitest | **2179 passed、4 failed**（全在 `web/gates/knip.test.ts`） |
| 真服務 e2e | **沒跑**：`tests/e2e/stack` 需要 `TMDB_API_KEY`，本機沒有 |
| CI（GitHub Actions） | **main 的 `CI` 從 2026-10-24 起是紅的**（`docs(progress): record the v0.3.0 release` 那次 push，run 40114628104）；排程 e2e 10-25、10-26 綠 |

三個紅燈的原因：

1. `tests/integration/test_rss_api.py::TestThePageFlow::test_add_poll_bind_and_see_the_jobs`——**時間炸彈**，CI 也紅在這條：fixture 的第二 cour 已全播完，Series 被判完結，輪詢結果變了（`test_rss_api.py:202`）。被撤銷的 M5 票 10b（`952dc733`、`a55078ae`）修過：把測試時鐘釘住。
2. `tests/integration/test_compose_hosts.py:103`（`SystemHostResolver().resolves("berth not a host")` 回 `True`）——本機 fake-ip DNS 把任何名字都解析成功；`69291d2d` 修過（偵測到 fake-ip 時 skip）。只在本機紅。
3. `web/gates/knip.test.ts` 4 條——測試造的暫存專案被 knip 報出三個未使用檔，真專案 knip 是 0 條；`70423b2f` 修過（探測目錄解 symlink，macOS 的 `/tmp`）。只在本機紅。

**主流程實走**（加 Feed → 搜尋 → 送單 → 入庫）：真服務起不來（缺 TMDB key），改用 `docs/development.md`〈UI 的 Fake 後端〉的 `rss` 與 `import` 情境走完。產品程式碼是真的，外部服務是替身；精靈沒走。

- 走得通：加 Mikan Feed → 立即輪詢 → 12 集自動入庫；搜尋 → 送單 → 約 2.5 分鐘入庫，作品頁出現 5 個檔案、帳本對得上；console 沒有實質 error。
- 卡住或不一致（依嚴重度）：
  1. 同一作品入庫集數三處對不上：檔案區「E01–E03」、季表「1 / 2」、媒體庫卡「1 / 3」。**可能是 Fake 的 TMDB 只有部分集已播造成，未驗證**；要對真資料再判斷是替身偽影還是口徑不一。
  2. `/rss` 有待綁定 Series 時整頁約 7300px，10 張待綁定卡排在 Feed 列與表單上面，剛加的 Feed 要捲到中段（`health-screens/01-rss-after-poll.png`）。
  3. 每一步多一次點擊：送單要點兩次（送單 → 確認送單）、`/jobs` 預設落在空的「在路上」、`/library` 預設落在空的 Movies、「入庫到」預設未指定（只有一條 Route 時也要選）。
  4. 立即輪詢沒有進行中指示；登入頁的 `/api/auth/me` 401 進 console。

### A5. 開 M5 前要先清掉的阻礙

| # | 阻礙 | 擋什麼 | 建議 |
| --- | --- | --- | --- |
| B1 | main 的 CI 紅、本機 test 有 6 條紅 | 每張票的完成標準（test 綠燈） | 把 `69291d2d`、`70423b2f`、`952dc733` + `a55078ae` 的測試修正 cherry-pick 回 main（只取測試與 `development.md` 的部分，不帶 M5 票檔）；一張小票或直接修 |
| B2 | 命令標記沒補完、標錯的、閘門漏洞（R1–R7） | 登錄表只收有標記的命令；接管開關與確認卡的邊界都靠它 | M5 第一段；補標時順便處理 R3–R7 與 R2 的閘門 |
| B3 | `resolve_issue` 不能逐動作標（R8） | Issue 的 AI 接管 | 拆成每個 `IssueAction` 一個命令，或讓標記依參數取值；建議拆 |
| B4 | 沒有統一的命令執行器（R9） | AI 工具、MCP、Discord 都要走同一條路 | 執行器承接 actor、角色、喚醒、事件推播、拒絕轉換 |
| B5 | 三種停住的 Job 沒有 Issue（R11）、非 admin 的可見範圍（R12） | AI「交給人」的出口、AI 活動與 Proposal 誰看得到 | 拍板清單第 7 條 |
| B6 | 核准路徑的帳本比對漏洞（R10） | AI 結果的驗證 | 接管開關那一段之前修 |
| B7 | 本機沒有 TMDB key、AI 的 key | e2e、prototype | 拍板清單第 9 條 |
| B8 | progress.md 沒記 M5 嘗試與撤銷 | 「文件是唯一的記憶」 | 階段二開頭補一列（附撤銷理由） |

---

## 階段一 B：M5、M6（與 M7）現在的計畫

出處：brief §6.10、§14、§17、§19；plan §11.6–§11.8。

**共同前提**（brief §14，2026-09-24 定的「AI native」與「沒有 AI 也完整可用」）：規則層 → AI → 人的三層漏斗；AI 只替人按審核頁、待處理頁上的那些按鈕；**可逆的命令通過驗證後 AI 自己做，不可逆的（刪 complete、移除 torrent、purge、改設定與 Route、忽略 Issue）永遠做成 Proposal 等人**；每種任務先影子模式、看一致率再切自動；關掉 AI 時行為與 M4 相同。

**M5 AI 核心**（plan §11.6）在做的是「背景的 AI」：
- provider（Anthropic 先做、介面留給別家）、`settings.ai`（憑證、**月預算**、各任務型別的模式）、每次呼叫記 Event、快取鍵 `torrent hash + 解析器版本 + prompt 版本`。
- 命令登錄表：每個命令登錄 pydantic 輸入、結果、拒絕理由、副作用等級、反向命令；AI 工具與 M7 的 MCP 都只從這裡來。
- `ai_tasks` 表與 `ai_worker` 迴圈：事件觸發、一件事一個任務、帶資料包與允許的工具與預算上限，結果是「已處理」或「交給人（附理由）」。
- 驗證：播出日比對、片長、Jellyfin 回驗、集存在、不撞目標、季集範圍；不通過的不套用。
- 影子模式、AI 活動頁（逐筆撤銷）、審核頁附 AI 的理由。
- 第一批任務：規則層 low 的 Plan、Unmatched 與待綁定 Series 猜作品、Series 的季號與 offset 修正、audit 確認或撤銷、三道程式檢查標出的可疑入庫。
- **驗收**：影子模式一週真實資料、一致率達標；benchmark `auto_wrong` 不升、review 比例下降；AI 不能在沒人確認下執行 `irreversible`（整合測試）；tokens 與費用看得到；關掉 AI 與 M4 相同。

**M6 Issue 與側面板**（plan §11.7）：Issue 各型別變成 AI 任務（relink、recheck、rematch 自動；刪 complete、移除 torrent 做成 Proposal）；**側面板**是每頁都開得到的對話區，工具是同一份登錄表，使用者在場時要求的可逆動作直接執行並給撤銷、不可逆的以 Proposal 卡確認。**驗收**：一件 `library_link_missing` 不經人修好；側面板「把這一集標成已看」「這部缺的集搜一下」做得到；「把這部的 complete 刪掉」停在 Proposal。

**M7 外部對話與 MCP**（plan §11.8）：M4 的 Discord 管道接上同一個核心（同一個 bot 推通知也收訊息、Proposal 是帶按鈕的訊息、身分用個人 API token 並帶角色）；登錄表包成 MCP server。**驗收**：手機收到「正在下載」、回一句「下好了通知我並標成已看」能完成；`user` 角色在外部管道與 MCP 碰到同一道門禁；Claude Code 經 MCP 查得到本週入庫。

**依賴**：M5 的登錄表與 Proposal 是 M6、M7 的地基（M6 只多任務型別與一個介面，M7 只多兩個介面）；M5 的「交給人」走 M4 的通知；M7 的 Discord 收訊息要 gateway（M4 只有 REST 私訊，brief §20.23），MCP 與外部管道要個人 API token（brief §16.2，**目前完全沒實作**）。

**和使用者這次的需求對不上的地方**：月預算上限、側面板排在 M6、「人工接管開關」沒有成為一級概念（只有各任務型別的模式）、對話 agent 只有「固定工具」沒有 skills / MCP / 壓縮 / 斜線指令、Discord 在 M7。下面 C 段逐條處理。

---

## 階段一 C：AI 方向調整

### C1. 人工接管開關

**形狀**：開關以「決定點」為單位，不以頁面為單位——同一頁有可逆與不可逆的動作。每個決定點三段：**人**（M4 行為）／**影子**（AI 寫下它會怎麼做，人照舊決定，統計一致率）／**AI**（可逆的通過驗證後直接做；不可逆的**仍是 Proposal**，差別只是 AI 先準備好建議，人一鍵確認）。這是 plan §11.6「各任務型別的模式」的延伸，與 Sonarr / Radarr 的「Unmonitored / Monitored」不同在多了影子這一段；影子的形狀在 pydantic-ai 的 deferred tools 裡是天然的（run 以「待執行的工具呼叫」結束，不執行就是影子，`06-…` §6）。

**背景任務的工具權**：背景任務不給 agent 自由呼叫工具。程式組資料包（torrent 名、檔案清單樣本、規則層的部分解析、TMDB 季集結構），模型只輸出固定 schema 的決定，程式驗證後經**同一個命令執行器**套用（`07-…` §2）。這同時是成本防護與注入防護。

逐點的接管邏輯（人工點完整清單在 `05-human-touchpoints.md` §A）：

| 決定點 | AI 接管時做什麼 | 驗證 | 永遠留給人 |
| --- | --- | --- | --- |
| 低信心 Plan（`/review`，七種 `ReviewReason`） | 改寫 Plan 的季集與分類後核准 | 集在 TMDB 存在、不撞目標、季集範圍、播出日、片長；R10 修好之後 | `target_exists` 要取代既有檔時 |
| Audit 確認 / 撤銷 | 依證據確認，或撤銷後 rematch | 同上；R3 修好之後 | — |
| Unmatched 檔案 | 指派到集或標 Extra | 同上 | 「忽略」（藏起問題）→ Proposal |
| 重複版本 | 「保留兩者」、「跳過」可自動 | — | 「取代舊版」（舊硬鏈接被換）→ Proposal |
| 第一批確認（RSS Series） | 確認或改正一集並套用到 Series（寫回 offset） | 播出日比對 | — |
| 待綁定 RSS Series | 猜作品、選 Route 後綁定 | 名字、開播日、唯一性；綁定會補舊集送單，受 C3 的數量與磁碟閘 | Route 沒有預設時 |
| Issue：`relink`、`recheck`、`retry`、`relook`、`rescan`、`replan`、`resubmit`、`claim_*`、`adopt` | 直接做 | 各命令自己的檢查 | — |
| Issue：`delete_complete`、`replace_with_link`、`delete_orphan`、`accept_loss`、`accept_removal`、`mark_sourceless`、任何「忽略」 | 準備 Proposal 與理由 | — | **全部**（刪檔或放棄追蹤，沒有反向命令） |
| 巡檢 Issue（`series_episodes_missing`、`series_episodes_collide`、`first_batch_stuck`、`feed_*_failing`） | 缺集→缺集搜尋並挑一筆送單；撞集→rematch；卡住→重試；Feed 失敗→診斷並提出修法 | 送單受 C3 閘；改 Feed 網址是改設定 | 改 Feed 網址、刪 Feed → Proposal |
| 停住的 Job（`submit_failed` 用完、`import_failed`、`stalled`；R11 待定） | 重試；`stalled` 找替代發佈 | 同上 | 刪 Job、移除 torrent |
| 被排除的 Feed Item（「仍然下載」） | **不接管**：排除條件是使用者自己定的規則，AI 推翻它沒有意義 | — | 全部 |
| 第一輪預覽（`prime_feed`，已標 `irreversible`） | 只建議 | — | 全部 |
| 設定、Route、精靈、通知 bot | 只在對話中準備 Proposal | — | 全部（brief §14） |
| 標成未看（清掉 Jellyfin 的觀看次數） | — | — | Proposal |

「不可逆」在這裡的判準照 brief §14 並補兩條：**會讓 Berth 連到新位址的**（改服務網址、加 Feed 網址：外洩 API key 的唯一真實路徑，`07-…` §2）與**對外發訊息的**，一律要人。

### C2. 對話式 agent（簡化版 claw）

**要做的**：每頁都開得到的側面板；對話中呼叫登錄表的工具、外部 MCP（例如 Tavily）與 skills；結果是卡片，要確認的動作在卡片上按；上下文自動壓縮與 `/compact`、`/new`、`/usage`、`/status` 這類斜線指令。

**claw 類專案能抄的**（`06-…` §1；`bk` 的 `claw-references.md` 讀過原始碼）：

- **確認是一筆持久化的資料列**，不是阻塞的回呼：所有 claw 都收斂到這個形狀——授權（誰能按）與投遞（卡片出現在哪）分開，沒有按鈕的頻道有文字 `/approve <id>` 備援。openclaw 的 issue 是反面教材：頻道沒有按鈕編碼器時按鈕退化成不能點的文字、核准提示寄到錯的頻道（openclaw#134982、#28753）。
- **一份斜線指令登錄表**給所有表面共用（Hermes 的 `COMMAND_REGISTRY`），只有人類訊息開頭的 `/` 才算。
- **頻道與核心分開**：nanobot 的 `MessageBus → AgentLoop → AgentRunner`。
- **Skills 漸進揭露**：system prompt 只放 name + description，需要時用唯讀工具載 body；Berth v1 只做純指令型 skill（不能變成執行入口）。

**不抄的**：nanoclaw 的容器隔離模型、openclaw 的整套 Gateway——它們是給通用電腦操作設計的（有 shell、檔案系統），Berth 的能力邊界本來就只有登錄表。

**卡片的原則**（上次嘗試驗證過、值得沿用，`00-…` §6.1）：卡片由**命令的結果型別**決定，不由模型決定；確認卡的內容是伺服器依實際參數產生的預覽，按下時重驗並要求參數 hash 一致；只有提出者能按；先搶狀態防雙擊。

**自己做 claw 的難度落在哪**（`06-…` §6，細表含每項的陷阱）：

| 項目 | 難度 | 現成的 |
| --- | --- | --- |
| agent loop | 低–中（難在 provider 差異、串流中的 tool-call 組裝、錯誤分類、取消） | pydantic-ai；`anthropic` SDK |
| 上下文壓縮 | 中（切點要保持 tool call / result 成對、失敗保留原歷史、待確認的 Proposal 不能被壓掉、壓縮破壞快取前綴） | pydantic-ai `ProcessHistory`、`AnthropicCompaction`；Anthropic server-side compaction（Claude 專用） |
| 串流 UI | 中（訊息 part 模型、工具狀態機、重連、取消、i18n、手機版面） | Vercel AI SDK UI（`@ai-sdk/react` 4.x 與 React 19 相容）；pydantic-ai 的 `VercelAIAdapter` 直接輸出它的協定 |
| **工具權限 / 確認** | **中–高**（不是 UI 問題而是狀態機：持久化、過期、參數綁定、誰能按、重放、多表面一致、重啟存活） | pydantic-ai deferred tools（資料形狀）；其餘自己做 |
| 多頻道 | 中（身分映射、卡片降級、長度切分、Discord 3 秒初始回應、gateway 長連線） | `discord.py`（2.7.1，persistent view 與 `DynamicItem` 重啟後仍可點）；**沒有 Python 的現成頻道抽象** |
| 斜線指令 / skills | 低 / 低–中 | 不需套件 |
| 防護、可觀測性 | 中 | 自己的 SQLite 表（C4、C6） |
| 背景任務 + 影子 | 中 | 沒有現成的 |

結論：**難的兩件是確認的狀態機與多頻道，這兩件不管用哪個 SDK 都得自己做**；SDK 能省的是 loop、壓縮、串流協定。

### C3. 預算改成防護

brief §6.10「月預算上限，超過即停用」與 plan §11.6 的「月預算」**建議刪掉**，換成擋無意義消耗的防護；總花費只做可見性與提醒，不停用（`07-…` §1）。理由：使用者不要因為額度讓 AI 不能用；失控的根源是循環與重複，不是總額；而且費用是估計值（第三方端點的價格 Berth 不知道），拿估計值當硬開關不可靠。**上限以 token 與步數計，不以美元計。**

| 防護 | 對話 | 背景任務 | 觸發後 |
| --- | --- | --- | --- |
| 每次呼叫 `max_tokens` | 4096 | 2048 | provider 端截斷 |
| 每個 run 的模型往返 | 10 | 4 | 停 |
| 每個 run 的總 token | 400K 輸入 + 30K 輸出 | 100K + 8K | 停 |
| 重複呼叫（同工具同參數） | 第 2 次警告、第 3 次停 | 同 | 停 |
| 無進展 / 乒乓（A-B-A-B、狀態雜湊不變） | 偵測即停 | 同 | 停 |
| 工具結果截斷 | 單筆上限，超過給摘要與「還有 N 筆」 | 同 | — |
| 並發 | 每使用者 1 個進行中的回覆 | 2 | 排隊 |
| 同一對象的嘗試 | — | 24 小時最多 2 次；「交給人」的結論也快取（同一個解不出來的 torrent 不重複付費） | 交給人 |
| provider 斷路器 | 連續 5 次失敗暫停 15 分鐘 | 同 | 退回 M4 行為 |
| 送單的數量與磁碟閘（R5） | 一次確認最多 N 個 torrent | 每輪最多 N 個、扣在途量 | 超過的做成 Proposal |

觸發後：**對話**停下並留一則說明（哪條保險絲、做到哪），使用者可按「繼續」一次；**背景任務**不套用、交給人並帶原因碼，同類原因一小時內第三次才通知。
**花費可見性**（不停用）：使用者自訂的每日提醒值；近 14 天日中位數的 5 倍異常提醒；用量頁的每日 token、快取命中率、估計費用。

數字是起點，prototype 用情境 1、2 量真實的步數與 token 之後再定。

### C4. Prompt injection

Berth 的風險面（`07-…` §2）：沒有 shell、沒有 email、沒有任意檔案存取；最壞的情況是**外洩 API key**（AI 改服務位址或加 Feed 網址，Berth 帶著 key 連過去）、**刪檔**、**送出使用者不要的 torrent**。外部內容進模型的入口：torrent 名與檔案清單、RSS、索引站結果、TMDB 簡介、網路搜尋結果與網頁、外部 MCP 的回應。

防線以**能力邊界為主、內容標記為輔**（OWASP LLM01、Simon Willison 的 dual LLM 與「lethal trifecta」、Google DeepMind CaMeL、Meta「Agents Rule of Two」的共同結論；來源在 `07-…`）：

1. **外部內容一律是資料**：工具結果以結構化欄位回、帶出處，外部文字包在標記的資料區塊裡；system prompt 明說資料區塊裡的指令不算。這只是輔助——模型可能照樣被說動，所以下面幾條才是真正的防線。
2. **背景任務零工具、固定 schema 輸出**，程式驗證後才套用；驗證是程式，模型說了不算（brief §14 已有）。
3. **對話的「污染」規則**：一則回覆裡讀過外部內容之後，帶自由文字參數的寫入一律降成 Proposal。上次嘗試的兩個守法要從逐工具改成通用：**引用的 id 必須出自本對話已存的工具結果**（`submit_guard`）、**網址與位址必須逐字出自使用者自己的話**（`subscribe_guard`）。
4. **工具權限分級**：read / reversible / irreversible 之外加兩個旗標——「連到新位址」與「對外發訊息」，兩者一律要人；「系統內部」的命令（背景迴圈入口、週報產生）不暴露成工具（`05-…` 觀察 5：目前 11 個 `irreversible` 全是這一類，要另立一個維度而不是第四個 Effect）。
5. **不可逆一律人確認**，確認卡由伺服器依實際參數產生並綁參數 hash。
6. **憑證永不進上下文**；回覆的 markdown 不載入外部圖片（圖片網址是常見的外洩通道）。
7. **外部 MCP**（Tavily 之類）只放行 allowlist 內的工具、用 Berth 自己寫的工具描述、描述 hash 一變就停用，結果當不可信資料。MCP 的 tool annotations 只是提示，規格要求 client 視為不可信（MCP spec 2026-07-28）。
8. **Discord**：只處理已綁定 Berth 帳號的人；確認按鈕只有發起人按得到；角色與 web 同一道門禁。
9. **整合測試**用假模型決定性重現注入（上次嘗試的做法），證明「被說動」也執行不了。

### C5. 可觀測性

只用自己的 SQLite（`07-…` §3）。Langfuse 要 Postgres、ClickHouse、Redis、S3，對單容器自託管太重；Phoenix 是第二個服務；OpenTelemetry GenAI semconv 仍在 Development，只預留欄位命名相容。

- `ai_runs`：每則回覆或每個背景任務一列——來源（對話 / 任務型別 / Discord）、使用者、步數、各類 token 合計、估計費用、停止原因（完成 / 哪條保險絲 / 交給人 / 錯誤）。
- `ai_calls`：每次模型呼叫一列——`run_id`、`step`、model、`input_tokens`、`output_tokens`、`cache_creation_input_tokens`、`cache_read_input_tokens`（原樣存，`None` 表示不知道，不當 0）、`cost_usd_est`（價格未知存 NULL）、延遲、`stop_reason`、工具名。成敗都記、自己 commit（上次嘗試的 `call_model` 做法）。
- `ai_tool_calls`：每次工具呼叫一列——命令名、參數摘要、結果或拒絕理由、是否被降成 Proposal。
- 快取命中率 = `cache_read / (cache_read + cache_creation + input)`（Anthropic 的 `input_tokens` 不含快取讀寫，OTel 的含，轉換時注意）。
- 價格表存每個模型的四個價（輸入、輸出、快取寫、快取讀）並帶查證日期。現價（Anthropic 官方 pricing 頁，2026-10-27 經子代理查證，USD / MTok）：Sonnet 5.5 $2 / $10（快取讀 $0.10）、Haiku 5.5 $0.10 / $0.50（$0.01）、Opus 5.5 $4 / $20（$0.20）、Fable 5.1 $10 / $50（$0.25）。動工時再查一次。
- UI：用量頁（每日 token 分類、命中率、估計費用、保險絲觸發次數、被擋下次數）；每個 run 的步驟頁（工具序列、每步 token、命中率、費用、停止原因）；對話裡的 `/usage`、`/status`。

### C6. 情境

細節在 `08-scenario-data-sources.md`。**限制**：環境裡沒有 TMDB key，TMDB 用 themoviedb.org 網頁與 repo 快照（`tests/fixtures/tmdb/tv-65942.json`）查，discover / recommendations / collection 端點沒實打；AniList、Bangumi、Fribb 有實打。

**情境 1：「最近有什麼推薦的新番 / 新劇」**

- 流程：TMDB discover（首播日、`with_original_language=ja`、Animation 類型）／ on_the_air → 動漫加 Bangumi `/calendar`（免 key、中文名與評分）或 AniList seasonal → 網路評價 → 清單卡（每部一列：分數**與票數**、首播、集數、已在媒體庫否）→ 使用者勾選 → 每部一張動作卡（訂閱 Mikan RSS / 搜現有集，帶 Route 與範圍）→ 確認 → 進流程。
- 問題：新番剛播時評分票數極少（Bangumi 本週 113 部放送，票數中位數 53，46 部不到 20 票），**分數必須連票數一起給**，不然排序沒有意義；TMDB 的動漫類型與季劃分常被社群改；「推薦」若能讀 Jellyfin 的觀看紀錄（Berth 已有 watch state）會比純熱門有用。
- **網路搜尋用什麼**：
  - Anthropic 的 server-side `web_search`：同一把 key、不用新帳號，$10 / 1,000 次，可用 `allowed_domains` 限網域，但綁 Anthropic。
  - Tavily：免費每月 1,000 credit，有 MCP server，不綁模型。
  - Brave Search API、Exa、自架 SearXNG 也可選；SearXNG 要手動開 JSON 輸出，穩定度差。
  - 建議預設 `web_search`，Tavily MCP 作為可選的外部 MCP；這也正好驗證 C4 的外部 MCP 防線。
- 推薦清單本身不需要網路搜尋也能成立，TMDB 加 Bangumi 就夠，網搜只是加分，所以設成可關。

**情境 2：「幫我下載 Re:Zero 全系列」或冷門劇**

- Re:Zero 是最壞的例子：**TMDB 只有 Specials（90 集）與 Season 1（85 集），第 2–4 季全併進 S1**（S2 約 E26–50、S3 約 E51–66、S4 約 E67–85）；四個 episode group 裡 Absolute 那個是空的；兩部 OVA（Memory Snow、Frozen Bond）是獨立的 TMDB 電影，同屬 collection 689287，和 TV 沒有連結。字幕組第四季用總集數命名（`4th Season - 84`），剛好等於 TMDB 的 S01E84；第三季常是 `3rd Season - 01`，要靠 offset。
- 「完整清單」最可靠的做法：**AniList relations 走圖**（從第一季出發 12 次呼叫得到 12 個條目：各季、分割 part、Break Time、OVA）**再用 Fribb anime-lists 對到 TMDB**（`episode_offset.tmdb` 是 26 / 38 / 50 / 66，正好是 TMDB 合併後各輪的起始集減一）。但三個來源對劇場版與 OVA 的歸屬各說各話：Fribb 把 Memory Snow 對到 TMDB 的 Season 0、AniList 走圖沒找到 Frozen Bond。
- **確認卡的顆粒度**：一張**總覽卡**（唯讀清單、可勾選：每個條目寫入庫成「劇集 S01E26–50」還是「電影」還是「Season 0」）→ 展開成「條目 × 發佈」的子卡（每張一個 torrent 或一個合集，帶解析度、字幕組、做種數、預估對應的集數範圍）→ **分批執行**（一批確認、一批送出，受 C3 的數量閘）。不要一張卡送整個系列。
- 其他問題：已完結作品 RSS 沒用，要搜合集（BD 合集 vs 逐集 WEB）；冷門劇只有零星做種；同一季多字幕組多解析度要有挑選規則（沿用搜尋的「為什麼不像這部」分類）；AniList 實測限流 30 次 / 分鐘（文件寫 90），條款禁大量收集，走圖結果要快取；Fribb 的授權條款未查。

**補充情境**（都只用 Berth 已有的資料，風險低、價值高）：

| # | 情境 | 需要的資料與命令 | 問題 | 建議 |
| --- | --- | --- | --- | --- |
| 3 | 「為什麼這集沒入庫」 | Job 時間線、Event、Issue、RSS Item 狀態（被排除？沒綁定？）、搜尋紀錄；**缺一個聚合的唯讀命令** | 答案散在五張表；模型要知道 Berth 的狀態機才講得對 | **當第一個 tracer**：全唯讀、不會出事，又最能驗證工具設計與卡片 |
| 4 | 「這部缺的集補一下」 | 作品頁的 `missing`、缺集搜尋（`search.plan_queries` 等，未標）、送單 | 缺集搜尋本來就分批「問下一批」；送單受數量閘 | 一張卡列出每集挑中的發佈，整批確認 |
| 5 | 「今天有什麼要我處理」 | `waiting.waiting_now`、Issue、審核佇列 | 接管開關沒開時，AI 只能整理與建議 | 分組摘要 + 可逆的一鍵處理 + 不可逆的 Proposal 清單 |
| 6 | 「BD 出了，換掉 WEB 版」 | 重複版本判定、搜尋、送單 | 「取代」不可逆；新版的集數對應要重算 | 搜到的先送單，入庫時走重複版本決定 → Proposal |
| 7 | 「這部完結了，訂閱可以停了嗎」 | Series 完結判定（M4 票 108、116）、Feed | 刪 Feed 不可逆（R4） | 建議停用而不是刪；刪除走 Proposal |

### C7. 架構選型

研究與比較表在 `06-agent-architecture.md` §7（來源附在該檔）。

| 面向 | A 內建 agent | B 只提供 MCP / CLI + skills | C 混合 |
| --- | --- | --- | --- |
| 實作難度 | 高；取決於 loop 用什麼（下表） | 最低：FastMCP 掛進 FastAPI + token 驗證 + 登錄表轉工具 | A 加上 B 的薄層；B 的增量很小，因為登錄表與門禁本來就要做 |
| 維護成本 | 追 SDK 與協定（pydantic-ai 每週版、AI SDK 大版本換協定、provider 參數變動） | 追 MCP 規格（2026-07-28 剛大改）；其餘由外部 agent 的維護者承擔 | 兩者之和 |
| 使用體驗 | 側面板在 Berth 裡、卡片與頁面脈絡整合、不用另外裝 agent | **沒有側面板**；體驗取決於使用者選的 agent；對已有 Claude Code 的人很好 | 最完整 |
| 人工接管開關 | 可行：`ai_worker` 在行程內、工具集可收窄、影子天然 | **做不到**：背景接管要常駐的觸發者；Berth 也看不到「AI 本來會怎麼做」 | 可行 |
| Discord | 自己做 gateway、身分、卡片 | 可讓 openclaw / Hermes 掛 Berth 的 MCP 得到 Discord 對話，但確認卡是它的、不是 Berth 的 Proposal | 內建 Discord 走同一個核心與 Proposal |
| 安全性 | 能力邊界由登錄表決定，agent 沒有 shell | **風險面最大**：外部 agent 帶它自己的 shell 與注入面，Berth 只能守伺服器端門禁 | 內建 agent 的工具集比 MCP 窄；同一道門禁 |

B 單獨做不到三個需求中的兩個（側面板、背景接管），所以問題收斂成 **C，而內建的那一半用哪個 loop**：

| 內建的 loop | 優點 | 缺點 |
| --- | --- | --- |
| A1 自寫（上次嘗試的 httpx 直打 + provider 抽象） | 依賴最少、完全掌控；provider 層已寫過並對 DeepSeek 驗證過 | 壓縮、串流協定、確認恢復都要自己寫——正好是最花時間的三件 |
| **A2 pydantic-ai**（2.61.0，MIT） | deferred tools（run 結束、存下待確認、帶結果恢復）= Proposal 與影子的天然形狀；`VercelAIAdapter` 直接接前端；`ProcessHistory` / `AnthropicCompaction`；`UsageLimits`；MCP client；多 provider；`TestModel` 測試不碰 HTTP | 每週一版；harness 還是 0.x；`ag-ui` extra 的版本落差；與 Berth 的 Proposal 表、快取前綴、SQLite 存訊息的整合**都未實測** |
| A3 Claude Agent SDK | 壓縮、skills、`/compact`、MCP、斜線指令都是 Claude Code 現成的 | wheel 116–129 MB、每 agent 約 1 GiB RAM、只有 Claude、確認是阻塞式回呼、session 檔在磁碟；開源專案散佈時 Commercial Terms 的適用性沒有結論 |

LiteLLM 不考慮：2026-03 與 2026-10-21 兩次 PyPI 供應鏈事件（帶 infostealer 的版本），依賴也重。

**推薦：C，內建 agent 用 A2（pydantic-ai），以 prototype 驗證為前提；驗證不過就退回 A1，沿用上次的 provider 層。**

理由：
1. B 做不到側面板與背景接管，只能當附加；但 MCP 匯出在登錄表做完之後幾乎免費（FastMCP 4.x 的 `http_app()` 掛進 FastAPI），而且給「已有 Claude Code 的進階使用者」與開發時的除錯很有用。
2. 內建 loop 的難處在確認狀態機、壓縮、串流協定。A2 是查到唯一同時給「deferred 確認 + Vercel 協定 adapter + 多 provider + MCP client + 不碰 HTTP 的測試」的函式庫，而且它的 deferred 形狀與我們要的 Proposal 表、影子模式同構——這是上次嘗試自己做、而且做得最重的部分（`tools.py` 1,119 行逐工具手寫 guard / preview / card / undo）。
3. A3 與 Berth 的約束最不合：單容器自託管加 1 GiB RAM 起跳、只有 Claude（使用者可能要 DeepSeek 或本地模型）、阻塞式確認與「Proposal 是一筆資料、可以在 Discord 上按」對不起來。
4. A2 的風險都是**整合**風險，用 prototype 一週就能回答：deferred → `proposals` 列 → 從另一個請求恢復；`message_history` 存 SQLite；`VercelAIAdapter(sdk_version=7)` 接 `@ai-sdk/react` 4.x 的確認卡；Anthropic prompt cache 命中率；重試與錯誤分類是否符合「provider 失敗交給人」。

**分層**（三個入口一個核心）：

```
入口：側面板（SSE / Vercel 協定）  Discord（discord.py gateway）  背景 ai_worker  MCP server（外部 agent）
          │                          │                         │                 │
          └──────────── agent runtime（loop、防護、壓縮、斜線指令、skills）───┘  │
                                     │                                            │
                     命令執行器（actor、角色、喚醒、事件、拒絕轉換、污染規則）◄───┘
                                     │
          命令登錄表（名稱、pydantic 輸入、結果型別、Effect、inverse、旗標、卡片型別）
                                     │
                            services（既有）    proposals 表    ai_runs / ai_calls / ai_tool_calls
```

### C8. 里程碑安排

| 里程碑 | 內容 | 為什麼這樣排 |
| --- | --- | --- |
| **M5 AI 地基與對話 agent** | 清障（B1–B4、B6）；命令登錄表與執行器；Proposal；provider 與 agent runtime；防護、壓縮、斜線指令；可觀測性；側面板與卡片；情境 1–3 的工具（TMDB discover / recommendations / collection、AniList + Fribb、網路搜尋、「為什麼沒入庫」聚合讀取） | 對話有人在場，是最安全的方式讓登錄表、Proposal、防護、可觀測性第一次接觸真實模型；背景接管建立在被驗證過的核心上 |
| **M6 人工接管開關** | `ai_tasks`、`ai_worker`、三段開關與影子統計、C1 那張表的決定點（第一批：低信心 Plan、待綁定 Series、audit、Unmatched；接著 Issue 與巡檢）、AI 活動頁的逐筆撤銷、每週完整巡檢交給 AI | 影子模式要一週真實資料才知道一致率，所以要在核心穩了之後才開始累積；它也依賴 B5（三種停住的 Job 要不要開 Issue） |
| **M7 外部頻道與 MCP** | 個人 API token（brief §16.2）；Discord 對話（gateway、身分綁定、Proposal 按鈕、長度切分、卡片降級）；MCP server（登錄表匯出、同一道門禁）；skills 文件給外部 agent | 只多介面，核心與 Proposal 共用；個人 API token 是 MCP 的前提 |

**對話 agent 要提前到 M5**：
- 這是使用者最想要的功能。
- 上次嘗試證明側面板放在 M5 做得出來。
- 有人在場的對話比自主的背景任務容易發現登錄表與確認卡的錯，風險也低。
- 原計畫 M5 做完只有背景任務、看不到東西，要等 M6 才有介面。

**Discord 放 M7**：
- 它需要 gateway 長連線、身分綁定、卡片在沒有按鈕時的降級。這些都是「頻道」的工作，不是 AI 的工作。
- 核心的 Proposal 在 web 上穩定之前接第二個頻道，會兩邊一起改。
- 它與接管開關互不依賴。如果想早點在手機上用，可以把 M7 的 Discord 對話與 M6 對調，或在 M6 尾端並行。這列在拍板清單第 4 條。

M5 比原計畫大。估計和上次嘗試的 20 張票同一個量級：上次沒有清障、壓縮、斜線指令、防護與情境工具，但那幾段改用 pydantic-ai 現成的部分能省掉一些。

---

## 大概的計畫

### M5（調整後）：AI 地基與對話 agent

**驗收**：
- 在側面板走完情境 1、2、3。情境 2 至少一部「TMDB 季劃分與發佈名不一致」的作品（Re:Zero）分批入庫正確。
- 不可逆與「連到新位址」的命令只能經 Proposal 執行（整合測試，含假模型注入）。
- 每個 run 的步驟、token、命中率、估計費用、停止原因看得到。
- 防護各觸發一次並留下說明。
- `/compact` 與自動壓縮後，待確認的 Proposal 仍在。
- 關掉 AI 時與 M4 相同。

**分段**（每段結束 repo 可運作）：

1. **清障**：先 cherry-pick 三個測試修正讓 CI 綠（B1）。接著補完命令標記並修正 R2–R7，拆開 `resolve_issue`（B3），修核准路徑的帳本比對（R10）。`progress.md` 補記上次 M5 的嘗試與撤銷。
2. **登錄表與執行器**：`CommandSpec` 存名稱、pydantic 輸入、結果型別、拒絕理由、Effect、inverse、旗標（連到新位址 / 對外發訊息 / 系統內部）、卡片型別。執行器把 API 層的喚醒、推播、角色、actor 收進來，API 改走執行器（B4）。沒有 AI 也成立。
3. **Proposal**：`proposals` 表，帶參數 hash、過期時間、提出者、狀態。預覽與執行分離，執行時重驗。沒有 AI 時人也能用（例如審核頁的「取代舊版」）。
4. **AI tracer**：
   - provider 設定與 `settings.ai`（Anthropic 先做，OpenAI 相容視拍板）。
   - agent runtime：A2 或 A1，看 prototype 結論。
   - 加上 `ai_runs`、`ai_calls`、`ai_tool_calls`，以及防護的前兩條（往返數、重複呼叫）。
   - 側面板接起來，跑情境 3「為什麼沒入庫」：全唯讀、第一張卡。
5. **寫入與確認卡**：
   - 加入送單、訂閱 RSS、缺集搜尋（情境 4）。
   - 確認卡、撤銷卡、污染規則與「位址逐字出自使用者」的通用守法。
   - 整合測試用假模型重現注入。
6. **外部資料工具**：TMDB discover / recommendations / collection、Bangumi calendar、AniList relations + Fribb 對照（附快取與限流）、網路搜尋（`web_search` 與可選的 Tavily MCP，含外部 MCP 的 allowlist 與描述 hash）。走完情境 1、2。
7. **claw 的其餘部分**：
   - 自動壓縮與 `/compact`，斜線指令登錄表（`/new`、`/compact`、`/usage`、`/status`）。
   - 純指令型 skills。
   - 防護的其餘幾條。
8. **用量頁與 run 步驟頁**，然後 UI 收尾（`/impeccable` critique、audit、polish）。
9. **驗收**。

### 階段二的 prototype 打算回答的問題

照你的要求，腳本放 `scripts/experiments/`，結論寫回 brief §20（新的一節）。用 `mattpocock-skills:prototype` 做。預定跑在 Fake 後端上，加一個最小的對話頁，不進 `web/`。

1. **pydantic-ai 的 deferred 能不能當 Proposal 表**：run 以待確認結束 → 寫一列 → 另一個 HTTP 請求帶結果恢復 → `message_history` 存進 SQLite 再讀回來能不能繼續。
2. **串流與確認卡的端到端**：`VercelAIAdapter(sdk_version=7)` 接 `@ai-sdk/react` 4.x 的確認卡能不能跑。若不順，改成自己的 SSE，量差多少工。
3. **情境 1、2 實際跑起來的品質**：
   - 模型能不能用 TMDB + AniList + Fribb 列出 Re:Zero 正確的條目與入庫路徑（劇集範圍 / 電影 / Season 0）。
   - 搜尋結果挑得對不對。
   - 一次情境要幾步、多少 token、命中率多少、估計多少錢。這會定 C3 的數字。
4. **防護的手感**：重複呼叫與往返上限在情境 2 會不會誤殺正常流程。
5. **壓縮**：自動壓縮後，待確認的 Proposal 與「網址逐字出自使用者」的證據還在不在。
6. **provider 差異**：Anthropic 官方（上次沒實測）與一個 OpenAI 相容端點（例如 DeepSeek），各自的工具呼叫品質與 prompt cache 命中。

不在 prototype 範圍：Discord、MCP server、背景接管與影子模式、正式 UI。

### 需要你拍板的決定

1. **上次 M5 為什麼撤銷？** 理由沒有記錄。如果是「做出來的不是我要的 claw」，這次的方向（pydantic-ai、skills、壓縮、斜線指令）就是在回應它。如果是別的原因（票切太碎、程式碼太多、provider 沒實測），請告訴我，計畫要跟著改。也請決定上次的程式碼怎麼用：我建議**重寫，但把 provider 層、`ai_calls`、Proposal 的預覽 / 執行分離、注入守法的測試方式當參考**，不直接 cherry-pick。
2. **架構**：C + pydantic-ai（prototype 驗證不過就退回自寫 loop），不用 Claude Agent SDK。
3. **預算**：刪掉 brief §6.10、plan §11.6 的「月預算上限，超過即停用」，換成 C3 的防護與只提醒的花費可見性。
4. **里程碑**：M5 地基與對話、M6 人工接管開關、M7 Discord 與 MCP。另一個選項是 Discord 提前到 M6、接管開關延到 M7。
5. **對話中哪些動作要確認卡**。建議：
   - 要卡：不可逆、送出 torrent、連到新位址、對外發訊息、受污染的寫入。
   - 不要卡：其餘可逆動作直接做並給撤銷卡。
   - 這比 plan §11.7 原本的「可逆的直接執行」嚴一點，因為送單在 Berth 的分類裡算可逆，但你的情境描述是要先看到確認卡。
6. **資料與搜尋來源**：
   - 加 AniList（含 Fribb 對照）與 Bangumi 兩個唯讀 adapter。
   - 網路搜尋預設 Anthropic `web_search`，Tavily 作為可選的外部 MCP。
   - 也可以只用其中一個，或先不做網搜。
7. **兩個 M4 遺留的待決項**：
   - `submit_failed` 用完、`import_failed`、`stalled` 要不要開 Issue（R11）。建議開，接管開關需要這個出口。
   - 非 admin 能不能用側面板、看得到哪些 Job（R12）。建議 `user` 可以用側面板，但只有讀取與自己的送單，其餘照 API 門禁。
8. **provider 範圍**：只做 Anthropic，還是第一版就同時做 OpenAI 相容格式（上次兩種都做了，DeepSeek 驗過）。
9. **金鑰**：prototype 與 e2e 要一把 TMDB key 和一把 AI key（Anthropic，或你想測的 OpenAI 相容端點）。請提供，或告訴我放在哪個 `.env`。
10. **清理**：`backup/m5-attempt-1-20261024`、`backup/main-before-reset-20261025`（本機與遠端都有）、`bk` 三個分支先留著當參考，M5 驗收後再刪？`bk` 的兩份研究要不要併進 main 的 `docs/research/`？
