# 11 — M1.5 驗收與里程碑收尾

**Status:** in-progress

**Blocked by:** 06、09、10

**讀:** plan §10（e2e）、§11.2b（驗收）；brief §17（M1.5 那一列）；`.scratch/m1/issues/15-m1-acceptance.md`（M1 收尾的做法）

## 做什麼

把 M1.5 的驗收釘進 CI，然後收尾。

**e2e 加上權限與瀏覽**（拆票時使用者拍板放進 e2e，每晚對真的 Jellyfin 12.1 跑）：在 M1 那一套 compose 上，以
Jellyfin API 建一個只開放一個媒體庫的一般使用者，用它登入 Berth，驗證：

- 看不到沒權限的媒體庫，直接請求那個媒體庫被拒；
- 不是 Berth 入庫的作品在牆上瀏覽得到（e2e 要自己放一部不經 Berth 的作品進 Jellyfin）；
- 標為已看之後 Jellyfin 那一端該使用者的 `UserData` 真的變了，標回未看也是；
- 某一集的播放連結指向 Jellyfin 的那一集；
- 帳號在 Jellyfin 被停用之後，Berth 的 session 結束。

**真環境走一次 brief §17 的驗收**：以一般使用者（`user` 角色）登入，不開 Jellyfin Web 就從媒體庫找到要看的那一集、
看到自己的進度並標記已看，按播放落在 Jellyfin 的那一集。

收尾包含 M1.5 新頁面與改過的頁面的 `/impeccable critique`、`audit`、`polish`，以及票 01–10 的 Comments 逐條
過完——該延後的寫進 plan §11.3 以後的里程碑而不是另開票（M1 票 15 的先例）。

## 驗收

- [ ] e2e 以受限的一般使用者驗證上面五件事，GitHub Actions 的 `e2e.yml` 綠燈（附執行紀錄）——**本機那一輪已綠（10 passed），Actions 那一次要等 push；`origin/main` 還停在 M1 收尾**
- [x] brief §17 M1.5 的驗收在真環境以 `user` 角色實跑一次並附證據
- [x] `/impeccable critique`、`audit`、`polish` 對 M1.5 的頁面跑完，發現逐條處理或明確記錄為延後
- [x] `DESIGN.md` 依 M1.5 實際做出來的東西更新
- [x] README、CHANGELOG、CONTEXT.md 更新；plan §10 的 e2e 範圍同步改
- [x] 票 01–10 的 Comments 逐條過完；延後的寫進 plan 對應的里程碑，並在 `docs/progress.md` 記錄
- [x] lint / type / test / benchmark 門檻 / 前端測試全綠並貼指令輸出

## 驗證（2026-09-19）

```
$ uv run ruff check . && uv run ruff format --check .
All checks passed!
$ uv run mypy
Success: no issues found in 221 source files
$ uv run lint-imports
Contracts: 6 kept, 0 broken.
$ uv run pytest -m 'not e2e'
1573 passed, 10 deselected in 168.30s (0:02:48)
$ uv run berth bench
overall   385    385/385   188/188  171/171     172           0           79      0       42   41   37   14
high: 0/84 wrong (0.0%)  medium: 0/88 wrong (0.0%)
$ pnpm -C web lint && pnpm -C web format:check && pnpm -C web typecheck
All matched files use Prettier code style!
$ pnpm -C web test
 Test Files  27 passed (27)
      Tests  435 passed (435)
$ pnpm -C web build
✓ built in 223ms
$ pnpm -C web gen:api && git diff --exit-code -- web/src/api/schema.d.ts
（只有這一輪新增的三個 poster_url_en）
$ uv run pre-commit run --all-files
（12 個 hook 全部 Passed）
```

`berth bench` 與 baseline 相同（172 / 0）。

**e2e**（`tests/e2e/`，一輪 compose 兩個模組）：

| 在哪裡 | 結果 |
| --- | --- |
| 本機 Docker Desktop（乾淨重建，`down --volumes` 後 `up --build`） | **10 passed in 879.68s（14:39）** |

