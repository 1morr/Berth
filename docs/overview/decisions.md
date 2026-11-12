# 決定清單

只收會改變系統怎麼運作、或你看到什麼的決定；實作細節的取捨在票的 `## Comments` 和 commit 裡。決定全文以來源為準。

**決定者**：使用者定（你自己定的）、使用者同意（agent 提議、你同意）、Agent 定（你沒看過）、不明（當時沒記，查不到）。2026-11-12 起，偏差紀錄和新 ADR 都要標決定者（`docs/progress.md`〈寫法與封存〉、`tests/unit/test_adr_rules.py`）。**看過**欄：「Agent 定」的決定在 `/1morr:checkpoint` 對話裡給你看過後填日期。

## 架構與範圍（ADR）

ADR 0001–0016 是 2026-10-30 從 brief 搬出來的，決定本身更早；只有內文寫明使用者的才標使用者定。

| 決定 | 決定者 | 來源 | 看過 |
| --- | --- | --- | --- |
| 索引站只接 Prowlarr，不支援 Jackett 與通用 Torznab | 使用者定 | [0001](../adr/0001-indexer-manager-prowlarr-only.md) | — |
| 只支援 Jellyfin 12 以上，套件內 image 釘 12.1 | 使用者定 | [0002](../adr/0002-jellyfin-12-minimum-pinned-image.md) | — |
| 移除 Route profile，絕對編號換算靠兩條證據決定是否自動入庫 | 不明 | [0003](../adr/0003-remove-route-profile.md) | |
| 媒體庫像 Jellyfin 那樣瀏覽，探索頁只放 TMDB 牆 | 不明 | [0004](../adr/0004-library-browsing-and-discovery.md) | |
| 顯示用標題跟 UI 語言，檔名只用英文 | 不明 | [0005](../adr/0005-display-title-follows-ui-language.md) | |
| `/review` 只列入庫決定，Issue 只在 `/issues` | 不明 | [0006](../adr/0006-review-and-issues-split.md) | |
| RSS 以 RSS Series 為單位：全部接受只排除、綁定時補舊集、Feed 必選 Route | 使用者定 | [0007](../adr/0007-rss-series-model.md) | — |
| AI 對可撤銷的命令自己做，不可撤銷的永遠要人；沒有 AI 也完整可用 | 不明 | [0008](../adr/0008-ai-autonomy-and-optional-ai.md) | |
| 部署只用 compose 加 `.env` | 使用者定 | [0009](../adr/0009-deploy-compose-and-env.md) | — |
| 精靈每個服務手動選套件內或既有，不偵測 | 使用者定 | [0010](../adr/0010-wizard-manual-service-selection.md) | — |
| 精靈保留兩個摩擦：TMDB 閘門、管理員密碼只有一格 | 不明 | [0011](../adr/0011-wizard-accepted-frictions.md) | |
| 擁有者就是 Jellyfin 管理員 | 不明 | [0012](../adr/0012-owner-is-jellyfin-admin.md) | |
| 接管既有服務只管 Berth 自己的物件 | 不明 | [0013](../adr/0013-berth-manages-only-its-own-objects.md) | |
| 不做站點請求預算 | 不明 | [0014](../adr/0014-no-site-request-budget.md) | |
| 通知用 Discord bot 私訊，用收件人的語言 | 不明 | [0015](../adr/0015-notifications-discord-dm.md) | |
| AI agent 內建加匯出 MCP、用 pydantic-ai、沒有月預算上限 | 不明 | [0016](../adr/0016-ai-agent-architecture.md) | |

## M5.6 AI 對話精簡

