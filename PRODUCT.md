# Product

<!-- impeccable:product-schema 1 -->

本檔是 Berth 的產品脈絡：使用者、目的、定位、限制。視覺世界不在這裡（那是 DESIGN.md）。
與 `docs/design-brief.md` 衝突時以 brief 為準，除非本檔註明是它推翻了 brief 的哪一節。

## Platform

web

## Users

**兩種安裝者輪廓**（brief §16.1）：

- **NAS 使用者**：已有目錄規劃，可能已經在跑 Jellyfin 或 qBittorrent。要的是把 Berth 接到既有服務上，而且不能動到既有媒體庫的路徑與觀看紀錄。
- **一般電腦使用者**：什麼都沒有。要能「下載一份 compose、跑起來、開瀏覽器」就完成整套設定，全程不需要打開另外三個服務的介面。

**角色**（brief §11、plan §11.1 T0.5）：以 Jellyfin 帳號登入，Berth 不自建密碼系統；角色由 Jellyfin 的
`Policy.IsAdministrator` 決定。

- `admin`：改 Route、刪除、審核（Review Queue、Issue 的動作、rematch、手動對帳）、所有設定。首次設定必須用 Jellyfin 管理員帳號，該帳號成為 Berth admin。
- `user`：探索、送單到指定 Route、看自己的 Job。看不到設定入口；自己的 Job 停在 review 時只能等 admin（2026-09-22 明確，brief §11、§19）。

Jellyfin 掛掉時沒有人能登入 Berth。這是已接受的取捨（brief §11，Seerr 同樣如此）。

**使用者要完成的工作**：找片 → 決定季與 torrent → 送下載 → 系統自動解析入庫 → 在 Jellyfin 播放；
出錯時修正（rematch、刪除、重新入庫）。

**散佈範圍**（2026-09-07 使用者確認）：開源給自架者，且要面向英語使用者。UI 文案自始規劃成可翻譯，
英文是一等公民而非之後補上的譯本。這推翻 brief §16.2 與 plan §7 的「不做英文版直到有需求」，
兩處已同步改寫。

## Product Purpose

自託管的**媒體取得與入庫協調器**：把索引站或 RSS 命中的 torrent 送到 qBittorrent，下載完成後解析內容、
比對 TMDB，以硬鏈接入庫到 Jellyfin，並維護可追溯、可修復的入庫帳本（brief §0）。

第一階段目標是把「探索 → 下載 → 入庫 → 在 Jellyfin 可播放」全流程跑通，同時支援動漫、美劇、韓劇與電影。

成功的定義寫在里程碑驗收（brief §17）。M1 的驗收是「美劇、動漫、電影各一部，全程不經人工入庫並在
Jellyfin 正確顯示」。長期指標是解析 benchmark 的**誤自動入庫率趨近 0**（brief §6.9）——寧可讓一個檔案
進審核佇列，也不要把它默默放到錯的地方。

## Positioning

**Berth 只做協調**（brief §1.1、§1.2）。它負責探索與決策、取得、入庫、帳本與修復、媒體庫檢視、可觀測性；
播放與轉碼交 Jellyfin，下載協定與做種交 qBittorrent，索引站接入交 Prowlarr / Jackett，metadata 交 TMDB，
多版本合併顯示交 Jellyfin（12 起原生合併；Berth 只支援 Jellyfin 12 以上）。

跟 \*arr 生態的差別（brief §1.3、§4.4、§6.5、§7.4、§20.2、§20.4）：

- **CJK 字幕組是第一級公民**。查證結論是沒有現成程式庫能處理中文字幕組的命名（brief §20.4），所以自建詞典
  與解析階段。這是 Sonarr / Radarr 在中文動漫上失手的地方。
- **硬鏈接失敗就是失敗，不退回複製**。Sonarr 會靜默複製一份，Berth 直接擋下並說明哪個掛載錯了。
- **Unmatched 不入庫也不搬走**，留在 complete 原位，由 UI 列出。不做 library 內的 unmatch 資料夾。
- **medium 信心自動入庫但掛 audit 旗標**，在審核佇列顯示為「已入庫待確認」，可一鍵撤銷。不是二選一的
  「全自動」或「全手動」。

明確不做（brief §18）：品質自動升級替換、內嵌播放器、多人審批、非影片媒體、
complete/incomplete 鏡像 library 結構、remote path mapping、TVDB / AniList 以外的多 provider、
字型安裝與字幕解壓、BDMV 原盤處理。巡檢與通知、AI 核心、側面板與外部對話不是不做，是 M4–M7（brief §14、§17）。**沒有 AI 也完整可用**：AI 只替人按審核與待處理頁上的按鈕；平常看片用 Jellyfin App，Berth 只在加新作品或收到「等你處理」時打開。

