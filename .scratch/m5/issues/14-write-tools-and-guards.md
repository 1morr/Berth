# 14 — 寫入工具與守法

**Status:** done

**Blocked by:** 13

**讀:** plan §11.6〈已定〉、〈分段〉第 5 段；brief §14、§20.24；`docs/research/m5-ai-direction-2026-10-27.md` A3 的 R5、C4 第 3–5 點、C6 情境 4；`docs/research/m5-prototype-2026-10-27.md`〈實跑才抓到的問題〉第 6 點、S5 / S6 逐字稿；`scripts/experiments/m5_agent_chat.py` 的 `harvest`、`_unseen`、`add_rss_feed`

## 為什麼

情境 1、2、4 需要訂閱、加 Feed、缺集搜尋。M5 的注入防線主要靠能力邊界：id 只能出自工具結果，網址只能出自使用者的話，送出 torrent 有數量閘。

## 做什麼

1. **工具**：
   - 讀取：索引站搜尋（帶季號時記得 `missing`）、缺集搜尋、Mikan 番組搜尋與字幕組清單。
     （票 13 已把 `search.search_torrents` 與新的 `media.route_choices` 加進工具，送單那一條路才走得通；這裡補「帶季號時記得 `missing`」與結果大小。）
   - 寫入：Mikan 訂閱、關鍵字訂閱、加 Feed、Route 清單（Route 清單見上一行）。
   - 新的卡片命令要在前端 `agent/ConfirmCard.tsx` 補列的畫法（`RowBody`、`COMMAND_TITLES`、拒絕理由的那一組句子）；沒補的照參數原文畫。模型給的一列若不是命令輸入（像送單的 `source_id`），在 `services/agent._CARD_INPUTS` 加換法。
   - 全部經登錄表與執行器。
2. **守法**（通用，不寫在個別工具裡）：
   - **id 必須出自這段對話已存的工具結果**：media、source、route、bangumi、subgroup。不是的回理由給模型，不出卡。
   - **網址必須逐字出自使用者的話**：`CONNECTS_OUT` 的參數。
   - 「讀過外部內容」的警示**只標在自由文字參數出自外部內容的卡**（實測：全部都標，警示就沒有意義）。
3. **送單的數量與磁碟閘**（R5）：一張卡最多 N 個 torrent，扣在途量，超過的拆成下一張。N 寫成設定預設值，理由記在 plan。
4. **一般使用者**只能送自己的單、只能讀；訂閱與加 Feed 是 admin。

## 驗收

- [x] 每個守法各有被擋與放行的測試（假模型）
- [x] 實測抓到的兩個預覽理由（`route_required`、`route_kind_mismatch`）在卡片出現之前就被擋下（測試）
- [x] 數量閘拆卡（測試）
- [x] `agent` 情境走一次「加這個 RSS：<網址>」與「上網找網址直接加」，前者出卡、後者被擋（playwright 實跑）
- [x] 全部檢查、pytest、vitest 綠；progress.md 已更新

## Comments

- 2026-10-27 協調者（票 03b 收尾時的 Heads up，已查證）：`routes.check_route` / `routes.check_routes` 標成 `REVERSIBLE`、沒有旗標，所以 `needs_person` 是假、也不是 `internal`，會進登錄表、可以被登錄成工具。但它們會寫探測檔、讓 qBittorrent 校驗到 100%，觸發使用者設的「完成時執行外部程式」（`services/routes.py` 的說明、brief §20.2、M4 票 19；健康迴圈因此刻意不探測）。AI 自己按一次，使用者那邊的外部程式就跑一次（常見是發通知）。這張決定工具時二擇一並寫一行依據：不登錄成工具；或加 `Flag.SENDS_OUT`（`needs_person` 變真、出確認卡），同步 `tests/unit/test_command_marks.py` 的 NAMED。