**brief §17 M1.5 的真環境驗收**（同一套 compose，真的 Jellyfin 12.1，以 `deckhand` 這個只開放 TV 媒體庫的
一般使用者登入 Berth，全程沒有打開 Jellyfin Web）：

- 切換列只有 TV（Movies 與 Anime 是他沒有權限的，牆上與切換列都沒有）；
- 牆上是「大熊餐廳 · 部分 · 剩 10 集沒看 · 10 / 46 集入庫」，旁邊是 e2e 放進去、不經 Berth 的
  `Harbour Test Footage`；
- 詳情頁最上面是觀看區，主按鈕「看下一集 S03E01」連到
  `http://127.0.0.1:8096/web/#/details?id=0ee15e70738cc8dbf131ee7acd6e09ac`——那個 id 在 Jellyfin 上是
  `Episode S03E01 翌日`，路徑是 `/data/library/tv/The Bear (2022) [tmdbid-136315]/Season 03/The Bear (2022) - S03E01 - Tomorrow [WEB][1080p][SuccessfulCrab].mkv`（Berth 入庫的那一條）；
- 在 Berth 上把 S03E01 標為已看之後，Jellyfin 那一端**這個帳號**的紀錄是
  `S03E01 Played=True PlayCount=1`、`S03E02/E03 Played=False`，劇的 `UnplayedItemCount` 由 10 變 9；
  畫面同時換成「剩 9 集沒看」、主按鈕變「看下一集 S03E02」。

截圖 `.playwright-mcp/t11-real-user-watch.png`（不進版控）。

## Comments

### e2e 的做法與這一輪抓到的

- **`origin/main` 停在 M1 收尾（`bbbf9e5`），M1.5 的 21 個 commit 一個都沒 push。** 所以 2026-09-17 與
  09-18 兩次 nightly 的 `e2e.yml` 綠燈跑的是 **M1 的程式碼**，不是工作目錄裡的 M1.5——票 03 把
  `/api/inventory/{id}` 從 route slug 改成 Jellyfin 媒體庫 id 之後，e2e 其實已經對不上了，只是 CI 看不到。
  這一票把 e2e 改好之後才 push。
- **兩個模組共用一輪**：精靈、送單、放位元組、等入庫與反查搬到 `tests/e2e/conftest.py`，全部
  `scope="session"`；`test_1_m1_pipeline.py` 只剩四條斷言，`test_2_m15_library.py` 疊在它之上。
  檔名的數字就是執行順序（pytest 照檔名收集），因為最後兩條會停用帳號、停掉 Jellyfin 容器。
- **重構引入、第一輪 e2e 抓到的兩個 fixture 錯**：(1) `jellyfin_client()` 在回傳前已經登入過，client
  已經是 `OPENED`，再 `with` 它會被 httpx 當成「同一個 client 開第二次」擋下來（收尾改用 `closing()`）；
  (2) `jellyfin` fixture 沒有相依 `configured`，M1.5 那個模組先跑時它在精靈建出管理員之前就去登入，
  `AuthenticateByName` 回 401。兩個都只有真的跑起來才看得到。
- **Jellyfin 把資料夾名裡的年份拆進 `ProductionYear`**：`Harbour Test Footage (2019)` 索引出來的 `Name`
  是 `Harbour Test Footage`，牆上顯示的也是它（`year` 另外一格）。第一輪 `searchTerm` 帶著年份，等了 600 秒
  才發現它其實早就索引好了。
- **重跑要先 `down --volumes`**：`POST /jobs` 對已經在的 torrent 回既有的 job（`imported`），精靈也不能再走
  一遍。這一輪為了驗新斷言用過一次「短路 `configured`」，收尾時拿掉了——那是 CI 永遠走不到的第二條路徑。

### 實測到與研究文件不符的一件事

- **`GET /Items/{集}?userId=` 的 `UserData` 讀不到整部劇遞迴標記的結果**。研究 §5 寫「對 Series / Season
  標記會遞迴到底下的集【實測 12.1.0】」，這一輪一開始照它拿單項端點讀回，量到的是 `Played=false`。追下去：
  同一集的 `UserData.Key` 在單項端點是 provider 導出的（大熊餐廳 S03E01 是 `403294003001`），在
  `/Shows/{劇}/Episodes` 與 `/Items?ids=` 是 item id（`0ee15e70-738c-…`）；整部劇那一次遞迴寫的是後者，
  所以前者讀不到。**單集自己標記時兩把鍵都會更新**。遞迴本身沒有錯，錯的是讀回的端點。
  研究 §5 與 brief §20.8 已補這一條；e2e 的斷言一律走清單端點（Berth 讀的也是那一支）。

