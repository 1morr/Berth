# 11 — Nyaa 與 acg.rip adapter + 新 Feed 第一輪預覽

**Status:** ready-for-agent

**Blocked by:** 10（預覽要畫得出排除與重複）

**讀:** plan §2.4（`primed_at`、`rss_series.key`）、§8.5、§11.4；brief §15（「Feed」「RSS Series」「補舊集」最後一句）；`docs/research/rss-sources.md`

## 做什麼

**兩個 adapter**：照票 07 的 fixture，Nyaa（搜尋 feed、使用者 feed）與 acg.rip（搜尋 feed）各一個 mapper，輸出同一種 Feed Item。

**非 Mikan 的 RSS Series 鍵**：標題骨幹 + 字幕組（AutoBangumi 的做法，brief §15）。骨幹 = 去掉字幕組、集號、tags 之後的標題；正規化規則沿用解析器現有的，不另寫一份。同一部作品的兩個字幕組是兩個 RSS Series。自動綁定走票 09 的同一條路；這些來源沒有番組頁，所以候選只從標題來。

**新 Feed 的第一輪預覽**（brief §15）：搜尋類 feed 第一輪就帶著歷史，所以第一輪不直接下載，而是列成預覽，使用者選「全部下載」或「只追之後的」。選完之後寫 `primed_at`。預覽裡要看得到排除與重複（票 10）。Mikan 聚合 feed 沒有這個問題（只有最近的集數），是否也要預覽在 shape 時決定並寫進 plan。

## 驗收

- [ ] 兩個 adapter 各有契約測試（fixture → Feed Item 欄位）
- [ ] 標題骨幹：同一部作品不同集數得到同一個鍵、不同字幕組得到不同鍵（單元測試，含 fixture 裡的真實標題）
- [ ] 新增搜尋 feed → 第一輪不送單、出現預覽 → 「只追之後的」之後舊的不送、新的送；「全部下載」之後全送（整合測試，雙向）
- [ ] acg.rip 搜尋 feed 裡的合集在預覽裡顯示為被排除（對應 M3 驗收「合集被排除」）
- [ ] playwright 實跑預覽，1280 與 390，附結果
- [ ] lint、type、test 綠燈
