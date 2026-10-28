# 27 — 訂閱的 skill；搜尋一律多語言（原名、英文、使用者的語言）

**Status:** ready-for-agent

**Blocked by:** 26

**讀:** 票 26 全文與 Comments；`berth/skills/*/SKILL.md`（現有四份）與 `tests/unit/test_skills.py`；`berth/services/search.py`（`search_torrents` 的 `query`、預設名字種類 `SearchSettings`）；`berth/services/agent.py` 的 instructions；brief §15、§20.21（季的搜尋記號）；`scripts/experiments/agent_sources_ab.py` 與 `agent-live*` 情境

## 為什麼

使用者 2026-10-28：

- 搜尋用的語言決定搜到哪種字幕：中文名搜到的多是中文字幕，英文名或原名什麼語言都有。其他國家的使用者也要能正常用。
- 助理要會**自己換關鍵字**，不是只能照 Berth 預設的名字搜（`search_torrents` 本來就收 `query`，只是沒有流程教它）。
- 決定：**用 skill 教流程，伺服器只守「一定要人選」的硬規則**（票 26）。原名和英文名一定要搜，再加使用者對話語言的作品名；搜種子下載也照同一套。

## 做什麼

1. **新 skill `subscribe`**（英文、格式照 `test_skills.py`）：
   - 搜尋：原名、英文名一定搜；再加使用者對話語言的作品名（TMDB 有就用，沒有就用模型自己的知識或網路搜尋，並說明來源）。Mikan 番組搜不到時換名字再搜。
   - 整理字幕組比較表：字幕組、字幕語言、解析度、最新到第幾集與日期、平常比播出晚多久（從發佈時間算）、做種數；給一個建議與理由。
   - 等使用者在對話裡選，或出卡讓使用者在卡上選（票 26 的必選欄位）；Mikan 有就走 Mikan，沒有才走關鍵字訂閱（指定字幕組）。
   - 訂閱前先看有沒有現成的訂閱（票 26），有就先問要不要刪掉舊的。
   - 站點連不上時：說哪個站、建議稍後再試，不自動改走另一個來源建訂閱。
2. **下載也多語言**：`missing-episodes`、`series-mapping` 找種子那一步照同一套名字（原名、英文、使用者的語言），結果不夠時換關鍵字（`query`）再搜；字幕語言與字幕組的偏好照使用者說的。
3. instructions 若要加一句（例如「搜尋關鍵字自己決定，見 skills」）就加，保持短。
4. **真模型確認**（用 `.env` key，預算上限 $1，用 `agent_sources_ab.py` 或 `m5_acceptance_scenarios.py` 的作法；需要時新增 `agent-live` 系列情境）：
   - 中文對話「幫我訂閱鐵旅！meet with 鐵道少女」：有沒有列出字幕組比較表、等使用者選、卡上字幕組必選；
   - 英文對話訂同一部：有沒有用英文 / 原名搜、表裡有英文字幕組；
   - 中文對話「下載葬送的芙莉蓮第一季」：有沒有多語言搜、列出中文字幕的發佈。
   兩種接口各跑一次，逐字稿與結論寫進 `docs/research/m5-acceptance-2026-10-28.md` 新的一節與票 Comments。

## 驗收

- [ ] `subscribe` skill 含上面幾條；`missing-episodes`、`series-mapping` 改成多語言（`test_skills.py` 綠）
- [ ] 真模型三題 × 兩種接口：有列表、等選、多語言搜（逐字稿）
- [ ] 全部檢查、pytest、vitest、前端 e2e 綠；CHANGELOG、progress.md 已更新
- [ ] 不發版、不 push

## Comments