### 票 01–10 的 Comments 逐條判定

逐條的結果記在 `docs/progress.md` 的偏差與決定與 plan §11.3。分三類：

**這一輪修掉的（4）**
- 票 02 的「EN 介面的海報仍取 `zh-TW` 那一輪」——使用者在收尾時拍板現在做（`poster_url` / `poster_url_en`）。
- 票 04 的「CLAUDE.md『原型不留』與 `scripts/experiments/` 留腳本措辭不一致」——使用者拍板改措辭。
- 票 07 的「Jellyfin 連不上沒有實跑，票 11 的 e2e 可以補」——`test_2_m15_library.py` 最後一條停掉 Jellyfin 容器再起回來。
- 票 03 的「單一作品與集的讀取跟著第一個呼叫端加進 `jellyfin_access`」——票 05、08 已經做掉，這一輪確認。

**寫進 plan §11.3 交 M2 的（5）**
- 大媒體庫的代價沒量（票 03 的 `library_index` 無快取、票 08 的由 TMDB id 找作品整份拿回來比、票 12 的整份 `MediaSources`）——三件事一起量再決定快取或分段取。
- 「待審」「Unmatched」篩選後的牆沒有觀看狀態（票 05），與上一條同一個代價。
- 被刪掉的 Jellyfin 帳號沒有實測（票 03）；停用那一條已由這一輪的 e2e 對真服務驗過。
- 缺集散在六季以上時只退回作品名、不分批問（票 10）。
- critique 與 audit 的發現（見 plan §11.3 的兩個新段落）。

**判斷題，不排里程碑（其餘）**
票 01 的一次性實驗腳本形狀重複；票 02 的 `JobOut.media_title` 沒改名、`title` / `title_en` 成對出現在九個型別裡；
票 03 的兩個端點同形 try、`PAGE_KEY` 沒用 `GHOST_LINK`；票 04 的 `image_url` 寫死 `/api/jellyfin/...`、
`JellyfinImageType` / `ImageSize` 各一個成員；票 05 的 `api/jellyfin.py` Divergent Change、`mark_played` 的布林旗標、
`libraryId` 穿到 `WatchToggle`；票 06 的 adapter 四個過濾參數平鋪、`query` 一路傳；票 07 的 `watch.py` 與 `watching.py`
名字相近（各自對得上名詞表）；票 08 的 `jellyfin_link` 放在 `services/inventory.py`、`watch.*` 與 `inventory.watch.*`
兩個命名空間、`WatchTarget` 與 `MediaKind` 兩套字；票 09 的「只看缺集」不寫進網址、收起的段落 Ctrl+F 找不到；
票 10 的勾選幾集再搜、缺集模式不寫進網址。這些在票裡都已經寫明理由，這一輪沒有新證據推翻，維持原判。

**「隨機」排序跨頁會重洗**（票 06）仍是已知限制：Jellyfin 每次請求重新洗牌，jellyfin-web 相同，照它留著這個選項。

### 這一輪另外抓到的

- **`MediaTile` 自己寫了一份沒有 `onError` 的 `<img>`**（critique 的 Riley）與 **`Poster` 也是**（audit 的 P1）：
  票 04 做的 `ArtSlot` 只被媒體庫牆用到，探索牆與詳情頁的身份帶各留了一份舊的，所以壞掉的海報在那兩處會露出
  瀏覽器的破圖示。兩處都收掉了。
- **未登入的新分頁載入時 `/api/auth/me` 回 401 並記成一筆 console error**（audit 指出）：那是探測用的，屬預期行為。
  「console 0 error」對已登入的 session 成立，對冷啟不成立——記在這裡免得下一個人當成 bug。

### code-review 兩軸（基準 `9aa6245`）

