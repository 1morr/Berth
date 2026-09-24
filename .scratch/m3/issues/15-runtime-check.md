# 15 — 片長驗證

**Status:** ready-for-agent

**Blocked by:** None — can start immediately（mediainfo 與 TMDB 片長都已經有了）

**讀:** plan §3.1（`planning` → `review`）、§4.2、§8.7、§11.4（「入庫前後的三道程式檢查」②）；brief §6.2（「分類器要能被 mediainfo 修正」）、§6.10、§14

## 做什麼

三道程式檢查的第二道：mediainfo 量到的片長與 TMDB 那一集的片長差太多時，不自動入庫。

- **抓什麼**：分類錯誤，像預告、NCOP、SP / OVA、兩集合併檔被當成一集正片。**抓不到**同一季裡算錯的集號（那是票 14 的事）。
- **門檻**：比例與絕對秒數怎麼定，先用 benchmark 語料裡有 mediainfo 的樣本量一次再寫死，量測結果記在本票 Comments。
- **TMDB 沒有那一集片長時跳過**。mediainfo 失敗時照 §8.7「失敗不阻擋」，也跳過。
- 可疑的送審核，理由是新的 `ReviewReason`，說得出兩個片長。
- 手動送單與 RSS 走同一條檢查。

同票 14，檢查是純函式，M5 的 AI 結果也要過它。

## 驗收

- [ ] 純函式單元測試：差太多、剛好在門檻內外、TMDB 沒片長、mediainfo 失敗
- [ ] 一個 90 秒的 NCOP 被解析成正片 → 送審核、理由說得出兩個片長（整合測試）；片長對得上的照常入庫（雙向）
- [ ] `berth bench` 跑一輪，`auto_wrong` 不升（review 比例的變化記在 Comments）
- [ ] 新理由的 zh-Hant 與 en 文案；plan §3.1 同步
- [ ] lint、type、test 綠燈