- 2026-10-27 票 19 交接：skills 用到的這幾支要進 `services/agent_tools.TOOLS`（並補 `about`）：`search.search_torrents`、`media.read_media`、`bangumi.search_bangumi`、`bangumi.read_bangumi`、`rss.subscribe_mikan`、`rss.subscribe_search`。加進去時 `tests/unit/test_skills.py` 的 `PENDING` 會紅，照著刪。命令改名的話同時改 `berth/skills/*/SKILL.md`（frontmatter 的 `tools` 與內文的工具名，格式閘門會擋對不上的）。`search_torrents` 的缺集搜尋在 skill 裡寫成 `scope: {missing: true, season: <n>}`。Route 由 `media.read_media` 的 `routes` / `default_route_id` 給（只列種類相符的），skills 不用 `routes.list_routes`；**`media.read_media` 現在是 `admin`**，要讓一般使用者拿得到 `missing-episodes`（他能送單），這支要開成 `audience=user`（作品頁本來登入就看得到），否則 skill 照 all-or-nothing 對他永遠不出現。

- 2026-10-27 實作（票 14）的決定：`routes.check_route(s)` **不登錄成工具**（使用者同意）：沒有情境要它，AI 按一次就觸發使用者設的「完成時執行外部程式」；`tests/unit/test_agent_tools.py::test_route_checks_are_not_tools` 守著。數量閘 N=13（`AiSettings.card_downloads`，一季一 cour；設定頁沒有這一格）。`rss.subscribe_search` 直接做，只有關鍵字出自網頁時出卡。「扣在途量」照現有磁碟閘：卡片逐列送，前面送出的那幾列算在途（有測試），預覽時不預估整張卡的大小。skill `missing-episodes` 仍用 `media.read_media` 拿 Route（`default_route_id` 只有它有），`media.read_media` 開成 `audience=user`。
- 2026-10-27 code-review 未處理（兩軸）：
  - **直接做的寫入沒有撤銷入口**（plan / brief「其餘可逆的直接做並給撤銷」）：`rss.subscribe_search` 的反向是不可逆的 `rss.delete_feed`，側面板沒有撤銷鍵，交給票 22（那張的 Comments 記了）。
  - **數量閘數的是列，不是 torrent**：`rss.subscribe_mikan` 一列送整季（可能十幾個），一張卡 13 列就可能上百個；每一個照樣過磁碟閘。→ 協調者要求處理，見下一條。
  - **超過上限的列只在卡片做完時告訴模型**（`card_outcome.held_back`）：卡片被拒、過期、脫離時那幾列不再提——使用者沒按或不要，本來就不該自己再提一張。
  - 網址守法是子字串比對：使用者貼過的網址的**前綴**也算出自使用者（票面「逐字出自」字面相符，風險低）。
  - 前端：命令名在 `COMMAND_TITLES`、`RowBody`、`refusalSentence` 三處分支（加一個卡片命令要改三處加後端 `_CARD_INPUTS`）；`ToolCall.tsx` 的 `FAILURE_KEYS` 手抄後端 `_failure` 的鍵，沒有契約測試；後備的 JSON 列把欄位識別符當「出自網頁」的欄位名印出來。
  - `Origins.check` 收 `connects_out` 布林而不是整個 `CommandSpec`（單元測試不必建登錄表的列）；`QueryScope` 與 `api/search._scope` 同一組季號規則各一份（API 要帶理由碼的 422）。
- 2026-10-27 協調者要求（同一張票的補做）：**讓按卡的人知道自己要送多少**。預覽逐列記 `torrents`：送單一列 1 個，Mikan 訂閱是提出時讀單一 feed 的筆數（`rss.mikan_season_size`，只讀；整季一律補、按下去就送、不經第一批確認，所以是上限，已經有的不再送），讀不到是 `null`。卡片 Mikan 那一列多一格「送出」：「會送出整季：N 個 torrent，按下確認就送，不經第一批確認」，讀不到時說「數量要送出時才知道」。測試先紅後綠：`test_agent_write_tools.py::TestWhatACardSends` 三條（12 集、讀不到、送單一列一個；把 Mikan 的計數換成 1 會紅）、vitest 一條（拿掉那一格會紅）。
  **13 的上限維持數列**，理由：一季 24 集的訂閱一列就超過 13，改成數 torrent 的話它要嘛永遠放不上卡、要嘛得豁免「每張至少一列」——豁免的正好是它要管的那一種，閘門變成只擋得住「好幾部一起訂」。數量閘要擋的是模型把一大串單筆送單塞進一次確認（2026-09-26 一次送 144 個）；訂閱是使用者說要的那一部，該做的是讓他按之前知道數量（卡片寫出來），而整季的每一個照樣逐筆過磁碟閘（`rss._submit` → `jobs.add_download`，前面送出的算在途）。plan §6〈確認卡〉同步。
