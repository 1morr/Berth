# Berth

自託管的媒體取得與入庫協調器：把索引站或 RSS 命中的 torrent 送到 qBittorrent，下載完成後解析、比對 TMDB、以硬鏈接入庫到 Jellyfin，並維護可修復的帳本。本檔只是名詞表；決定與事實在 `docs/design-brief.md`，實作在 `docs/plan.md`。

## Language

### 媒體與目的地

**Media**:
TMDB 上的一部電影或一部劇集，鍵為 `movie:<tmdb id>` / `tv:<tmdb id>`；劇集底下有 Season 與 Episode，編號沿用 TMDB。
_Avoid_: title, show, series, item

**Tracked Media**:
Berth 曾為其下載、訂閱或入庫過的 Media。
_Avoid_: subscribed media, library item

**Library Route**（UI 顯示「媒體庫」）:
一個入庫目的地：Jellyfin 媒體庫、一個寫入目標路徑、一個 qBittorrent category。
_Avoid_: root folder, destination；程式碼中不要用 `library` 指 Route（`library` 一律指下一條的 Jellyfin Library）

**Inventory**（UI 顯示「媒體庫」頁）:
一個 Jellyfin Library 的整面牆（這位使用者在 Jellyfin 看得到的那幾個之一），疊上 Berth 經手作品的入庫
狀態。牆上是 Jellyfin 的每一部作品、分頁與排序照 Jellyfin，可依類型、年份篩選（M1.5 票 06，只篩 Jellyfin 那一頁）；Berth 經手的作品是指向這個媒體庫的每一條 Route 上
有 Job 的，加上帳本目標落在它們底下的——在 Jellyfin 裡的疊到那一格，還沒進的另列一條。M1（票 13）時
它是一條 Route 一頁、只有 Berth 經手的作品，M1.5 票 03 改成現在的定義。
_Avoid_: library（程式碼中，那是下一條的 Jellyfin Library）, collection, shelf

**Narrowing**（UI 顯示「類型」「年份」）:
Inventory 牆上依類型、年份縮小 **Jellyfin 那一頁**（M1.5 票 06）；同一種之間是「或」、兩種之間是「且」。它和牆的排序合稱
**Wall Query**（`WallQuery`：`sort`、`order`、`genres`、`years`）。選項清單在程式碼裡叫 `filters`（`/Items/Filters`、
`GET /api/inventory/{id}/filters`），沿用 Jellyfin 的名字；前端的開關與面板叫 narrowing。**不是**「待審」「Unmatched」
那兩個 filter：那兩個篩的是 Berth 經手的作品清單，Jellyfin 的類型套不上。
_Avoid_: filter（指類型、年份時）, facet

**Watch State**（UI 顯示「觀看狀態」）:
一位使用者在 Jellyfin 對一部作品（或一集）的觀看紀錄，Inventory 的卡片上一行字：**已看**、**看到 N%**（只有影片）、
**剩 N 集沒看**（只有劇集，沒開始看的也算），都不成立就是還沒看過。紀錄存在 Jellyfin、屬於那個人，Berth 不存；
Berth 只讀它，並替那個人**標為已看 / 標為未看**（寫回 Jellyfin）。標為未看會清掉觀看次數與最後觀看時間，對劇集是
每一集，復原不了；標為已看會把看到一半的位置歸零（對劇集是每一集），所以兩者清得掉東西時都先確認（M1.5 票 08）。
_Avoid_: seen, history, played state

**Resume**（UI 顯示「繼續觀看」）:
一位使用者在 Jellyfin 看到一半的集與電影（Jellyfin `/UserItems/Resume`），最近看的在前；卡片說的是看到幾 %，看過又重看
到一半的片也算。首頁上方是整個帳號的，Inventory 頁上方只含那個 Jellyfin Library 的（M1.5 票 07）。
_Avoid_: continue, in progress, recently watched

**Next Up**（UI 顯示「下一集」）:
一位使用者每部看過的劇的下一集（Jellyfin `/Shows/NextUp`）：最後看過的那一集之後、還沒看的第一集。看到一半的集不算
（它在 Resume），一年內沒看過的劇也不算（jellyfin-web 的預設）；範圍同 Resume。兩者合稱 **Watching**
（`services/watching.py`、`WatchingOut`）。
_Avoid_: upcoming, next episode（TMDB 的「下一集播出」是另一件事）, queue

