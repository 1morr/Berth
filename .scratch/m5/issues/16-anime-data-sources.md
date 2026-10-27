# 16 — 動漫資料來源：AniList、Fribb、Bangumi

**Status:** done

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

- [x] 三個 adapter 都有契約測試（fixture 取自真的回應）；AniList 的 429 退避有測試
- [x] Fribb 授權查過、結論記在 brief §20
- [x] 情境 1、2 的整合測試綠（假模型，不打網路）
- [x] 全部檢查與 pytest 綠；plan §8 補 adapter；progress.md 已更新

## Comments

- 2026-10-27 票 19 交接：
  - **命令名**：skills 先用了 `anilist.search_anime`、`anilist.read_franchise`、`anilist.read_season`、`fribb.lookup_anime`、`bgm.read_calendar`（Bangumi 番組計劃用 `bgm`，`bangumi` 這個模組名已經是 Mikan 的番組查詢）。名字不同的話改 `berth/skills/*/SKILL.md`；`tests/unit/test_skills.py::test_a_pending_tool_is_not_misnamed_once_its_module_exists` 會在模組建好、名字對不上時紅。工具進 `TOOLS` 時刪 `PENDING` 的那幾格。
  - **情境 1、2 還要**：`media.read_media` 與 `discover.read_trending` 進 `TOOLS`（目前不是工具、`about` 是空的）。
  - **第 4 點的 offset 重疊**：票 19 寫進了 `series-mapping`（offset + 1 是第一集、同一季的範圍要首尾相接、重疊或有縫時用集數串起來並對 TMDB 的總集數、表上註明改了哪幾段）。要不要另外做程式檢查仍由這張決定、記理由。
- 2026-10-28 實作（票 16 本身）：
  - **決定**都記在 progress.md「偏差與決定」2026-10-28 M5 16 那幾行：Fribb 照用（沒有授權檔，執行時下載、不打包）、offset 交給 skill 而程式只給 `first_tmdb_episode`、「標題比對」註明在對話的表上（卡片沒有備註格）、五支工具算外部內容（卡片標記改叫「出自外部來源」）、系列走圖一層一次、`media.read_media` 給模型的精簡版、`PENDING` 拿掉、429 fixture 用文件範例。
  - **code-review 已處理**：AniList 一頁 50 筆與 `relationType(version: 2)` 實測補進 brief §20.3；`noqa` 寫原因；`Bangumi` Protocol 改名 `Bgm`（模組、factory 方法同名）；註解裡指 cour 的「一輪」改掉（Turn 才是一輪）；`ANIME_TOOLS` 一份給 `TOOLS` 與 `EXTERNAL_TOOLS`；實驗腳本改 import `FOLLOWED`；i18n key `fromWeb` → `fromOutside`；CONTEXT 加 Franchise；brief 的 Fribb 授權照實寫「沒有明文授權」的前提與不加署名的理由；`series-mapping` 第 4 步改成「OVA 或劇場版只對到第 0 季也用標題找」，情境 2 補 Memory Snow 用標題找到 TMDB 電影那一條。
  - **code-review 沒處理（判斷題）**：
    - `_int` 在 `adapters/anilist` 與 `adapters/fribb` 各一份（各自解自己的格式，三行）。
    - `TtlCache` 與 `services.sources.SourceCache` 的淘汰寫法相同，沒合併（後者回的是拒絕、id 由它自己生）。
    - `AnimeOut`、`CalendarItemOut` 逐欄抄 adapter 的 dataclass（repo 慣例：adapter dataclass、services pydantic）。
    - `AnimeSeason`（adapter 的 enum）直接出現在 `anilist.read_season` 的簽名（import-linter 允許）。
    - 卡片的說明句只提 AniList、Bangumi，沒提 Fribb：Fribb 的結果只有 id 與數字，沒有抄得上卡片的字。
  - **留給之後**：一般使用者沒有 `new-season-picks`（它要的 `rss.*` 只給管理員）；要給的話是另一張票決定讓一般使用者推薦但不訂閱。
