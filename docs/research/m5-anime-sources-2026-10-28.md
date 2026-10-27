# M5 動漫資料來源查證：Fribb/anime-lists、AniList、Bangumi（2026-10-28）

查證日期全部是 2026-10-28。承接 `docs/research/m5-ai-direction-2026-10-27/08-scenario-data-sources.md` §2.1、§2.2、§2.4，那邊已驗證的欄位與實測數字不重做，本檔只補授權、限流、錯誤格式與 UA。

## 結論

**(a) Fribb/anime-lists：執行時下載並在本機留一份做查詢，風險低，但 Fribb 倉庫本身沒有授權檔。**

- `Fribb/anime-lists` 根目錄沒有 `LICENSE`，GitHub 也不認得授權（`gh api repos/Fribb/anime-lists` 的 `license` 為 `null`，`/license` 回 404）。所以「Fribb 允許什麼」沒有明文可引；法律上等於保留所有權利，只有「公開倉庫、README 說明是給人拿去對照 ID 用」這個事實上的意圖。
- 它的資料來源是 `anime-offline-database`（ODbL 1.0 + DbCL 1.0）與 `Anime-Lists/anime-lists`（ScudLee 的 fork，無授權檔）。ODbL 明文允許商業與非商業使用、暫時或永久重製（§3.1），「使用」本身不需要署名；只有「公開傳遞」資料庫或「公開使用 Produced Work」才要署名（§4.2、§4.3），且衍生資料庫公開時要 share-alike（§4.4）。
- Berth 的做法（使用者自己的機器在執行時抓、存本機、只供自己查詢、不再散布）沒有觸發 §4.2 / §4.4。**不要把 `anime-list-full.json` 打包進 Berth 的 repo 或 Docker image**，那才是 redistribution（Fribb 無授權、上游是 ODbL）。
- 署名建議（便宜保險，ODbL §4.3 的範例句型）：在文件或 UI「關於」處寫 `Contains information from anime-offline-database (manami-project / cedya77), which is made available here under the Open Database License (ODbL).` 並連到 Fribb/anime-lists 與 Anime-Lists/anime-lists。
- 更新頻率：每週一次，週二 16:04 UTC 左右由 "automated list update" 提交（最近 10 筆都是每 7 天一次）。原始檔網址在預設分支 `master`：`https://raw.githubusercontent.com/Fribb/anime-lists/master/anime-list-full.json`。回應 `cache-control: max-age=300`，有 `ETag`，可用 `If-None-Match`。

**(b) AniList**：文件寫 90 req/min，但頁首警告目前降級為 **30 req/min**（臨時措施，不收提高上限申請）。另有 burst limiter。超限後 1 分鐘 timeout，回 HTTP 429 + `Retry-After`（秒）+ `X-RateLimit-Reset`（Unix 秒）+ `X-RateLimit-Remaining: 0`，body 是 `{"data": null, "errors": [{"message": "Too Many Requests.", "status": 429}]}`。client 必須：把上限當 30 設計；讀每個回應的 `X-RateLimit-Remaining`；收到 429 就依 `Retry-After` 暫停（沒有該標頭則用 `X-RateLimit-Reset` 換算，再沒有就等 60 秒），timeout 期間的任何請求都會延長問題，所以要全域排隊而不是各自重試；快取結果、不預抓全站（ToS 禁 hoarding / 當儲存服務）。文件沒有要求特定 User-Agent。

**(c) Bangumi UA**：非瀏覽器使用者必須帶「開發者個人 ID + 應用名稱」；分發的應用附版本號；開源專案附主頁；預設 UA 可能被禁用。格式例：`1morr/berth/<version> (https://github.com/<owner>/berth)`。`/calendar` 在官方 OpenAPI（`open-api/api.yml`）有記載；文件沒有任何速率數字。

---

## 1. Fribb/anime-lists

### 1.1 授權

