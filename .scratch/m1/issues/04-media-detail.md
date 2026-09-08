# 04 — Media 詳情與追蹤

**Status:** ready-for-agent

**Blocked by:** 03

**讀:** plan §2.2、§5（`folder_name` 與 `title`）、§6（media 群組）、§8.3；brief §7.5、§13（Media 詳情）

## 做什麼

點探索頁的卡片進 Media 詳情：看得到 TMDB 資訊與各季各集；按「追蹤」把 Media 存進 `media` 表並
**凍結 `folder_name`**；可指定預設 Route。

`folder_name` 一旦寫進去就只從那裡讀（plan §5）——之後 TMDB 改了標題也不會讓已入庫的資料夾對不上。

Media 詳情頁是決策中心，M1 會分三次長出來：本票做 TMDB 資訊與季集、票 08 加搜尋結果表、
票 13 加檔案與版本清單。本票先 `/impeccable shape` 把整頁的版面定下來，後兩票往裡面填。

## 驗收

- [ ] `GET /api/media/{id}` 回 TMDB 詳情與季集快照（各季各集的 number / name / air_date / runtime；
      episode groups 的 absolute 排序若存在）
- [ ] `POST /api/media/{id}/track` 建立 Media 並依 plan §5 模板與 brief §7.5 的標題語言凍結 `folder_name`
- [ ] `POST /api/media/{id}/refresh` 重抓快照且**不改** `folder_name`（有測試釘住）
- [ ] 快照超過 24 小時自動刷新
- [ ] 詳情頁顯示各季各集清單與追蹤狀態，可選預設 Route（只列 `collection_type` 相符的 Route）
- [ ] 電影與劇集兩種 kind 都走得通，電影沒有季集區塊
- [ ] 追蹤過的作品回到探索頁時卡片狀態是「已追蹤」
- [ ] Media 詳情頁走 `/impeccable shape`（版面要留給票 08 的搜尋結果表與票 13 的檔案清單）
- [ ] playwright 實跑；深淺兩主題文字對比 ≥ 4.5:1；390px 窄版可用
- [ ] zh-Hant 與 en 並列；lint / type / test 全綠並貼指令輸出
