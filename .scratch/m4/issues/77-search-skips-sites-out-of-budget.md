# 77 — 一個站的請求預算用完時，搜尋照樣問其他站

**Status:** ready-for-agent

**Blocked by:** 76（同一批對外請求與錯誤訊息的程式，先讓 76 改完 log）

**讀:** `berth/adapters/budget.py` 開頭的說明；M3 票 20、plan §3.2、§8.4；`docs/research/request-budget.md`；`berth/services/search.py` 的預算段；前端搜尋卡片的「等請求預算」說明與 i18n

## 為什麼（2026-10-09 使用者本機實測）

- 使用者訂閱 Mikan 的 MyBangumi，Berth 在一小時內對 mikanani.me 發了 87 個請求：`.torrent` 32、單集頁 21、作品頁 17、各作品 RSS 15、MyBangumi 2。Mikan 那一小時的 60 格就用完了。
- 之後搜《Law & Order》，跟 Mikan 無關的影集：
  - 因為 Prowlarr 底下也有 Mikan，現行規則是「有一站放不下就一個都不問」，Nyaa 等還有額度的站也沒被問；
  - 畫面只說等 43 分鐘。
- 畫面最後一行是後端的英文原始訊息 `request budget for mikanani.me is used up; it fits again at 2026-10-09T01:13:14.847316+00:00`：沒走 i18n，時間是 UTC 的 ISO 字串。

## 做什麼

1. **搜尋改成跳過放不下的站**：
   - 有額度的站照常問、照常佔格；放不下的站這次不問，結果裡列出「哪幾個站這次沒問、何時放得下」。
   - 所有站都放不下時，才維持現在的「整批等待」畫面。
   - 改變的是 plan §8.4 / 票 20 的規則：同一 commit 改 plan 與 brief，progress.md「偏差與決定」記一行。
   - 先查 Prowlarr 的搜尋 API 能不能只問指定的 indexer（context7 或 OpenAPI，查到補進 brief §20）。不能指定的話，寫出替代做法再實作，理由寫在 Comments。
2. **畫面**：
   - 「這次沒問的站」與「全部都等」兩種狀態都走 i18n key，zh-Hant 與 en 並列；
   - 時間用使用者時區與既有的相對時間格式，例如「43 分鐘後」；
   - 不再顯示後端原始英文訊息。
3. **查一件事、記下來，不在這張改**：MyBangumi 一次訂閱就吃掉 87 格，其中 `.torrent` 下載與單集頁有沒有算進預算、該不該算。結論寫在 Comments；需要改就另開票。
4. 測試：
   - 整合測試（雙向）：Mikan 額度用完、Nyaa 有額度時，搜尋有問 Nyaa、結果標出 Mikan 沒問；全部用完時維持等待；
   - vitest：兩種狀態的文案（兩種語言）與時間格式；不顯示原始訊息。
5. 實跑：隔離環境（專案名 `berth-t77`、另一組 port），把 Mikan 的預算用完再搜一部非動畫影集，附截圖。**不准碰使用者的 `berth-local`。**

## 驗收

- [ ] 放不下的站被跳過、其他站照問；全部放不下才整批等待；雙向整合測試
- [ ] 畫面兩種狀態走 i18n、當地時區、相對時間；不再出現後端原始訊息；vitest
- [ ] Prowlarr 能否指定 indexer 的查證補進 brief §20；plan 與 brief 的規則同步，progress.md 偏差已記
- [ ] MyBangumi 的請求量與預算計法結論寫在 Comments（需要就另開票）
- [ ] 隔離環境實跑截圖；全部檢查、pytest、vitest、前端 e2e 綠
