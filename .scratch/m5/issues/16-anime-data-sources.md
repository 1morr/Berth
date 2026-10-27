# 16 — 動漫資料來源：AniList、Fribb、Bangumi

**Status:** ready-for-agent

**Blocked by:** 14

**讀:** plan §11.6〈已定〉的外部資料、〈分段〉第 6 段；brief §20.3、§20.24；`docs/research/m5-ai-direction-2026-10-27/08-scenario-data-sources.md` §1–§2（Re:Zero 的實例、速率、條款）；`docs/research/m5-ai-direction-2026-10-27.md` C6 情境 1、2；`docs/research/m5-prototype-2026-10-27.md` 的 S1 / S2 逐字稿；`scripts/experiments/m5_agent_chat.py` 的 `anilist_*`、`fribb_lookup`、`bangumi_calendar` 與 `SKILLS["series-mapping"]`

## 為什麼

情境 1（新番推薦）與 2（整部系列）要的資料 Berth 沒有：
- 當季清單附評分人數。
- 系列的每一輪。
- AniList 輪次對 TMDB 季集的換算（TMDB 常把多輪併成一季）。

prototype 實測過這三個來源的組合可行。

## 做什麼

1. **adapters**（各一個）：
   - **AniList**（GraphQL）：搜尋、系列走圖（SEQUEL / PREQUEL / SIDE_STORY / PARENT / SUMMARY，可選 SPIN_OFF）、季表（評分人數由分數分佈加總）。
     - **限流 30 次 / 分**，429 照 `Retry-After` 等。結果快取，條款禁止大量收集。
   - **Fribb anime-lists**：執行時下載到 `CONFIG_ROOT`，每週更新一次。
     - **先查授權**：不允許的話改成只用標題搜尋，並記進 brief。
   - **Bangumi** `/calendar`：要帶有意義的 User-Agent。
2. 端點、速率、條款這些外部事實補進 brief §20，附來源（`docs/research/m5-ai-direction-2026-10-27/08-scenario-data-sources.md` 有大半）。
3. 工具（讀取類，外部內容），經登錄表註冊。
4. 系列換算的規則：
   - Fribb 的 `episode_offset` 可能讓區段重疊一集。實測裡模型自己用總集數改正，這一步要寫進 skill（票 19）或做成程式檢查，二選一，記理由。
   - 劇場版在 TMDB 是獨立的 movie：Fribb 對不到時用標題搜尋，卡片上註明「標題比對」。
5. 情境 1、2 用假模型各寫一條整合測試（外部服務用錄下來的 fixture）。

## 驗收

- [ ] 三個 adapter 都有契約測試（fixture 取自真的回應）；AniList 的 429 退避有測試
- [ ] Fribb 授權查過、結論記在 brief §20
- [ ] 情境 1、2 的整合測試綠（假模型，不打網路）
- [ ] 全部檢查與 pytest 綠；plan §8 補 adapter；progress.md 已更新

## Comments

- 2026-10-27 票 19 交接：
  - **命令名**：skills 先用了 `anilist.search_anime`、`anilist.read_franchise`、`anilist.read_season`、`fribb.lookup_anime`、`bgm.read_calendar`（Bangumi 番組計劃用 `bgm`，`bangumi` 這個模組名已經是 Mikan 的番組查詢）。名字不同的話改 `berth/skills/*/SKILL.md`；`tests/unit/test_skills.py::test_a_pending_tool_is_not_misnamed_once_its_module_exists` 會在模組建好、名字對不上時紅。工具進 `TOOLS` 時刪 `PENDING` 的那幾格。
  - **情境 1、2 還要**：`media.read_media` 與 `discover.read_trending` 進 `TOOLS`（目前不是工具、`about` 是空的）。
  - **第 4 點的 offset 重疊**：票 19 寫進了 `series-mapping`（offset + 1 是第一集、同一季的範圍要首尾相接、重疊或有縫時用集數串起來並對 TMDB 的總集數、表上註明改了哪幾段）。要不要另外做程式檢查仍由這張決定、記理由。