- 來源：<https://github.com/Fribb/anime-lists>（`gh api repos/Fribb/anime-lists/git/trees/master`，2026-10-28）。根目錄內容：`.gitignore`、`README.md`、`anime-list-full.json`、`anime-list-mini.json`、`anime-lists-reduced.json`、`anime-offline-database-reduced.json`、`collections/`、`indices/`。**沒有 LICENSE / COPYING。**
- `gh api repos/Fribb/anime-lists --jq .license` → `null`；`gh api repos/Fribb/anime-lists/license` → `404 Not Found`。產生器 `Fribb/anime-lists-generator`（<https://github.com/Fribb/anime-lists-generator>）同樣 `license: null`。
- README 沒有任何授權或署名要求的字句（全文只描述格式、產生方式與「corrections have to be brought to those source projects」）。
- 搜尋 issue 標題含 license 的結果為空（`gh api search/issues`，`repo:Fribb/anime-lists license`）。
- 結論：沒有明文授權。實務上這是社群大量使用的對照表（Sonarr 周邊工具、Plex/Jellyfin 外掛等），但 Berth 不應重新散布該檔，只在執行時抓取。若將來要內建一份快照，需先在 Fribb 倉庫開 issue 請作者補授權（這是對他人倉庫的公開動作，屬全域規則「碰別人的東西」，要當次徵得同意）。

### 1.2 上游資料與授權

README「lists」一節：

