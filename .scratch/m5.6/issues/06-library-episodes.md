# 06 — `find_in_library` 給集數

**Status:** ready-for-agent

**Blocked by:** 01

**讀:** spec〈範圍〉C4；研究文檔 §4 C4；plan §6〈inventory〉、§8.2〈找作品與集：`items()`〉；brief §12

## 為什麼

Jellyfin 沒刮到 TMDB id 的作品，`media_read_media` 找不到，模型只知道「媒體庫裡有一部叫這個名字的」，不知道使用者有哪幾集，就沒辦法判斷缺什麼。

## 做什麼

1. 劇集的命中多一格 `episodes`：用 Jellyfin 的季號與集號，依季寫成範圍，不連續的地方斷開（例如 `S01E01–E05, S01E07–E12`）。電影沒有這一格。
2. 輸出或工具說明註明這是 Jellyfin 的編號，不是 TMDB 的。
3. 只替命中的劇集讀集數；請求數有上界（命中數有上限，fake client 計數）。走這個人看得到的媒體庫，門禁不變（brief §12）。
4. Jellyfin 讀集數失敗時，那一筆的 `episodes` 是空的並說明原因，整次呼叫不失敗。

## 驗收

- [ ] 劇集命中帶依季的範圍，中間缺一集時會斷開；電影沒有 `episodes`（測試）
- [ ] 請求數有上界（fake client 計數）；讀集數失敗不拖垮整次呼叫
- [ ] 工具說明寫明是 Jellyfin 的編號
- [ ] 全部檢查、pytest 綠；progress.md 已更新

## Comments