**Watch Area**（UI 顯示「觀看」）:
Media 詳情最上面那一塊：作品在 Jellyfin 裡、而且這位使用者看得到時才有——身分帶裡的主按鈕（**Carry On**），加上 Jellyfin
的季切換與那一季的集（`services/watch_area.py`、`GET /api/media/{id}/watch`，M1.5 票 08）。季與集是 Jellyfin 的，不是 Media 的
Season / Episode（那一份在下面的「季集與入庫」）。不在 Jellyfin 與看不到是同一個答案：沒有這一塊。
_Avoid_: player, playback area, library detail

**Carry On**（UI 在主按鈕上：「繼續看」「看下一集」「從 S01E01 開始看」）:
這位使用者接下來看這部劇的哪一集：Jellyfin 的 NextUp 帶 `seriesId`——看到一半的那一集也算、沒看過是第一集、看完了就沒有。
與 **Next Up** 不同：那是首頁一整列、每部看過的劇一格，看到一半的不算、沒看過的劇不列。電影沒有 Carry On，主按鈕開那一部。
_Avoid_: next up（指這一顆時）, resume point, up next

**Jellyfin Library**（UI 顯示「Jellyfin 媒體庫」）:
Jellyfin 那一端的 virtual folder：一個名字、一個 collection type、**一到多條**路徑。Berth 不擁有它——
套件內的 Jellyfin 由 Berth 建三個（Movies / TV / Anime），既有的一律只讀，最多加一條路徑。
一個 Library Route 指向它的其中一條路徑。程式碼中的 `library` 指的就是這個。
_Avoid_: virtual folder（對使用者時）, folder, collection

**Library root**:
媒體庫路徑的父目錄（設定值，預設 `/data/library`）。Berth 與 Jellyfin 把同一個宿主目錄掛在同一個
容器路徑，所以這一個字串對兩邊都成立。
_Avoid_: media root, library path（那是單一媒體庫的路徑）

**Berth path**（UI 顯示「Berth 寫入」）:
Library root 底下、Berth 寫入用的那一條路徑（`<library root>/<slug>`）。既有 Jellyfin 是**加**這一條，
舊路徑原地不動。
_Avoid_: target path（那是 Route 上的欄位）, new path

**Complete / Incomplete root**:
qBittorrent 的完成與未完成下載根目錄；complete 是硬鏈接的來源。
_Avoid_: download folder, save path（僅指 qBittorrent 的欄位時可用）

### 設定

**Service**:
Berth 協調的三個外部服務之一：Jellyfin、qBittorrent、Prowlarr。字串同時是 compose 的服務名。
_Avoid_: integration, provider（Provider 專指 metadata provider）

**Service Origin**:
精靈對單一服務的判定：`bundled`（套件內，Berth 全自動接手）或 `existing`（既有，使用者自己的那一台）。
逐服務判斷，沒有全局模式；探測中與逾時是輪詢期間的暫時值。**與 Trigger 的「來源」無關**。
_Avoid_: mode, service type

**Bundled service**（UI 顯示「套件內」）:
compose 起的、而且還沒被設定過的服務。判準逐服務不同：Jellyfin 的 `StartupWizardCompleted=false`、
qBittorrent 免密進得去、Prowlarr 讀得到 API key 且無索引站。
_Avoid_: managed, built-in, ours

**Existing service**（UI 顯示「既有」）:
使用者自己的服務，或不在這套 compose 裡的服務。Berth 只做檢查，改動一律要按鈕確認。
_Avoid_: external, remote, byo

**Step status**（UI 顯示於每一條纜繩）:
精靈裡一個步驟的結果，五種：`ok`（已完成，這一次真的做了）、`skipped`（已經是這樣，沒動它）、
`running`（進行中，做之前就寫進設定所以輪詢看得到）、`failed`（失敗）、`pending`（尚未執行）。
**`skipped` 不是「跳過不做」**，是「已經是想要的樣子」——重按精靈時大部分步驟都會是它。
_Avoid_: success/error（那是 HTTP 的詞）, done（`ok` 與 `skipped` 都算做完）

**Berth（泊位）**:
設定精靈把八個步驟歸成的四格：Jellyfin、qBittorrent、來源（索引站與 RSS）、媒體庫路徑。
只在精靈與泊位板上用；與產品名 Berth 同字，指的是畫面上那一格。
_Avoid_: stage, section, panel

### 取得