> The lists are generated through the anime-lists-generator based on a couple of already existing lists and mappings from other repositories.
> 1. anime-offline-database (<https://github.com/cedya77/anime-offline-database>)
> 2. Anime-Lists/anime-lists (<https://github.com/Anime-Lists/anime-lists/>)

「Generation and Corrections」一節：缺 TMDB / TVDB / IMDB id 的條目會再用 TheMovieDB API 的 search 或 external ID 端點補齊。（來源：<https://github.com/Fribb/anime-lists/blob/master/README.md>）

**anime-offline-database**

- 原作者 manami-project 的倉庫 `manami-project/anime-offline-database` 已 archived（最後 release `2026-27`，2026-07-04）；Fribb 現在引用的是延續版 `cedya77/anime-offline-database`（`gh api repos/cedya77/anime-offline-database`，最近 push 2026-10-25）。
- 兩個倉庫的 `LICENSE` 開頭相同：
  > This dataset ("anime-offline-database" by "manami-project" on github.com) is made available under the Open Database License 1.0: http://opendatacommons.org/licenses/odbl/1.0/.
  > Any rights in individual contents of the database are licensed under the Database Contents License 1.0: http://opendatacommons.org/licenses/dbcl/1.0/
  （<https://github.com/manami-project/anime-offline-database/blob/master/LICENSE>、<https://github.com/cedya77/anime-offline-database/blob/main/LICENSE>）
- cedya77 README「Licence」：
  > The dataset is made available under the Open Database License v1.0 (LICENSE) with its contents under the Database Contents License v1.0, the same terms the original was published under. You are free to share and adapt it, including commercially, provided you attribute it, keep any redistributed database under the same licence, and do not use technical measures that restrict others from using it.
  > Attribution should name both this project and manami-project, whose work every entry here descends from.
  > Individual metadata providers hold their own rights over the data they publish.
  （<https://github.com/cedya77/anime-offline-database/blob/main/README.md>）
- ODbL 1.0 關鍵條款（LICENSE 全文內，章節號為 ODbL 原文）：
  - §3.1：「…grants to You a worldwide, royalty-free, non-exclusive, terminable (but only under Section 9) license to Use the Database for the duration of any applicable copyright and Database Rights. These rights explicitly include commercial use, and do not exclude any field of endeavour.」授權範圍含「d. Creation of temporary or permanent reproductions by any means and in any form, in whole or in part」。
  - §4.2：只在「Publicly Convey」資料庫 / 衍生資料庫時要附授權副本或 URI、保留版權聲明。
  - §4.3：「if you Publicly Use a Produced Work, You must include a notice … Contains information from DATABASE NAME, which is made available here under the Open Database License (ODbL).」
  - §4.4：「Any Derivative Database that You Publicly Use must be only under the terms of: i. This License; ii. A later version…; iii. A compatible license.」
- 判讀（非法律意見）：自託管、本機使用、不公開傳遞資料庫，則不觸發 §4.2 與 §4.4；Berth UI 若把由此查到的結果「公開」展示給第三方才碰到 §4.3，加一行署名即可。

**Anime-Lists/anime-lists（ScudLee 系）**

- `Anime-Lists/anime-lists` 是 fork（parent `ScudLee/anime-lists`），最近提交 2026-10-24；`ScudLee/anime-lists` 本身最後 push 2023-04-25。兩者 `license: null`，根目錄只有 `README.md`、`anime-list*.xml`、`animetitles.xml`、`generate-lists.*`、`update.*`、`transforms/`，**沒有授權檔**；README 對 license / attribution / copyright 無相關字句（`gh api ... contents`，2026-10-28）。

### 1.3 更新頻率

`gh api "repos/Fribb/anime-lists/commits?path=anime-list-full.json&per_page=10"`（2026-10-28），commit message 全是 `automated list update`：

| 時間（UTC） |
| --- |
| 2026-10-20 16:04 |
| 2026-10-13 16:04 |
| 2026-10-06 16:04 |
| 2026-09-29 16:04 |
| 2026-09-23 05:27 |
| 2026-09-15 16:09 |
| 2026-09-08 16:09 |
| 2026-09-01 16:09 |
| 2026-08-25 16:09 |
| 2026-08-18 16:09 |

每週一次（週二 16:04–16:09 UTC，只有 9/23 偏離）。10-27 那週的更新到 2026-10-28 查證時尚未出現（最新仍是 10-20），所以「每週」不是保證準時；client 以「每週檢查一次、用 ETag 條件請求」即可。

### 1.4 下載網址

- 預設分支：`master`（`gh api repos/Fribb/anime-lists --jq .default_branch`）。
- `https://raw.githubusercontent.com/Fribb/anime-lists/master/anime-list-full.json`：`curl -I` 回 `HTTP/2 200`、`content-type: text/plain; charset=utf-8`、`cache-control: max-age=300`、有 `etag`。（raw 端點的 content-type 是 `text/plain`，client 要自己 `json.loads`，不能依賴 content-type。）
- 同目錄的 `anime-list-mini.json` 是同內容去縮排版，下載量較小。大小與筆數見前份研究 §2.4（7.5 MB、39,579 筆；mini 沒有實測）。

## 2. AniList

### 2.1 速率限制

來源：<https://docs.anilist.co/guide/rate-limiting>（2026-10-28 抓）。

> WARNING: The API is currently in a degraded state and is limited to **30 requests per minute**. This is a temporary measure until the API is fully restored.
> The AniList API has a rate limit of 90 requests per minute.
> When you make a request to the AniList API, you will recieve `X-RateLimit-Limit` and `X-RateLimit-Remaining` headers in the response.
> If you exceed the rate limit, you will recieve a 1 minute timeout. Any further requests in this timeout period will also include the `Retry-After` and `X-RateLimit-Reset` headers in the response.
> `Retry-After` is the number of seconds you should wait before making another request.
> `X-RateLimit-Reset` contains the Unix timestamp of when you can make another request.

429 範例（文件原文）：

```
HTTP/1.1 429 Too Many Requests
Retry-After: 30
X-RateLimit-Limit: 90
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1502035959
```

> Along with the `429` error code, you will recieve a GraphQL error message:

```json
{ "data": null, "errors": [ { "message": "Too Many Requests.", "status": 429 } ] }
```

Burst：

> On top of the above rate limiting, we also have a burst limiter. This limiter is designed to stop you from hammering the API with too many requests in a very short period of time.

（文件沒有給 burst 的數字。）

> WARNING: We are not currently accepting requests for increased rate limits.

注意：文件的 429 範例顯示 `Limit: 90`，但降級期間實際標頭是 30（前份研究 2026-10-27 實測 `X-RateLimit-Limit: 30`）。client 應讀標頭，不要寫死 90。

### 2.2 Terms of Use

來源：<https://docs.anilist.co/guide/terms-of-use>（2026-10-28 抓）。

> 1. Free for non-commercial usage. See our commercial usage section for more.
> 2. Using the AniList API as a backup or data storage service is strictly prohibited.
> 3. **Hoarding** or mass collection of data from the AniList API is strictly prohibited.
> 4. Applications or services must comply with our naming guidelines.
> 5. Use of the AniList API within competing, non-complementary services of the same nature is prohibited. This includes, but is not limited to, anime and manga list or tracker services. The restriction applies to all data provided through the API, including both user data and media data.

> Data collection for educational purposes: For purely educational projects, such as school assignments, we tend to be very lenient on the 3rd point.

Naming guidelines：

> If "**AniList**" or "**AniChart**" are used in the title/name of the application, you must clearly state that your app is unofficial by appending either "**UNOFFICIAL**" or "**for AniList**"/"**for AniChart**" to the title/name of the application.
> Just the titles/names "**AniList**" and "**AniChart**" are strictly prohibited

Commercial usage：

> The AniList API may be used within commercial applications or services operating at less than $150 of revenue per month free of charge, no express permission is required.

對 Berth 的意義：agent 按需查詢並做短期快取沒問題；不要排程預抓全站、不要把 AniList 當持久資料庫（本機快取要有 TTL 與上限）；Berth 名稱不含 AniList，不受命名條款約束；Berth 是下載協調器而非 anime list / tracker，不屬第 5 點。「快取多久算 storage / hoarding」文件沒有量化，這裡是判讀，不是文件原文。

### 2.3 User-Agent 與請求格式

- `Introduction`（<https://docs.anilist.co/guide/introduction>）與 `Getting Started`（<https://docs.anilist.co/guide/graphql/>）都沒有提到 User-Agent 要求；範例只送 `Content-Type: application/json`、`Accept: application/json`，POST 到 `https://graphql.anilist.co`，body `{query, variables}`。
- 結論：文件未要求 UA。仍建議送可識別的 UA（Berth 名稱 + 版本），因為這是良好的 API 公民習慣，但這是我們的決定，不是文件要求。

### 2.4 GraphQL 錯誤回報

來源：<https://docs.anilist.co/guide/graphql/errors>（2026-10-28 抓）。

> Errors are returned as part of the GraphQL response. You can find them in the `errors` field of the response object.
> Always check the `errors` field of the response object to see if there are any errors.
> Even if you recieve a status code of `200`, you may still receive an error.

範例（欄位錯誤）：

```json
{ "data": null, "errors": [ { "message": "Cannot query field \"nonexistentField\" on type \"MediaList\".", "status": 400, "locations": [ { "line": 4, "column": 5 } ] } ] }
```

- 每個 error 有 `message`、`status`（HTTP 風格數字）、`locations`；mutation 驗證錯誤多一個 `validation` 欄位。
- **文件沒有寫 `Media(id: <不存在>)` 的行為**。本檔只引用文件，不推測；前面「404 + errors」是慣例上的預期，要寫進 client 的處理邏輯前需實測一次（`Media(id: 999999999)`）。client 規則：不論 HTTP 狀態，先檢查 `errors` 再用 `data`；`status` 以 body 的 `errors[].status` 為準。

## 3. Bangumi

### 3.1 User-Agent

來源：<https://github.com/bangumi/api/blob/master/docs-raw/user%20agent.md>（raw 於 2026-10-28 抓），原文：

> 非浏览器的 API 使用者请指定一个带有**开发者个人 ID **和**应用名称**的 User Agent。
> 如果你的应用需要进行分发（如安卓客户端，或者某个语言的 SDK Library），请附上**版本号**。
> 如果你的应用是一个开源项目，请在 User Agent 附上项目主页。
> 各种请求库的默认 UA 可能会被禁用。
> 建议的 User Agent 比如：
> - `czy0729/Bangumi/6.4.0 (Android) (http://github.com/czy0729/Bangumi)`: 移动端 APP，请添加版本号。
> - `trim21/bangumi-episode-ics (https://github.com/Trim21/bangumi-episode-calendar)`：cloudflare workers，不进行分发，不需要添加版本号。
> - `sai/my-private-project`：某人的私有项目。
> **请不要使用类似于 `database`，`Bangumi/1.0`，`Bangumi/1.3.13.0` 的 User Agent。**

OpenAPI 的 `info.description` 也連到這份文件（`open-api/api.yml`）。對 Berth 的做法：`<owner>/berth/<version> (<repo url>)`，由程式常數組出，版本取套件版本。

### 3.2 `/calendar` 在 OpenAPI 中

- 規格檔：<https://github.com/bangumi/api/blob/master/open-api/api.yml>（OpenAPI 3.0.0，`servers: https://api.bgm.tv`；最後修改 2025-07-01）。注意 `open-api/v0.yaml` 是 `/v0/...` 新版端點，**不含 `/calendar`**；`/calendar` 屬於舊版 API，在 `api.yml`。（倉庫根目錄的 `api.yml` 路徑已不存在，是 `open-api/api.yml`。）
- 定義（`operationId: getCalendar`，summary「每日放送」，無參數、無需授權）：回應 200 是 array，每個元素 `{ weekday: {en, cn, ja, id}, items: [Legacy_SubjectSmall] }`，`weekday` 範例 `en: Mon`、`cn: 星期一`、`ja: 月耀日`、`id: 1`。
- `Legacy_SubjectSmall` 欄位（規格內文）：

  | 欄位 | 型別 | 說明（規格原文） |
  | --- | --- | --- |
  | `id` | integer | 条目 ID |
  | `url` | string | 条目地址 |
  | `type` | integer enum 1/2/3/4/6 | 条目类型：1 书籍、2 动画、3 音乐、4 游戏、6 三次元，「没有 5」 |
  | `name` | string | 条目名称 |
  | `name_cn` | string | 条目中文名称 |
  | `summary` | string | 剧情简介 |
  | `air_date` | string（`YYYY-MM-DD`） | 放送开始日期 |
  | `air_weekday` | integer | 放送星期 |
  | `images` | object | 封面：`large` / `common` / `medium` / `small` / `grid` |
  | `eps`、`eps_count` | integer | 话数 |
  | `rating` | object | `total`（总评分人数）、`count`（`"1"`..`"10"` 各分值人数）、`score`（number） |
  | `rank` | integer | 排名 |
  | `collection` | object | 收藏人数：`wish`、`collect`、`doing`、`on_hold`、`dropped` |

- 規格上所有欄位都沒標 `required`。2026-10-28 實測（`curl -A "berth-research/0 (...)" https://api.bgm.tv/calendar`）：200、`cache-control: max-age=3600`、7 個 weekday、112 個 item；其中只有 57 個有 `rank`、110 個有 `collection`、93 個 `rating` 帶 `score`。**所以 `rank`、`collection`、`rating.score` 必須當 optional 解析**；`url`、`images` 的 scheme 實測是 `http://`（`http://bgm.tv/subject/390200`、`http://lain.bgm.tv/...`），顯示前要升成 https 或保持原樣自行決定。
- 這份實測與前份研究（113 筆）差一筆，是放送表本身隔日變動，不是格式變化。

### 3.3 速率限制

- `docs-raw/` 只有 `How-to-Auth.md`、`Search-API.md`、`user agent.md`；`open-api/api.yml` 與 `v0.yaml` 內搜尋 `rate` 只命中分頁的 `limit` 參數，沒有速率限制說明；`README.md` 搜尋 `rate/limit/频率/限` 也無命中。
- 結論：**Bangumi 沒有公開文件化的速率限制**。`/calendar` 回應 `cache-control: max-age=3600`，client 照這個快取（至少 1 小時）就幾乎不會碰到問題。保守起見仍要自己限速並處理 429/5xx。

## 4. 還沒查證（留給實作）

- AniList `Media(id: <不存在>)` 的實際回應（文件沒寫）。
- AniList burst limiter 的數字（文件沒寫）。
- Fribb 作者是否願意補授權（需對他人倉庫開 issue，要使用者當次同意）。
- cedya77 延續版與 Fribb 現行資料的對應是否有差異（Fribb README 仍連到 cedya77，但 `anime-offline-database-reduced.json` 的內容來源未比對）。
