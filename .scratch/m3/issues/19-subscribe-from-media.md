# 19 — 從 Media 頁訂閱

**Status:** ready-for-agent

**Blocked by:** 11（三種來源）、12（Mikan 綁定時補舊集）

**讀:** plan §7（Media 詳情）、§11.4；brief §13（Media 詳情的「RSS 訂閱」）、§15（「從 Media 頁訂閱」）

## 做什麼

次要入口（brief §15）：在 Media 詳情頁選一個來源，建一條單一 feed，並**預先綁定這部作品**。

- **Mikan**：選番組與字幕組 → 建 `/RSS/Bangumi?bangumiId=&subgroupid=` 的 Feed → 長出的 RSS Series 直接綁到這部作品與所選的 Route → 照票 12 補舊集（預設勾選）。番組怎麼找（Mikan 搜尋頁或使用者貼網址）在 shape 時決定，要先查 Mikan 有沒有可用的搜尋入口，查到的補進 brief §20。
- **Nyaa / acg.rip**：以這部作品的標題（與 `services/search.py` 同一份標題集合）組搜尋 feed 網址 → 建 Feed → 走票 11 的第一輪預覽。
- 已經有 RSS Series 綁在這部作品上時，詳情頁顯示它們（來源、字幕組、是否確認、最近一集），可以連到 `/rss`。
- 綁定走票 08 的同一個命令，凍結 `folder_name` 的規則相同。

## 驗收

- [ ] 從詳情頁訂閱一部 Mikan 作品 → Feed、RSS Series 已綁定、舊集已送單（整合測試）
- [ ] 從詳情頁建 Nyaa 或 acg.rip 搜尋 feed → 出現第一輪預覽
- [ ] 詳情頁列出已綁在這部作品上的 RSS Series
- [ ] 只有 admin 看得到訂閱入口
- [ ] playwright 實跑，1280 與 390，附結果
- [ ] lint、type、test 綠燈
