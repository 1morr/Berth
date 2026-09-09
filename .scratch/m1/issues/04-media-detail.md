# 04 — Media 詳情與追蹤

**Status:** done

**Blocked by:** 03

**讀:** plan §2.2、§5（`folder_name` 與 `title`）、§6（media 群組）、§8.3；brief §7.5、§13（Media 詳情）

## 做什麼

點探索頁的卡片進 Media 詳情：看得到 TMDB 資訊與各季各集；按「追蹤」把 Media 存進 `media` 表並
**凍結 `folder_name`**；可指定預設 Route。

`folder_name` 一旦寫進去就只從那裡讀（plan §5）——之後 TMDB 改了標題也不會讓已入庫的資料夾對不上。

Media 詳情頁是決策中心，M1 會分三次長出來：本票做 TMDB 資訊與季集、票 08 加搜尋結果表、
票 13 加檔案與版本清單。本票先 `/impeccable shape` 把整頁的版面定下來，後兩票往裡面填。

## 驗收

- [x] `GET /api/media/{id}` 回 TMDB 詳情與季集快照（各季各集的 number / name / air_date / runtime；
      episode groups 的 absolute 排序若存在）
- [x] `POST /api/media/{id}/track` 建立 Media 並依 plan §5 模板與 brief §7.5 的標題語言凍結 `folder_name`
- [x] `POST /api/media/{id}/refresh` 重抓快照且**不改** `folder_name`（有測試釘住）
- [x] 快照超過 24 小時自動刷新
- [x] 詳情頁顯示各季各集清單與追蹤狀態，可選預設 Route（只列 `collection_type` 相符的 Route）
- [x] 電影與劇集兩種 kind 都走得通，電影沒有季集區塊
- [x] 追蹤過的作品回到探索頁時卡片狀態是「已追蹤」
- [x] Media 詳情頁走 `/impeccable shape`（版面要留給票 08 的搜尋結果表與票 13 的檔案清單）
- [x] playwright 實跑；深淺兩主題文字對比 ≥ 4.5:1；390px 窄版可用
- [x] zh-Hant 與 en 並列；lint / type / test 全綠並貼指令輸出

## Comments

- **`tracked` 是欄位而不是「有沒有這一列」。** 點進詳情頁就會寫下一列（快照要有地方放），
  `tracked` 才是追蹤與否。連帶決定了 `folder_name` 的規則：**還沒追蹤時它跟著 TMDB 的標題走**
  （畫面上是「將會是」的預覽），追蹤那一刻凍結，之後 refresh 一律不動它。兩個方向各有一條測試。
- **季集只取英文那一輪。** 集名會進檔名（plan §5 的 `{episode_title}`），中文集名放進去等於讓
  磁碟上的檔名跟著 UI 的語言跑。所以詳情打兩輪（`en-US` 結構 + `zh-TW` 顯示用標題與簡介），
  季集只打 `en-US`：一部四季的作品是 2 + 4 + 1 = 7 個請求，24 小時一次。
- **絕對編號只是快照上的一欄，不是判定依據。** brief §20.3 已量過它不可靠（十部只有六部有、
  有的部有好幾個互相衝突）。這一票把它顯示出來，怎麼用是票 06 解析器的事。
- **這一票沒有「取消追蹤」。** plan §6 的 media 群組只有三支端點，而刪除範圍是 brief §9.2（M2）。
- **`GET /media/{id}` 順手回相符的 Route 清單。** 「只列 `collection_type` 相符的」是領域規則
  （`domain.collection_type_for`），放前端會變成第二份；也省掉一次 `GET /routes`。
- **季表在 1213 集的作品上沒有分頁。** 預設全收，展開是使用者自己要的（使用者拍板）。
  真的痛的時候再說——plan 沒要求虛擬捲動。
- **票 08 與票 13 往這一頁的中間插。** 區塊序列與「整寬堆疊」的理由寫在
  `.scratch/m1/media-detail-shape.md` §3，那份是三張票共用的版面契約。
- **`_missing()` 為認不得的 id 捏了 `tmdb_id=0` / `kind=tv`**（code review 的判斷題）。`/media/nonsense`
  的回應在那兩欄上說了謊，只是畫面在那條分支裡不讀它們。沒有改成 nullable 是因為那會讓每一個
  正常回應的消費者都要處理 `null`，代價落在常態路徑上。留給真的有 API 消費者（MCP）時再定。
- **每季一個請求是序列的**：一部四季的作品在一次 `GET` 裡打 7 支 TMDB。令牌桶本來就會排隊，
  而快照 24 小時才重抓一次，所以沒有併發化。真的痛的時候再說。
- **`image_base()` 自己讀一次設定**，所以 `_feed` 那一輪會多讀一次 `settings`。一個 SELECT，
  換掉的是「把設定沿著三層函式傳下去」的管線，接受。