## Operating Context

- **部署形態**：單一容器、單一 Python 程序（FastAPI + 同程序背景 worker + SQLite WAL），前端 React SPA
  由同一個 FastAPI 提供靜態檔（plan §1.1、brief §16.1）。備份就是複製 `/config`。
- **目標宿主**：Linux（NAS 與伺服器）與 Windows（Docker Desktop / WSL2）。exFAT 不支援。
- **開箱即用套件**：`deploy/docker-compose.yml` 起 `berth`、`qbittorrent`、`jellyfin`、`prowlarr` 四個容器，
  共用同一個 `/data`（brief §16.3、plan §9.1）。每個外部服務都可以從 `COMPOSE_PROFILES` 拿掉，改接既有的那一套。
- **外部服務**（brief §3）：Prowlarr / Jackett（Torznab）、qBittorrent（Web API v2，下限 4.4 / API 2.8.4）、
  Jellyfin（伺服器 API key）、TMDB（REST v3，唯一 metadata provider）。RSS 第一批是 Mikan 與 Nyaa。
- **典型流程**：手動是「探索 → Media 詳情搜 torrent → 選 Route 送單 → 下載 → 解析比對 → 硬鏈接入庫 →
  通知 Jellyfin 掃描 → 深連結播放」；自動是「RSS 訂閱 + Rule → 比對 → 去重 → 建 Job」。
- **維運儀式**：Reconciler 每日 04:00 對帳（也可手動觸發），健康檢查每 5 分鐘（plan §3.2）。
  使用者不會整天盯著 Berth——它平常在背景跑，人只在「想找新片」與「有東西壞了」兩種時刻打開它。
- **裝置**（2026-09-07 使用者確認，文檔原本未提及）：**桌機瀏覽器為主，手機要能完成日常操作**。
  精靈與設定在桌機做；手機上要能看下載佇列、審核低信心比對、送一個新的下載進去。
  所有主要頁面都要有真正可用的窄版，不是只求不破版。

## Capabilities and Constraints

**里程碑**（brief §17、plan §11）：

| | 內容 |
| --- | --- |
| M0 骨架 | 實驗、compose 套件、設定精靈、Route 建立、健康檢查 |
| M1 手動全流程 | 探索 → 搜尋 → 送單 → 輪詢 → 規則 planning → 硬鏈接 → 掃描 → 可播放 |
| M1.5 媒體庫瀏覽 | 整個 Jellyfin 媒體庫疊上 Berth 狀態、繼續觀看、已看 / 未看、選季選集（**2026-09-19 完成**） |
| M2 修正與對帳 | 審核佇列、Unmatched 指派、rematch、Reconciler、刪除範圍、重新入庫、`rebuild-ledger`、Job 詳情頁（**2026-09-24 完成**） |
| M3 RSS | Mikan / Nyaa / acg.rip adapter、RSS Series 自動綁定、排除條件、去重、補舊集、一次性連結（2026-09-24 重新設計） |
| M4 巡檢與通知 | 每日程式檢查、每週週報；「可以看了」「有 N 件等你處理」；`events` 訂閱者、channel adapter（Telegram / Discord 擇一）、每人的訂閱設定（不需要 AI） |
| M5 AI 核心 | 規則層 → AI → 人的三層漏斗；AI 替人按審核頁的按鈕：可逆的通過驗證後自己做、不可逆的要人；影子模式、AI 活動與撤銷（2026-09-24 改） |
| M6 Issue 與側面板 | Issue 交給 AI、側面板對話、不可逆的動作以提案確認 |
| M7 外部對話與 MCP | 聊天軟體裡與助理對話，提案卡帶按鈕，個人 API token；MCP server |

**技術限制**：

- 硬鏈接不能跨檔案系統、跨 mount、exFAT、跨 btrfs 子卷 / ZFS dataset / mergerfs branch（brief §4.4、§20.2）。
- Berth 與 qBittorrent 必須在同一台機器，不支援 remote path mapping（brief §16.4）。
- qBittorrent 版本下限 4.4；4.x 與 5.x 的 API 欄位有差異，一律依 `docs/research/m0-experiments.md` 的實測實作。
- Jellyfin 的語言碼分不出中文繁簡，只能用 `zh` 加自由文字標題變通（brief §6.7、§20.1）。
- **Berth 只支援 Jellyfin 12 以上**。10.10 / 10.11 的劇集原生多版本不可靠、要靠 MergeVersions 插件，12.0 起原生合併；還在 10.x 的使用者要先升級，而升級不可逆（brief §19、§20.9）。12.x 會把多集檔與同起始集的單集併成一集（brief §7.7、§7.8、§20.9）。
- 秘密（API key、密碼）存在 SQLite，只靠檔案權限保護，不做應用層加密（brief §16.2）。

