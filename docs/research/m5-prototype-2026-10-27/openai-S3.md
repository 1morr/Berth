# openai · S3 冷門作品：宝石の国

對話 `94fcb4419ca3`。要看：標題對不對得上；搜不到時怎麼辦；有沒有重複搜同一個詞


## 👤 我想看《宝石の国》（Land of the Lustrous），幫我找來源下載。

我來找《寶石之國》的來源。

- 🔧 `berth_discover_search({"query": "宝石の国 Land of the Lustrous"})` → {"items": [{"id": "tv:74091", "kind": "tv", "title": "寶石之國", "title_en": "Land of the Lustrous", "year": 2017, "tracked": false}], "problem": null, "detail": ""}
- 🔧 `anilist_search({"query": "宝石の国"})` → {"Page": {"media": [{"id": 98707, "idMal": 35557, "type": "ANIME", "format": "TV", "status": "FINISHED", "episodes": 12, "season": "FALL", "seasonYear": 2017, "startDate": {"year": 2017, "month": 10, "day": 7}, "title":
- 🔧 `fribb_lookup({"anilist_ids": [98707]})` → {"98707": {"type": "TV", "themoviedb_id": {"tv": 74091}, "season": {"tvdb": 1, "tmdb": 1}, "episode_offset": null, "tvdb_id": 331787}}
- 🔧 `berth_routes({})` → [{"route_id": 1, "name": "Movies", "collection_type": "movies", "enabled": true}, {"route_id": 2, "name": "TV", "collection_type": "tvshows", "enabled": true}, {"route_id": 3, "name": "Anime", "collection_type": "tvshows
- 🔧 `berth_media({"media_id": "tv:74091"})` → {"id": "tv:74091", "kind": "tv", "title": "寶石之國", "title_en": "Land of the Lustrous", "title_original": "宝石の国", "year": 2017, "tracked": false, "default_route_id": null, "awaiting_review": 0, "seasons": [{"season_number"
- 🔧 `berth_search_torrents({"media_id": "tv:74091", "season": 1})` → {"returned": 226, "problem": null, "detail": "", "rows": [{"source_id": "gSVGTxIz9yCNVgVc-UP0-Q", "title": "[Arid] Land of the Lustrous [Dual-Audio][BDRip 1080p Hi10 FLAC]", "indexer": "Anime Tosho", "size_gb": 29.7, "se
- 🔧 `berth_mikan_search({"query": "宝石の国"})` → []
- 🔧 `berth_mikan_search({"query": "Houseki no Kuni"})` → [{"id": 1421, "title": "宝石之国"}]
- 🔧 `berth_mikan_search({"query": "寶石之國"})` → [{"id": 1421, "title": "宝石之国"}]
- 🔧 `berth_mikan_bangumi({"bangumi_id": 1421})` → {"id": 1421, "title": "宝石之国", "subgroups": [{"id": 202, "name": "生肉/不明字幕", "updated": "2018-06-08", "releases": 1, "latest": "[Moozzi2] 宝石之国 Houseki no Kuni (BD 1920x1080 x264 Flac)", "bound_to": null, "feed_url": "https
- 🔧 `berth_search_torrents({"media_id": "tv:74091", "keyword": "宝石之国 简体 繁体 合集"})` → {"returned": 100, "problem": null, "detail": "", "rows": [{"source_id": "CBoP2ZgFlkVlJRQYpM56yg", "title": "BurnAware Professional 12.1 FULL [TechTools]", "indexer": "The Pirate Bay", "size_gb": 0.01, "seeders": 31732, "
《寶石之國》在 Berth 的對應：**tv:74091**，只有 TMDB S1（12 集，已播 12、入庫 0）。AniList 98707 → TMDB 對照正常，沒有季號偏移問題。

## 索引站找到的來源（Anime Tosho，都是 BD）
| 版本 | 大小 | 做種 | 備註 |
|---|---|---|---|
| [Arid] Dual-Audio BDRip 1080p Hi10 FLAC | 29.7 GB | 75 | 畫質最好、種子最多，日英雙語 |
| [Breeze] 1080p BD AV1 dual audio | 17.1 GB | 18 | AV1，體積折衷 |
| [Sokudo] 1080p BD AV1 dual audio | 3.7 GB | 12 | 小體積 AV1 |
| [Prof] 1080p x265 10bit BluRay dual audio | 8.2 GB | 6 | x265 相容性好 |

⚠️ 注意兩點：
- 這些都是**日英雙語、無中文字幕**。另外有一個 `HiDive-DL Eng Dub` 是純英語配音，不建議。
- 用中文關鍵字（宝石之国／合集）搜索引站沒有結果，索引站只有英文標題的 BD 版。

## 想要中文字幕的話
Mikan 上有（已完結 2017 番，只有整包/舊種，沒有持續更新）：
- 喵萌奶茶屋 — 簡體 01–12 合集 720P
- DHR 動研字幕組 — 繁體 全 12 話 720P
- 極影字幕社 — 只有第 1 話（BIG5）

這部是完結番，訂閱 Mikan 番組（RSS）不一定會回頭抓舊集，比較保險的是把該字幕組的 RSS 貼給我加 Feed，或你直接找種子。

## 建議
先用 **[Arid] 29.7 GB（75 種）** 送單到 Anime route，一次拿齊 12 集，字幕另外外掛。

要我現在開確認卡嗎？還是你想改 3.7 GB 的 Sokudo 小體積版、或先處理中文字幕來源？


## 數字

```json
{
 "provider": "openai",
 "scenario": "S3",
 "conv": "94fcb4419ca3",
 "seconds": 40,
 "runs": 1,
 "requests": 9,
 "tool_calls": 11,
 "input": 46089,
 "output": 2150,
 "cache_read": 41216,
 "web_searches": 0,
 "cost_usd": 0.00429,
 "stops": [
  "end_turn"
 ],
 "errors": [],
 "outcomes": {
  "ok": 11
 },
 "tool_names": [
  "berth_discover_search",
  "anilist_search",
  "fribb_lookup",
  "berth_routes",
  "berth_media",
  "berth_search_torrents",
  "berth_mikan_search",
  "berth_mikan_search",
  "berth_mikan_search",
  "berth_mikan_bangumi",
  "berth_search_torrents"
 ],
 "proposals": [],
 "cache_hit": 0.894
}
```
