# 112 — 作品頁 Mikan 可以「只下載現有的（一次性）」

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** brief §15「從 Media 頁訂閱」「一次性 RSS 連結」「全部接受，只排除」；plan §6 rss（`/rss/oneshot`、Mikan 番組與字幕組）；`berth/services/oneshot.py` 的 `read_oneshot`；`berth/api/rss.py` 的 `SubgroupOut`；`web/src/media/SubscribePanel.tsx` 的 `MikanPicker`；`web/src/rss/OneshotSection.tsx`

## 為什麼

使用者 2026-10-19：已完結、字幕組只出了合集的作品，從作品頁只能「訂閱」——建出一條單一 feed，那筆合集馬上被全域的「不自動下載合集」擋下，Feed 留著也不會再有新的。這種作品要的是「把現在有的下下來」，那正是 /rss 的一次性連結（不建 Feed、逐筆手動送單、排除條件不擋），只是在作品頁走不到、還要自己拼單一 feed 的網址。

## 做什麼

1. **先重構**：把 `OneshotSection` 的勾選清單（列、勾選全部單集、逐筆送出與結果）抽成可共用的元件，/rss 的一次性連結改用它，行為不變。
2. **後端**：`SubgroupOut` 帶這一組的單一 feed 網址（`feed_url`，由 `mikan.bangumi_feed_url` 產生）——網址格式只住在後端，前端不拼。
3. **前端**：`MikanPicker` 選好字幕組之後，「訂閱」旁邊多一個「只下載現有的」：就地展開共用的勾選清單，網址、作品、Route 都帶好（Route 照訂閱那裡選的）。逐筆走一般手動送單（`trigger = manual`），合集照樣勾得了，不建 Feed。
4. **訂閱的回報**：「訂閱」完成時，讀到的若有被排除的，回報說出幾筆、理由（例如「1 筆是合集，沒有自動下載」），並指向「只下載現有的」。
5. i18n zh-Hant、en 並列；文件：brief §15「從 Media 頁訂閱」補這一條路；plan §6；CHANGELOG；progress.md session 紀錄。

## 不做

- Nyaa、acg.rip 的搜尋 feed（那兩站走搜尋頁）。
- 訂閱前就預讀單一 feed 判斷「這組只有合集」（多一次請求；回報那一句已經接住）。

## 驗收

- [ ] /rss 一次性連結改用共用元件後行為不變（既有 vitest 全綠）
- [ ] `GET` 番組的字幕組帶 `feed_url`，與 `mikan.bangumi_feed_url` 一致（pytest）
- [ ] 作品頁選字幕組 → 「只下載現有的」→ 清單帶好作品與 Route，勾一筆合集送出成 `manual` Job，沒有長出 Feed（vitest）
- [ ] 訂閱後有被排除的時，回報說出筆數與理由；全部送出時不說（vitest，zh-Hant 與 en）
- [ ] playwright 實跑作品頁一次性下載一筆合集，附截圖（1280 與 390）
- [ ] 全部檢查、pytest、vitest 綠；brief、plan、CHANGELOG、progress.md 已更新

## Comments
