# 06 — 媒體庫牆的排序與類型、年份篩選

**Status:** ready-for-agent

**Blocked by:** 03

**讀:** plan §11.2b；brief §13（媒體庫）、§20.8（排序與篩選）；`docs/research/library-browsing.md` §2（`/Items/Filters`
那一列）、§3、§7（劇集庫、電影庫、篩選面板）；票 01 的結論；`.scratch/m1.5/library-shape.md`

## 做什麼

媒體庫牆可以依 Jellyfin 的慣例排序，並依類型與年份篩選。沿用 jellyfin-web 的做法（研究 §7），不自己發明：

- 排序：劇集庫與電影庫的選項不同（劇集有「新集加入」`DateLastContentAdded`、「最近看過」`SeriesDatePlayed`），
  每個排序鍵後面接 `SortName`，可切升降冪。
- 類型與年份清單來自 `GET /Items/Filters?userId=&parentId=&includeItemTypes=`（三版形狀一致、含年份）；
  `genres` 以 `|` 分隔、`years` 以逗號。
- `/Items/Filters` 帶 `parentId` 時 Jellyfin **不套**媒體庫權限（研究 §2），所以只能在票 03 的閘門驗過媒體庫 id
  之後呼叫。
- `/Items` 會靜默忽略打錯的參數：每個參數都要有「伺服器真的有過濾」的測試，而不只是「請求送出去了」。

排序與篩選的狀態放在網址上，與票 03 保留的「待審」「Unmatched」篩選並存；兩者怎麼組合、還沒進 Jellyfin 的作品
在篩選下怎麼呈現，照票 03 的 shape。

## 驗收

- [ ] 劇集庫與電影庫各有自己的排序選項（對照研究 §7），可切升降冪
- [ ] 類型、年份篩選的清單來自 `/Items/Filters`，只列這個媒體庫有的；可多選
- [ ] 排序與篩選的狀態在網址上，重新整理與分享連結都還原得回來；與分頁一起正確運作
- [ ] 契約測試：`sortBy`、`sortOrder`、`genres`、`years` 各自證明伺服器真的有過濾或排序（票 01 的實測或錄製）
- [ ] 整合測試：對不在允許清單的媒體庫取篩選清單被拒且沒有轉發
- [ ] 篩選後沒有結果時說得出原因與怎麼清掉篩選
- [ ] playwright 實跑：劇集庫與電影庫各排序一次、篩選一次，附結果；鍵盤可完成；390px 與深淺兩主題
- [ ] lint / type / test 全綠並貼指令輸出
