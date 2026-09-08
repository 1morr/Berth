# 03 — TMDB 快照與探索頁

**Status:** ready-for-agent

**Blocked by:** 01（`media` 的欄位由它決定）、02（型別產生器先接上）

**讀:** plan §2.2、§6（discover 群組）、§7、§8.3、§11.2（T1.1）；brief §13（探索）

## 做什麼

打開 `/` 看得到趨勢與熱門作品、能搜尋、卡片顯示追蹤狀態。`/` 不再導向 `/health`。

帶進來的東西：`media` 與 `tmdb_cache` 表與 migration（欄位依 plan §2.2，若票 01 決定採用 TVDB
則含 `tvdb_id` / `episode_source`）；TMDB adapter 補 `trending/{tv,movie}/week`、`{tv,movie}/popular`、
`search/multi` 與 `configuration` 的圖片基底；`services/` 的探索命令、快取與速率限制。

探索頁是 M1 的第一個新頁面，走 `/impeccable shape` 再實作。

## 驗收

- [ ] `media` 與 `tmdb_cache` 表與 migration 完成，空資料庫升得上去也降得回來
- [ ] `GET /api/discover/trending`、`/discover/popular`、`/discover/search?q=` 回作品清單
      （tmdb id、kind、標題、年份、海報路徑）
- [ ] 探索頁顯示趨勢與熱門、搜尋框可搜；卡片顯示追蹤狀態（M1 只有未追蹤 / 已追蹤）
- [ ] 探索與搜尋的 TMDB 快取 1 小時生效：同一查詢第二次不打外部（有測試）
- [ ] 全域 40 req/s 令牌桶存在且有測試
- [ ] 顯示用標題另以 `zh-TW` 取一次（brief §7.5 的檔名仍用英文，本票不碰檔名）
- [ ] TMDB 憑證缺失或 TMDB 不可達時，探索頁顯示可行動的錯誤而不是空白畫面
- [ ] `/` 不再導向 `/health`；未登入仍導向 `/login`
- [ ] 探索頁走 `/impeccable shape`；playwright 實跑並附結果
- [ ] 深淺兩主題所有文字對比 ≥ 4.5:1；390px 窄版沒有頁面層級的橫向捲動
- [ ] zh-Hant 與 en 並列，沒有硬編字串
- [ ] lint / type / test 全綠並貼指令輸出
