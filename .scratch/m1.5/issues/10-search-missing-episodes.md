# 10 — 缺集一鍵搜

**Status:** ready-for-agent

**Blocked by:** 08

**讀:** plan §6（search 群組）、§8.4（索引站 adapter 與查詢名）、§11.2b（M1 帶過來的 critique 那一段）；brief §6.9
（benchmark）；`.scratch/m1/search-results-shape.md`；`.scratch/m1.5/media-detail-shape.md`

## 做什麼

季表已經知道缺哪幾集，搜尋卻仍從作品名開始（plan §11.2b）。從季表的缺集直接開始搜尋：

- **查詢由後端產生**，前端不重算——`GET /search/queries` 先給看會拿哪幾個名字去問，這條規則只能有一份實作
  （plan §6）。缺整季、缺幾集、缺一集時要問什麼（季包、單集、動漫的絕對編號），用測試先寫出來再實作。
- 結果表照舊：送單、預估季集、Tags 都不變。

按鈕放在哪、一次搜一季還是勾選幾集，照票 08 的 shape。

## 驗收

- [ ] 季表上有缺集時可以直接開始搜尋；沒有缺集時不出現這個入口
- [ ] 查詢由後端依缺的季集產生，`/search/queries` 的預覽照實顯示；單元測試涵蓋整季、數集、單集與有絕對編號的作品
- [ ] 搜尋結果照舊可以送單（playwright 走一次：缺集 → 搜尋 → 送單確認）
- [ ] 改到解析器時跑 `berth bench`，`auto_wrong` 不升並貼輸出
- [ ] plan §6 的 search 群組同步改
- [ ] 390px 與深淺兩主題；鍵盤可完成；zh-Hant 與 en 並列
- [ ] lint / type / test 全綠並貼指令輸出