**Standards 軸處理了的**：`WALL_GRID` 加 `items-start` 原本打到六個消費者，而就地確認只在媒體庫牆上，
其餘四處（探索牆、繼續觀看、觀看區的集）被順手拿掉了同排拉齊的行為——改成另一個常數
`WALL_GRID_CONFIRMABLE`，只給那兩個容器；**舊快照在 EN 介面會印「無海報」**（票 11 之前的列沒有
`poster_url_en`，而 Berth 手上就有那張圖）——讀進 view 與卡片時落回另一輪，兩條測試加變異驗證；
`Submitted` 與 `imports_of` 從 `conftest.py` 搬到 `harness.py`（conftest 是 pytest 的 plugin 不是 library）；
探索牆的壞圖與 zh-Hant 的「對不到 1」各補一條測試（兩條都做了變異驗證）；`Poster` 與測試的註釋把
TMDB 的圖說成 Berth 的圖片代理，改掉；`harness.py` 的 compose 註釋不準；CHANGELOG 的「五件事」改六件事。

**Standards 軸記下、沒改的**：`Poster.tsx` 與 `ArtSlot` 是同一段程式碼的第二份（外框不同，合併要讓
`ArtSlot` 多收一個 `className`，寫進 plan §11.3）；`?filter=` 現在有兩道閘門而 `routes.tsx` 那一道實際上
擋不住（實測 `useSearch` 原樣交出 `filter="nonsense"`，所以頁面那一道才是真的——型別守衛共用留給 M2）；
`tmdbText` 的名字與 docstring 還是「文字」但它現在也挑圖；`poster_url` / `poster_url_en` 維持成對不做成型別
（持久化與 wire 格式，改是破壞性變更；第 5 對出現時才抽挑選器）。

**Spec 軸處理了的**：**驗收第 1 條被我提前勾成 `[x]`** 而 GitHub Actions 那一次根本還沒跑（`origin/main`
仍停在 M1 收尾）——退回未勾；plan §11.3 宣稱「逐條的判定記在 `docs/progress.md`」但實際在票的 Comments，
改成實話並在 progress.md 補三類摘要；audit 與 polish 的紀錄補進 progress.md；CHANGELOG 漏了三條缺陷修復
與 `Unmatched` 的翻譯，補上；`Poster` 的 `onError` 補測試。

**Spec 軸記下、沒改的**：
- `assert viewer.get("/auth/me").status_code == 401` 單獨撐不起註解說的「session 是真的沒了」——閘門若改成
  每次請求重驗而不刪 session，這兩行照樣過。要分得出來得直接讀 session 表（e2e 已有在容器裡讀 sqlite 的先例）。
- `assert area["jellyfin"]["url"] or area["jellyfin"]["port"]` 是弱斷言；真正證明播放連結的是下面那段
  `item_id` 對 Jellyfin 的比對。
- 整部劇的遞迴只驗到**那一季**的每一集（語料只有一季，兩季以上沒有樣本）。
- brief §17 的真環境證據停在「連結目標正確」而不是真的按下去——刻意的（全程不開 Jellyfin Web），
  但票面寫的是「按播放落在 Jellyfin 的那一集」，落差記在這裡。
- 票 01–10 還有幾條 comment 沒有在任何紀錄裡點名：票 02 的 `services/media._fetch` 防禦分支走不到也沒刪、
  `FakeTmdbClient` 的三個 mapping 同形（這一輪又多了 `poster_translations`）；票 04 的 `fill_width` 等一起傳；
  票 05 的寫入失敗訊息與 401 送回登入頁仍只有 vitest（這一輪的 e2e 走的是 API 層）；票 06 的 `genres` 契約
  證據強度；票 08 的季集請求帶了用不到的 `fields`。都維持原判，記在這裡。
- critique 的幾條 minor 沒有落到任何紀錄：三頁的 `h1` 三種大小與兩種可見性、缺集搜之後關鍵字欄的
  placeholder 仍說「留空就用這部作品的各個名字」、`?page=2` 不畫那兩列但畫面上沒說、
  `/library/item-movies` 有 222 個 Tab 停留點。
