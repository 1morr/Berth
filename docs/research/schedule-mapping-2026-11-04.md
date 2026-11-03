# 時間表的卡片對 AniList 與 Bangumi：用什麼對（2026-11-04）

M5.5 票 14。問題：時間表的卡片（TMDB）要顯示 AniList 的放送時刻與 Bangumi 的評分，對不上就不顯示、不猜。Berth 沒有 TMDB 對 AniList / Bangumi 的 id 對照表（Fribb 在 M5 票 23d 拿掉，brief §20.3），要選一種對應方式。腳本 `scripts/experiments/schedule_mapping.py`；原始回應與結果 JSON 在 `.local/experiments/`（不進版控）。

## 結論

- **原文名壓平後完全相同就算同一部**（TMDB `original_name` 對 AniList `title.native`、Bangumi `name`；NFKC、不分大小寫、只留字母與數字）。時刻另外要 AniList 那一筆的日本日期與 TMDB 播出日差一天以內；同名不只一部、或兩筆一樣近就不顯示。
- 不接 Wikidata：兩種都對到的 52 部（AniList 38、Bangumi 14）**0 件不一致**，Wikidata 只多對到 AniList 5 部、Bangumi 1 部，卻要多一個外部來源。
- 對不到的主要是續作（AniList / Bangumi 一季一條、名字帶「第2期」，TMDB 多季一條）與國產動畫（AniList、Bangumi 放送表大多沒有）。這是「對不上就不顯示」的代價，接受。

## 做法

那一週（2026-11-02 – 11-08）的卡片照票 09 的時間表算（discover `with_genres=16`、`ja|zh`、前後各寬一天，每部的上一集或下一集落在這一週），168 張（`ja` 93、`zh` 75）。兩種對應：

1. **Wikidata**：`tv/{id}` 帶 `append_to_response=external_ids` 拿 `wikidata_id`（同一個請求，不多打），再用 `wbgetentities` 讀 P8729（AniList anime ID）與 P5732（Bangumi subject ID）。對到的 id 還要在這一週的 AniList 放送裡、在 Bangumi 放送表上才算。
2. **原文名相同**：對這一週的 AniList `airingSchedules`（全部頁數）與 Bangumi `/calendar`。

## 數字（日本作品的卡片，93 張）

| 對應 | AniList | Bangumi |
| --- | --- | --- |
| Wikidata 有 id | 55（59.1%） | 29（31.2%） |
| 同上，且這週在放送裡 | 43（46.2%） | 15（16.1%） |
| 原文名相同 | 53（57.0%） | 48（51.6%） |
| 任一 | 58（62.4%） | 49（52.7%） |
| 兩種都對到 / 不一致 | 38 / 0 | 14 / 0 |

卡片有 `wikidata_id` 的 80/93（86.0%），但 Wikidata 上的 AniList / Bangumi id 多半是第一季那一條，續作的那一季不在這週的放送裡。國產（75 張）兩種都幾乎對不到（AniList 原文名 3 張、Bangumi 0）。

**日期**：原文名或 Wikidata 對到 AniList 的 61 張裡，57 張 AniList 那一集的日本日期與 TMDB 播出日同一天；其餘 4 張差 1、2、2、5 天（AniList 的下一集落在窗口裡，或 TMDB 的日期不同），所以時刻只收差一天以內的那一筆。

## 評分的季別守衛（同日補量）

TMDB 多季併成一部、`original_name` 是系列名；Bangumi 一季一條，第一季的條目常用系列名。只比原文名的話，第二季以後的卡可能掛上第一季的分數，所以評分另外要 Bangumi 條目的開播日（`/calendar` 的 `air_date`）與卡片那一季的開播日（`tv/{id}` 的 `seasons[].air_date`）對得上。

原文名對到唯一一筆 Bangumi 的 48 張（日本作品的卡片 93 張）：

| 容差 | 對得上 |
| --- | --- |
| ±0 天 | 36/93（38.7%） |
| ±1 天 | 48/93（51.6%） |
| ±3、7、14、30、60 天 | 48/93（51.6%） |

差距都是 0 天（36 張）或 −1 天（12 張，Bangumi 記早一天，深夜檔），所以容差取 **±1 天**。會顯示評分的（有分數也有人數）：**守衛前 46/93 = 49.5%，守衛後 46/93 = 49.5%**。

這一週守衛沒有擋掉任何一張：日本作品裡第二季以後的卡 17 張，原文名一張都沒對到 Bangumi（放送表上續作的條目名帶「第N期」之類的季號，舊季的條目不在表上）。守衛是防線，擋的是 Bangumi 續作沿用系列名、或放送表收了舊季條目的情況；任一邊沒有開播日就不顯示。

## 其他事實

- AniList 的 `airingSchedules(airingAt_greater, airingAt_lesser, sort: TIME)` 一頁 50 筆，`pageInfo.hasNextPage` 說還有沒有下一頁；一週（前後各寬一天）117 部、三頁。過去的放送也回（官方只保證未來的準確，brief §20.3）。
- 標準庫 `urllib` 預設的 User-Agent（`Python-urllib/…`）打 AniList 被 Cloudflare 擋（403，`error code: 1010`）；帶一個 User-Agent 就過。Berth 的 adapter 走 httpx。
- Bangumi `/calendar` 的名字是 HTML 跳脫過的（`Welsh &amp; Shedar`），比對前要還原。

## 限制

- 只量了一週。換季時重跑：季初 TMDB 與 AniList 的條目都可能還沒齊。
- 「不一致 0」只說兩種方式互相不矛盾，沒有逐筆人工核對。只有標題對到、Wikidata 沒對到的 37 張列在腳本輸出最後一段，粗看沒有明顯誤配，沒有逐筆查證。

## 來源

- AniList [AiringSchedule](https://docs.anilist.co/reference/object/airingschedule)、`POST https://graphql.anilist.co`（2026-11-04 實測）。
- Bangumi `GET https://api.bgm.tv/calendar`（[bangumi/api](https://github.com/bangumi/api)）。
- TMDB [TV Series External IDs](https://developer.themoviedb.org/reference/tv-series-external-ids)（`append_to_response`）；Wikidata [wbgetentities](https://www.wikidata.org/w/api.php?action=help&modules=wbgetentities)，屬性 [P8729](https://www.wikidata.org/wiki/Property:P8729)、[P5732](https://www.wikidata.org/wiki/Property:P5732)。