**Download Job**（簡稱 Job）:
一個 torrent 在 Berth 中的生命週期紀錄，以 info hash 為鍵。
_Avoid_: torrent（指 Job 時）, download, task

**Trigger**:
Job 的來源：`manual`、`rss:<rule>`、`reimport`。
_Avoid_: source, origin

**Indexer Result**:
索引站的協定回的原始一列：發佈名、大小、做種、來源站、下載連結、info hash。**還沒經過解析器**。
_Avoid_: hit, item, row

**Search Result**:
索引站回傳的一筆候選 torrent，附解析出的 Tags 與預估季集。也就是 Indexer Result 過了解析器之後的樣子。
_Avoid_: release（僅指發佈名解析時可用）

**Missing Episode Search**（UI 顯示「搜這部作品缺的集」/「搜 S01 缺的集」）:
從季表上缺的那幾集開始的搜尋：查詢由後端依缺的季集產生（整季缺問季包、缺幾集逐集問、有絕對編號的用絕對編號），
不是作品名。範圍是整部作品或一季。
_Avoid_: gap search, 補集, 一鍵補齊

### 入庫

**Import Source**:
待入庫的檔案集合：Job 的內容目錄，或 complete 下的任一目錄（重新入庫時）。
_Avoid_: input, folder

**Release Info**:
從發佈名或檔名解析出的結構化欄位（標題候選、季、集、版本、字幕組、來源、解析度、字幕語言…）。
_Avoid_: parse result, metadata

**Tags**:
一個檔案版本的可辨識屬性集合（source、resolution、subs、hardsub、group、version、edition），以固定 token 渲染進檔名。
_Avoid_: quality, flags, labels

**Candidate**:
對一個影片檔的一種季集對應，附策略、信心與理由。
_Avoid_: match, guess

**Mapping Strategy**（簡稱 Strategy）:
Candidate 的季集是怎麼決定的：explicit / folder / context / arc_name / single_season /
absolute_group / absolute_cumulative / air_date_offset / cour_offset / movie。
_Avoid_: method, rule, source

**Arc name**（篇章名）:
一輪播出的名字而不是季號（`柱訓練篇`、`Hashira Training Arc`、`最終季`）。對到 TMDB 的季名就
等同季號提示。
_Avoid_: subtitle, part name

**Cour**:
同一季裡的一輪播出（`第二部分` / `Part.2`）。字幕組可能每個 cour 從 01 重數，也可能季內連號。
_Avoid_: part（`Part 2` 是檔名裡的寫法，不是這個概念的名字）, half

**Virtual season**（虛擬季）:
TMDB 把好幾輪播出併成一季時，用季內 `air_date` 間隔（> 180 天）切回來的那一輪。
_Avoid_: split season, sub-season

**Import Plan**（簡稱 Plan）:
對一個 Import Source 逐檔決定分類、對應 Media / 季 / 集、目標路徑、Tags、信心與理由的可審核計劃；套用前不動任何檔案。
_Avoid_: mapping, import job, rename plan

**Pre-plan**（預先計劃）:
`metadata_ready` 之後、下載完成之前先算的那一份 Plan（`plans.status = preplan`）：不讀檔案、不動狀態，只回答「這一包對不對、還來得及取消嗎」。
_Avoid_: draft plan, preview

**Review Reason**（停下來的理由）:
一份 Plan 停在 review 的四種理由：`low_confidence`、`medium_not_allowed`、`nothing_to_import`，以及入庫途中目標上已經有別人的檔案的 `target_exists`。四種的下一步不同，所以是封閉集合而不是一句話。
_Avoid_: error, message

**Plan Item**:
Plan 中一個檔案的決定，`action` 為 import / extra / subtitle / skip / unmatched / review。
_Avoid_: entry, row

**Confidence**:
Plan Item 的三級信心：high、medium、low。high 與 medium 自動入庫，low 進 Review Queue。
_Avoid_: score, probability

**Audit**:
medium 信心自動入庫後掛的旗標，在 Review Queue 顯示為「已入庫待確認」。
_Avoid_: pending, provisional

**Folder Name**（資料夾名）:
作品在媒體庫裡的資料夾：`Title (Year) [tmdbid-N]`。在第一次送單成功那一刻凍結，之後 TMDB 改名不動它，計劃與入庫都照凍結的那一串寫；在那之前它跟著標題走，畫面上是「將會是」。
_Avoid_: directory name, slug（slug 是 Route 的）

