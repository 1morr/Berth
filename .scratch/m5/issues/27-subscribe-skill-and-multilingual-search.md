# 27 — 訂閱的 skill；搜尋一律多語言（原名、英文、使用者的語言）

**Status:** done

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

- [x] `subscribe` skill 含上面幾條；`missing-episodes`、`series-mapping` 改成多語言（`test_skills.py` 綠）
- [x] 真模型三題 × 兩種接口：有列表、等選、多語言搜（逐字稿）
- [x] 全部檢查、pytest、vitest、前端 e2e 綠；CHANGELOG、progress.md 已更新
- [x] 不發版、不 push

## Comments

### 2026-10-29 實作（`45e326d5..HEAD`）

**做了什麼**

- **新 skill `subscribe`**（`berth/skills/subscribe/SKILL.md`，只給管理員：要 `rss.*`）：找作品 → `rss_list_subscriptions` 看現有的 → 定要搜的名字（原名、英文名一定搜；再加對話語言的作品名：繁中用 `title`，中文另加字幕組常寫的簡體名，其他語言用模型自己知道的或網路搜尋並說來源）→ Mikan 用中文、原名、羅馬字、英文名輪流搜番組，種子搜尋不帶 `query` 一次、`attempts` 裡沒有的名字再用 `query` 搜 → 比較表（字幕組、字幕語言、解析度、最新集與日期、平常比播出晚多久〔`published_at` 對 `aired_blocks` 推的播出日，估算〕、做種數、在不在 Mikan）＋一個建議 → **列表那一則問完就停**，不叫訂閱工具、不說卡已備好；有現成訂閱時同一則問要不要刪（`rss_delete_feed`）→ 選的字幕組在 Mikan 上走 `rss_subscribe_mikan`，不在才走 `rss_subscribe_search`（`term` 照那一組發佈名裡的寫法）→ 站連不上時說哪一站、建議稍後再試，不自己改走另一個來源。
- **多語言搜尋**：`missing-episodes`、`series-mapping` 找種子那一步照同一套名字（三份 skill 的名字規則是同一段字），結果不夠時換 `query`（羅馬字、帶季的名字、字幕組的寫法），並提醒 `query` 只照打的字判、季集要自己核；字幕語言與字幕組照使用者說的，沒說就偏好對話的語言；卡片每一列說字幕組與字幕語言。`new-season-picks` 的「還在播」改成載入 `subscribe`（拿掉它自己那套挑字幕組的步驟與 `bangumi.*` 宣告），「播完了」的搜尋也照同一套名字。
- **`missing-episodes` 的觸發與列表**：描述從「補缺集」放寬到「下載一季還沒有的」（真模型第 1 輪兩種接口對「下載第一季」都沒載入任何 skill）；出卡前在對話裡分字幕語言列候選，**使用者沒說字幕偏好、候選又有不同字幕語言時先問**，回答後才出卡。
- **instructions** 加一句：搜尋關鍵字自己決定，作品用原名、英文與使用者語言的名字搜，結果少就換名字（skills 說怎麼做）。
- **測試**：`test_skills.py` 的全部 skill 與「只給管理員」的集合加 `subscribe`（加之前紅兩條）。
- **真模型**：`agent_sources_ab.py --set subscribe`（三題；逐字稿多記卡上的字幕組選項與第幾句之後出卡）。五輪、$0.107。最終版：訂閱兩種接口 × 中英文 4 次都列表、等選、第二句才出卡、卡上字幕組必選（Mikan 2 選 1、nyaa 8 選 1），英文對話推薦英文字幕的 SubsPlease 並走 nyaa；下載兩種接口 × 2 次都載入 `missing-episodes`、多語言搜、分中英文字幕列表、問完才出卡、卡上都是中文字幕的 01–28 合集。逐字稿與每一輪改了什麼在 `docs/research/m5-acceptance-2026-10-28.md`〈票 27〉。

**決定（票面沒寫到的）**

- **「Mikan 有就走 Mikan」照字幕組判**：選的字幕組在 Mikan 上就走 Mikan，不在才走關鍵字訂閱。英文使用者要的英文字幕組（SubsPlease）不在 Mikan，作品雖然在 Mikan 上有番組，也走 nyaa；照「作品在 Mikan 上就走 Mikan」的話英文使用者訂不到英文字幕。
- **下載也可能先問**：票面只要求列出中文字幕的發佈；「出卡前先寫表」只靠提示時 OpenAI 接口 2 次裡 1 次照樣只叫工具、不寫字，改成沒說偏好又有多種字幕語言時先問（一則不叫工具的回覆一定有字）。使用者已說了偏好、或候選只有一種字幕語言時照舊同一則出卡。
- **`missing-episodes` 只收「一季」**：描述不寫「一部」，免得「下載整部 Re:Zero」載到它而不是 `series-mapping`。

**未處理（記錄）**

- **繁中全名沒拿去搜種子**：多數次只用短名或 Mikan 的簡中番組名搜索引站。這一部在索引站上只有英文名的發佈，比較表不受影響；skill 的「`attempts` 裡沒有的每個名字都再搜」只被部分照做。
- **字幕組名讀錯**：nyaa 搜尋的字幕組選項有 `VARYG (Tetsuryou! meet with Tetsudou Musume`（`rss.search_subgroups` 把組名後的括號讀進來），票 26 的組名解析，該另開票。
- **Mikan 卡的 `name`** 有一次被模型寫成字幕組名 `ANi`（Feed 名），只影響 RSS 頁顯示。
- **`new-season-picks` 沒用真模型重跑**（只改成載入 `subscribe`）。真模型樣本每種條件 1–2 次。
- **code-review**（Spec / Standards）已改：Mikan 分流記成決定、CHANGELOG 措辭、`subscribe` 第 6 步與票 26 的 `required` 一致、`missing-episodes` 描述收窄、研究表照逐字稿的實際搜尋字重寫、逐字稿標題的輪次、三份 skill 的名字規則收成同一段、過長的一行、實驗腳本的命名。沒改：skill 裡 release 一詞（CONTEXT.md 的 Search Result 建議少用，既有 skill 都這樣寫，要改就四份一起）；三份 skill 的名字規則沒有測試守一致（只斷言含某段字的測試過不了雙向變異），改其中一份要三份一起改；`new-season-picks` 叫 `subscribe` 靠內文，沒有「被引用的 skill 也看得到」的測試（兩份都只給管理員，現在不會出事）。

**驗證**：pre-commit 全過、`pytest -m "not e2e"` 5195 passed / 1 skipped、`pnpm -C web test` 2316 passed、`pnpm -C web e2e` 72 passed（先 `pnpm -C web build`）。真模型五輪合計 $0.107（上限 $1）。不發版、不 push。
