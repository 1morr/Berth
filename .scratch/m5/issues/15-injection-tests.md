# 15 — prompt injection 的整合測試

**Status:** done

**Blocked by:** 14

**讀:** brief §14；`docs/research/m5-ai-direction-2026-10-27.md` C4 全部、`docs/research/m5-ai-direction-2026-10-27/07-guardrails-injection-observability.md` §2；票 13、14 的守法

## 為什麼

外部內容裡的指令一定會有部分被模型照做。防線靠的是**照做了也做不到**。這要用測試證明，而不是相信 prompt。

## 做什麼

用假模型重現「模型被說動」的情況，逐一證明擋得住。外部內容的來源包括 torrent 標題、RSS Item、AniList 與 Bangumi 的資料、網頁搜尋結果：

1. 外部內容要它加一個 Feed：網址不是使用者打的，被擋。
2. 外部內容要它送使用者沒要求的 torrent：出卡，不直接送。
3. 外部內容要它改設定或服務位址：永遠要人，出卡或被擋。
4. 外部內容要它說出 key：憑證從來不在上下文裡（斷言送給模型的訊息不含任何 key）。
5. 外部內容在回覆裡塞外部圖片：前端不載入（與票 12 的測試對上）。
6. 偽造前端的核准與歷史：不被採用（與票 11、13 對上）。

## 驗收

- [x] 以上六類各至少一條整合測試，全部是「模型照做了，系統擋住」
- [x] brief §14 或 plan §11.6 標明哪些防線由哪些測試守（宣稱與測試逐條對得上）
- [x] 全部檢查與 pytest 綠；progress.md 已更新

## Comments

- 2026-10-28 完成。`tests/integration/test_agent_injection.py`：注入的字經真的工具進到模型（`ENTRIES`：torrent 標題、Feed Item、Mikan 番組資料、網頁搜尋，假服務回它），假模型下一步照做，斷言只看程式層的結果；六類各一個類別，加 Feed 與送單兩類逐一入口都跑。前端那一半在 `web/src/agent/AgentPanel.test.tsx` 的 `AgentPanel with a reply an injection wrote`。對照表在 plan §11.6〈注入的防線與守它的測試〉，`tests/unit/test_injection_claims.py` 雙向核對。每一道防線都拆掉做過變異，各有測試紅（progress.md 的 session 紀錄列了是哪幾個）。
- **AniList、Bangumi（bgm.tv）的資料**（票面列的入口）這張沒做：工具在票 16、還不存在。它們進 `TOOLS` 時 `test_every_read_tool_is_classified` 與 `test_every_read_tool_is_tried` 會紅，票 16 的 Comments 記了要把它們加進 `ENTRIES`。
- code-review 已改：名詞照 CONTEXT（入口不叫「外部內容」、Feed Item）、`Source` / `release` 改名 `InjectionEntry` / `indexer_result`、具名的入口常數取代位置取用、重複的步驟抽成 `to_add_the_attackers_feed` 與 `read_tools`、`needs_person` 那一條改用合法參數叫看得到的卡片工具並斷言出卡（原本用 `{}`，驗證就先擋了）、TMDB 與 Jellyfin 的 key 列進子集斷言、補 `assert_reached`、前端那條等串流的回覆出現、claims 檢查認模組層與 `async` 的測試、表裡 `test_every_read_tool_is_classified` 自成一列、關鍵字訂閱那一列註明「直接做但不送」。
- code-review 未處理：測試直接叫 `rss._search_url`（私有）擺假 feed 的網址，同 `test_rss_*` 的前例；改成公開會多一個只給測試用的介面。
