# AI agent 架構：內建 agent 加匯出的 MCP，pydantic-ai，沒有月預算上限

2026-10-27 重寫 M5 時的方向（上一輪因設計太簡單被撤銷，分支 `backup/m5-attempt-1-20261024`）：

- **架構**：內建 agent 加之後匯出的 MCP。內建的 loop 用 pydantic-ai（prototype 不過就自己寫），不用 Claude Agent SDK、不用 LiteLLM。
- **拿掉月預算上限**，改成防護加只提醒的花費可見性（brief §6.10）。
- **provider 兩種都做**：Anthropic 與 OpenAI 相容，各自設 base URL 與 key。
- **外部資料**：AniList + Fribb + Bangumi；網路搜尋預設 Anthropic `web_search`，Tavily 可選。2026-10-28 縮小：Fribb 與 AniList 的標題搜尋、系列走圖拿掉，AniList 只留當季清單、Bangumi 放送表照留（新番推薦要它們）；整部系列改用網搜集數表加 TMDB 季集表，沒有網搜時照 TMDB 播出日切段、每一季都標「請確認」（`docs/research/agent-sources-ab-2026-10-28.md`）。
- **卡住而沒有 Issue 的三種 Job**（重試用完的 `submit_failed`、`import_failed`、停滯）開 Issue；一般使用者可以用側面板，但只能讀取與處理自己的送單。
- 對話裡哪些動作出確認卡見 brief §14。

來源：brief §19 舊列「M5 的方向」（原文在 `docs/archive/m5.md`）；`docs/research/m5-ai-direction-2026-10-27.md`、brief §20.24。
