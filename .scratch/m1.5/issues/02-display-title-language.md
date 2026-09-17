# 02 — 顯示用標題與簡介跟著 UI 語言

**Status:** done

**Blocked by:** 無 —— 可立即開工

**讀:** brief §7.5、§19（「顯示用標題的語言」那一列）；plan §8.3（TMDB 的三輪與快取）、§11.2b；`PRODUCT.md`
（英文是一等公民）

## 做什麼

M1 為止畫面一律顯示 TMDB `zh-TW` 那一輪的標題與簡介，EN 介面上海報牆、詳情頁 h1 與簡介全是中文（票 15
的 critique）。2026-09-17 決定改成跟著 UI 語言走：`zh-Hant` 顯示 `zh-TW` 那一輪，`en` 顯示 `en-US` 那一輪。

現況的三個缺口：後端不知道使用者的 UI 語言（語言只存在前端）；`en-US` 那一輪的簡介沒有存下來；下載列
一律顯示英文標題，不論介面語言。

範圍是**作品的標題與簡介**。檔名、資料夾名與季名比對用的字串不跟 UI 走（brief §7.5）；集名仍只抓
`en-US`（plan §8.3，集名會進檔名），不在本票。媒體庫牆上已在 Jellyfin 裡的作品顯示 Jellyfin 的名稱，
那是票 03 的事；本票只管 TMDB 來的標題。

## 驗收

- [x] EN 介面：探索牆、搜尋結果牆、Media 詳情（h1 與簡介）、下載列、現有媒體庫牆的卡片顯示 `en-US` 那一輪的
      標題與簡介；zh-Hant 介面維持 `zh-TW` 那一輪
- [x] 某一輪缺翻譯時的後備有測試釘住（沿用現有的後備規則，不另發明）
- [x] 在頁面上切換語言，標題與簡介跟著換，不必重新整理
- [x] 既有的快取與快照（`tmdb_cache`、Media 快照）在格式改變之後不會讓畫面壞掉或顯示空標題（有測試）
- [x] 檔名與資料夾名不受影響：命名與凍結資料夾名的既有測試不改期望值照樣綠
- [x] playwright 實跑：EN 與 zh-Hant 各看探索牆、一部劇集與一部電影的 Media 詳情、下載列，附文字結果
- [x] lint / type / test 全綠並貼指令輸出

## Comments

- code-review（Standards）記下沒改的：`JobOut.media_title` 改了語意但沒改名（與 `title` / `title_en` 同一個慣例，
  CHANGELOG 已記）；`MediaTile` 與 `InventoryTile` 挑標題的寫法一樣、`services/jobs` 的 `media.snapshot().title`
  與 `services/inventory` 的 `snapshot.title or media.title_en` 寫法不同但結果相同——媒體庫牆由票 03 換掉，到時再
  看要不要收；`title` / `title_en` 成對欄位出現在九個型別裡（`title_en` 同時是檔名用的標題，包成一個「語言文字」
  型別不乾淨）；`FakeTmdbClient` 的 `translations` 與 `overview_translations` 總是一起出現。
- 媒體庫牆（票 13 那一面）的排序仍照 `zh-TW` 標題，EN 介面上看起來不是字母序；牆的排序在票 03 改由 Jellyfin 提供。
- **海報仍取 `zh-TW` 那一輪**：TMDB 的海報分語言，playwright 實跑時 Moana 在 EN 介面是「海洋奇緣」的中文海報。
  票面範圍只有標題與簡介，沒改；要不要開票由使用者決定（progress.md 的發現）。
- `services/media._fetch` 的 `display.title or base.title` 在正式環境走不到：adapter 已把空標題換成原文，而 TMDB
  未翻譯時回英文（brief §20.3）。它是既有的防禦，沒有測試守、也沒刪。
