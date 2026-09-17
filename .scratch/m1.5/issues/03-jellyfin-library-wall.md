# 03 — 媒體庫頁改成瀏覽整個 Jellyfin 媒體庫（權限閘門）

**Status:** ready-for-agent

**Blocked by:** 01、02

**讀:** plan §2.1、§6（auth、inventory）、§7、§8.2、§11.2b；brief §11、§12、§13（媒體庫）、§19（M1.5 拆票前的
四條、顯示用標題的語言）、§20.8；`docs/research/library-browsing.md` §2、§3.1、§7、§9；票 01 的結論；
`.scratch/m1/library-shape.md`；`CONTEXT.md` 的 **Inventory**、**Jellyfin Library**

## 做什麼

M1.5 的 tracer bullet。媒體庫頁從「一條 Route 一頁、只列 Berth 經手的作品」（票 13）改成「一個 Jellyfin
媒體庫一頁、整個媒體庫」：一般使用者打開它，看到的是自己在 Jellyfin 看得到的那幾個媒體庫與裡面的每一部
作品，包括不是 Berth 入庫的；Berth 經手的作品疊上票 13 的入庫狀態，還沒進 Jellyfin 的（下載中、待審、
卡住）仍然在牆上。

**權限是這一票的核心**，集中在 services 的一處，後面的每一張票都經過它（plan §11.2b 前置、研究 §9 第 1 點）：

- Jellyfin 的 `userId` 一律取自 session，絕不收前端傳入。
- 媒體庫 id 對這位使用者的 `GET /UserViews?userId=` 允許清單驗證，不在清單就拒絕、不轉發。
- 取允許清單時一併讀帳號的 `Policy`，兩者同一份短時間快取；帳號被停用就結束 Berth 的 session。
- 單一作品與集的讀取走會檢查可見性的端點（依票 01 的實測結果），不用 `/Items?ids=`。

**名稱**：牆上已在 Jellyfin 裡的作品顯示 Jellyfin 的名稱（拆票時使用者拍板，brief §7.5）；還沒進 Jellyfin 的
卡片沿用票 02 的規則，跟著 UI 語言。

**連結**：有 TMDB id 的作品連 `/media/:id`（探索與媒體庫共用詳情頁）；沒有的只給 Jellyfin 深連結。牆上的
作品本來就帶 Jellyfin item id，所以票 13 留下的「反查完卻沒有 `jellyfin_series_id`、卡片一直說還在掃描」
對已在 Jellyfin 裡的作品不再發生——Berth 的作品與 Jellyfin 的作品之間的對應**不能只靠帳本的
`jellyfin_series_id`**。

海報是票 04（本票沒有 Jellyfin 圖的卡片用佔位）；觀看狀態、排序篩選、繼續觀看與下一集是票 05–07。
shape 要替它們留位置，就像 M1 票 04 替票 08、13 留位置那樣。還沒進 Jellyfin 的作品放在哪（混在分頁牆裡還是
另一列）在 shape 定——牆的分頁與排序來自 Jellyfin，那些作品不在 Jellyfin 的結果裡。

## 驗收

- [ ] 媒體庫頁一個 Jellyfin 媒體庫一頁（取代 `/library/:routeSlug`），切換列只列這位使用者 `UserViews` 裡、
      Berth 瀏覽得了的媒體庫類型（電影、劇集）；`/library` 導向第一個
- [ ] 牆上是該媒體庫的全部 Series / Movie（含非 Berth 入庫的），大媒體庫分頁
- [ ] Berth 經手的作品疊上入庫狀態；還沒進 Jellyfin 的作品仍在頁面上；「待審」「Unmatched」兩個篩選保留
- [ ] 已在 Jellyfin 裡的作品顯示 Jellyfin 的名稱；有 TMDB id 的連 `/media/:id`，沒有的只給 Jellyfin 深連結
- [ ] 權限集中在 services 一處；整合測試證明：不在允許清單的媒體庫 id 被拒且**沒有轉發給 Jellyfin**（Fake
      記錄不到那次查詢）、前端塞進來的 `userId` 不起作用、帳號被停用後 session 結束且下一個請求是 401
- [ ] 允許清單與 `Policy` 共用一份短時間快取，快取時間有常數與理由
- [ ] adapter 新方法有 Fake 與契約測試（用票 01 錄的 fixture）；每個過濾參數有「伺服器真的有過濾」的斷言
- [ ] Jellyfin 連不上時頁面說得出原因，不是空白牆
- [ ] `CONTEXT.md` 的 **Inventory** 改定義；plan §6（inventory 群組）、§7（路由）同步改
- [ ] `fake_setup_server.py` 有一個能演整庫瀏覽與受限使用者的情境，README 的情境表同步
- [ ] 媒體庫頁走 `/impeccable shape`（`.scratch/m1.5/library-shape.md`）；playwright 實跑並附結果，含受限使用者
- [ ] 對比 ≥ 4.5:1；390px 窄版可用；zh-Hant 與 en 並列
- [ ] lint / type / test 全綠並貼指令輸出