| 日期 | 決定 | 決定者 | 來源 | 看過 |
| --- | --- | --- | --- | --- |
| 11-06 | 方向：skills 與工具簡潔、通用，確認卡不逐列問 | 使用者定 | `docs/research/agent-slimming-2026-11-06.md` | — |
| 11-06 | 做 A1、A2、A4、B1–B4、C1–C4，放棄 A3 | 使用者同意 | 同上 | — |
| 11-06 | M5.6 排在 M6 之前 | 使用者定 | `docs/archive/m5.6.md` | — |
| 11-07 | Route 由伺服器定：一條直接用、多條問一次、零條拒絕 | Agent 定 | M5.6 票 04；archive 偏差 | |
| 11-07 | 以作品訂閱照作品首播日挑 Mikan 番組（挑錯季的根因） | Agent 定 | M5.6 票 08 Comments；brief §20.29 | |
| 11-07 | 核准訂閱時重新找一次番組，卡片不帶番組 id | Agent 定 | M5.6 票 08 Comments | |
| 11-07 | Mikan 沒有就退回 nyaa、acg.rip 關鍵字訂閱 | Agent 定 | M5.6 票 09 Comments | |
| 11-07 | `recommend` skill 只有管理員拿得到（一般使用者少了推薦的決策指引） | Agent 定 | M5.6 票 07 Comments | |
| 11-07 | 系統指示加「先認出作品，選定前不搜發行」 | Agent 定 | M5.6 票 07 Comments；brief §14 | |
| 11-07 | `series_episodes` 接受從媒體庫 index 讀到的 id（放寬 Jellyfin 門禁） | 使用者定 | M5.6 票 06 Comments；brief §12 | — |
| 11-07 | 搜尋 `contains` 命中「简繁日内封」這類寫法可以接受 | 使用者定 | M5.6 票 07 Comments | — |
| 11-07 | 確認卡這輪不改列結構 | 使用者定 | M5.6 票 10 Comments | — |
| 11-07 | 追加面板拖寬，上限維持 40rem | 使用者定 | M5.6 票 10b | — |
| 11-07 | S7／S8 搜種子次數未達標，接受、不開票 | 使用者定 | M5.6 票 11 Comments | — |
| 11-07 | 訂閱挑錯季不在 M5.6 修，排 M6 第一張 | 使用者定 | M5.6 票 11 Comments | — |
| 11-08 | 帶著已知的挑錯季缺陷發 0.5.1 | 不明 | `docs/progress.md` 11-08 列 | |

## M6 人工接管開關（進行中）

| 日期 | 決定 | 決定者 | 來源 | 看過 |
| --- | --- | --- | --- | --- |
| 11-10 | Issue 各型別、每週巡檢交給 AI、修正回流移到 M6.5 | 使用者定 | progress 偏差；plan §11.7b | — |
| 11-10 | M6.5 補進重複版本與 `episodes_overdue` | 使用者定 | progress 偏差 | — |
| 11-10 | 拿掉影子模式，改對凍在 repo 的案例做 AI 評估 | 不明 | progress 偏差；ADR 0008 | |
| 11-10 | 開關兩段（人／AI）、預設人 | 不明 | `.scratch/m6/spec.md`〈開關〉 | |
| 11-10 | 背景任務兩段呼叫，答「資料不夠」才給限網域唯讀網搜 | 不明 | progress 偏差；plan §4.5 | |
| 11-11 | 背景任務一次送超過 13 個 torrent 或磁碟不夠改 Proposal；評估件數 20／60 分級 | 使用者定 | progress 偏差 | — |
| 11-11 | 檔案清單帶片長、TMDB 每集帶 `runtime` | 不明 | progress 偏差 | |
| 11-11 | 第一批五種任務併成四型 | 不明 | progress 偏差；spec〈範圍〉 | |
| — | 防護數字（2048 output、每輪 4 次、並發 2、24 小時 2 次） | 不明 | spec〈AI 任務〉；`docs/research/m5-ai-direction-2026-10-27.md` C3 | |
| 11-12 | 交回人 < 5%（AI 處理 95% 以上） | 使用者定 | progress 偏差；spec〈AI 評估〉 | — |