**前端既定技術**（plan §1.4、§7，已實作到 repo）：React 19、TypeScript、Vite、Tailwind v4、
TanStack Router 與 Query、react-i18next。不用 shadcn/ui（2026-09-22 結案）；媒體卡片、狀態徽章、
時間線、Plan 表格、檔案樹全是專案自有元件。

**API-first**（brief §14）：UI 的每個動作都是一個有名字、有 schema、冪等的服務命令；Plan、Event、Issue
都是結構化 JSON。這是為了之後接 AI 與 MCP 留的形狀，不是現在要做 agent 迴圈。

**季集來源是 TMDB**（brief §10，2026-09-09 M1 票 01 定案）：TVDB 不採用。TMDB 是媒體牆、標題、海報、
季集與電影的唯一來源。

## Brand Commitments

- **名稱**：Berth（brief §1.4）。船席——torrent 靠岸、卸貨、入倉。五個字母，直接用作 Docker service 名、
  CLI 名與 qBittorrent 的 category 前綴（`berth-*`）。名稱衝突已查核可用（brief §20.5）。
- **視覺識別**：**沒有**。Berth 目前沒有 logo、沒有品牌配色、沒有指定字體。`docs/assets/tmdb.svg` 是
  第三方 TMDB 的官方標誌，不是 Berth 的。任何視覺世界都在 DESIGN.md 建立，不是既有約束。
- **語氣**：文檔未明文規定。已知的只有錯誤訊息的要求——失敗時要給出可複製的手動步驟，並指出是哪個容器
  少了哪個掛載（票 06、09、10 的驗收）。
- **i18n 規則**：UI 文案一律走 i18n key，不硬編。檔名 token、log 訊息、程式碼識別符維持英文（brief §16.2）。
  UI 語言為 zh-Hant 與 en 並列（見 `## Users` 的散佈範圍）。

## Evidence on Hand

- `docs/assets/tmdb.svg` —— TMDB 官方標誌，README 的歸屬區塊已使用。
- README 已含 TMDB 的法定聲明（中英雙語）：「This product uses the TMDB API but is not endorsed or
  certified by TMDB.」TMDB 條款限非商業使用（brief §20.3）。任何介面上出現 TMDB 資料的地方都要帶這個歸屬。
- `LICENSE` —— MIT（brief §16.2、§19）。
- `docs/research/m0-experiments.md` —— 對真實 Jellyfin 10.10 / 10.11 與 qBittorrent 4.4 / 5.2 的實測結果，
  命名模板與 API 行為以它為準；Jellyfin 12（Berth 支援的唯一版本線）與它不同的地方，以 `docs/research/jellyfin-12.md` 為準。

**目前沒有、不可捏造**：使用者見證、使用者數、效能數據、任何「已有 N 人在用」的說法。Berth 做到 M2
（手動全流程、媒體庫瀏覽、修正與對帳），還沒有 RSS（M3），README 明說這件事。

## Product Principles

1. **一個介面完成所有事。** 使用者不該為了設定或修錯而打開 qBittorrent、Jellyfin 或 Prowlarr 的介面。
   M0 的驗收條件字面上就是「全程沒開過另外三個服務的介面」。
2. **動手前先給看。** Plan 在套用前不碰任何檔案；差異先顯示再套用；破壞性動作要二次確認並說明後果。
3. **寧可停下來問，不要默默做錯。** 低信心進審核佇列，medium 自動入庫但留可撤銷的 audit 旗標。
   誤自動入庫的成本遠高於多問一次。
4. **失敗要說得出下一步。** 每個錯誤都要指出具體原因（哪個掛載、哪個版本、哪個 header），
   並給可複製的手動修正步驟。「連線失敗」不是可接受的訊息。
5. **一切可追溯、可修復。** 每次入庫都有帳本紀錄，Reconciler 定期對帳，不一致以 Issue 呈現而非靜默。

## Accessibility & Inclusion

目標是 **WCAG 2.2 AA**（2026-09-07 使用者決定；brief 與 plan 原本未提及無障礙）。實務底線：

- 每個任務都能純鍵盤完成，焦點永遠可見，Tab 順序符合視覺順序。
- 文字與必要的非文字對比達 AA 數值。深淺兩個主題都要達標。
- 狀態不只靠顏色表達——健康、信心、Job 狀態都要有文字或形狀的第二訊號。
- 表單錯誤與非同步結果要能被輔助技術讀到（`aria-live`、可程式關聯的錯誤訊息）。
- 這是驗收條件，不是加分項；`/impeccable audit` 逐頁檢查。