**Version**（版本）:
同一集或同一部電影並存的其中一個檔案，以 Tags 區分。版本選單上的名字由 Jellyfin 算（12 起原生合併），Berth 只抄下來。
_Avoid_: copy, duplicate（Tags 完全相同的才是重複）

**Resolve**（反查）:
入庫之後向 Jellyfin 問出那個檔案是哪一個 item（劇集再加它的 Series）。延遲、會重試，排程存在帳本上；找到之前卡片說「Jellyfin 還在掃描」。
_Avoid_: sync, lookup, match

**Ledger Entry**:
一條「來源檔案 → 目標硬鏈接」的紀錄，含 hash、來源相對路徑、目標路徑、inode、Media / 季 / 集、Tags、plan item、Jellyfin item id。
_Avoid_: link record, file record, history

**Benchmark Corpus**（語料）:
凍結的真實 torrent 檔案清單加上逐檔正解與 TMDB 快照（`tests/fixtures/parser/`）。`berth bench` 在它上面量解析器，門檻是 `auto_wrong`（自動處置但處置錯）不得上升。e2e 也從它取三包發佈。
_Avoid_: dataset, test data

**Extras**:
可辨識但不屬於正片的內容（NCOP / NCED、PV、CM、Menu、預告、花絮、特典映像），入庫到 Jellyfin 的 `extras/`。
_Avoid_: bonus, specials（Specials 指 TMDB season 0）

**Unmatched**:
解析後對不到 TMDB 任何一集或一部的影片或字幕檔；留在 complete，不入庫。
_Avoid_: unknown, orphan（Orphan 是對帳用語）

**Review Queue**:
需要人工處理的統一清單：低信心 Plan、Audit、Unmatched、重複版本、Issue。
_Avoid_: inbox, pending list, interactive import

**Rematch**:
把已入庫或 Unmatched 的檔案改指派到另一季集、標為 Extra 或忽略；一律經過 Plan。
_Avoid_: fix, remap, move

**Reimport**:
以 complete 下的目錄為 Import Source 重新入庫。
_Avoid_: re-run, resync

### 修復

**Reconciler**:
比對帳本、qBittorrent、complete 目錄、library 目錄四方一致性的排程工作。
_Avoid_: scanner, sync, health check（Health Check 指服務與 Route 連線）

**Issue**:
Reconciler 或管線發現的不一致，有固定型別（library_link_missing、source_missing、inode_mismatch、orphan_complete、unknown_torrent、unmanaged_library_file、job_without_files）。
_Avoid_: error, problem, orphan（僅作 Issue 型別名的一部分）

**Unmanaged**:
library 內不是 Berth 建立的檔案；只列出，永不刪除。
_Avoid_: foreign, external, legacy

**Delete Scope**:
刪除時可組合的四個旗標：移除 library 鏈接、從 qBittorrent 移除 torrent、刪除 complete 檔案、清除帳本。
_Avoid_: purge level, cleanup mode

**Health Check**:
對服務連線、版本、Route 硬鏈接與跨服務可見性的檢查，結果顯示在健康頁。**四項**：Jellyfin、
qBittorrent、索引站、Route；前三項對應精靈的前三個泊位，第四項是所有 Route 的總結。
背景迴圈每 5 分鐘跑一次，也可以在畫面上按「立即重測」。
_Avoid_: diagnostics, status check

**Drift（設定漂移）**:
Berth 建議的 qBittorrent 偏好被改成別的值。**不是紅燈**——那台服務還在動，只是下載路徑或
自動管理一旦不對，入庫遲早會失敗；畫面用 `assigned`（需要你）而不是 `blocked`，
並在服務設定頁給逐鍵差異與「還原建議設定」。
_Avoid_: mismatch, out of sync, misconfiguration

**Event**:
Job 時間線上的一筆事件：型別、時間、actor、payload。
_Avoid_: log, activity, history

### RSS

**Feed**:
一個 RSS 來源（Mikan、Nyaa、generic），有輪詢間隔。
_Avoid_: subscription（Subscription 是 UI 上「訂閱一部作品」的動作）, source

**Rule**:
綁定 Media 與 Route 的自動下載規則：包含 / 排除條件、字幕組、解析度、字幕偏好、季與集 offset、策略。
_Avoid_: filter, subscription rule, watch

**Feed Item**:
Feed 中的一筆項目及其解析與比對結果（new / matched / downloaded / ignored / unmatched）。
_Avoid_: entry, post
