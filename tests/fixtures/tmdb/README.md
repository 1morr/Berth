# TMDB 快照

解析語料（`../parser/`）指到的每一部作品的 `MediaSnapshot`（plan §4.3、§4.6）。
**錄一次即凍結**：benchmark 與單元測試離線跑，不打 `api.themoviedb.org`（plan §10）。

檔名是語料的 `tmdb` 欄位：`tv-209867.json`、`movie-872585.json`。

## 怎麼錄的

```bash
uv run --env-file .env python scripts/record_tmdb_snapshots.py           # 只補缺的
uv run --env-file .env python scripts/record_tmdb_snapshots.py --force   # 全部重錄
```

那支腳本跑的是**產品自己的路徑**：開一個暫時的資料庫、把憑證寫進去、呼叫
`services/media.refresh_media`，再把 `media.tmdb_snapshot_json` 原樣寫出去。手工組一份
JSON 只會證明它與想像一致；這樣錄下來的形狀與 Berth 執行時存進資料庫的那一份是同一個。

憑證讀環境變數 `TMDB_API_KEY`（`.env.example` 有說明）。**Berth 本身不讀它**——產品的唯一
來源是 `settings.services.tmdb.api_key`，由設定精靈第 6 步寫進資料庫（M1 票 02b）。

## 這一批

2026-09-10（M1 票 05），對真的 `api.themoviedb.org` 錄的 18 份，涵蓋 v0 語料的 20 筆
（`tv-94664` 與 `tv-93405` 各被兩筆語料共用）。

英文那一輪決定結構與所有會進檔名的字串，`zh-TW` 那一輪只補顯示用標題與簡介（plan §8.3）。
所以季名與集名是英文的——季名正是 plan §4.4「篇章名 → 季號」的來源，票 06 會用到。

快照會隨 TMDB 變（補完的集數、改過的標題）。重錄之後 `berth bench` 的數字若動了，那是
**真的**變了，要當成一次改動來看待，不是雜訊。
