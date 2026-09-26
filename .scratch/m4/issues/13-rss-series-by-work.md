# 13 — RSS 頁以作品呈現 Series；完結的自動收起

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** brief §15、§19 2026-09-26「RSS Series 保留、以作品呈現」那一列；plan §2.4（`rss_series`、`rss_items`）、§6 rss 群組、§7；`.scratch/m3/rss-shape.md`；開工先 `/impeccable shape` RSS 頁的 Series 段與 Feed Item 段

## 為什麼（2026-09-26 使用者試跑）

- Series 那一列寫「自動綁定 · 入庫到 Anime · Mikan 3985 × 583」——後面是 Mikan 的番組 id × 字幕組 id，內部編號。
- 標題顯示的是**長出這個 Series 的那一筆 Item**（`rss_series.title_raw`），看起來像「最新的下載」，其實不是。
- 看不到這個 Series 下載了什麼；下方「最新的 Feed Item」看不出來自哪個 Feed、哪個 Series。
- 當季播完之後 Series 永遠留在清單上。
- Series 層有排除條件，使用者多半只想要 Feed 層的。

使用者拍板：**Series 保留**（它是「番組 × 字幕組 → 綁定、Route、季號與 offset、第一批」的記憶，拿掉就得每筆 Item 重認作品、
修正沒地方存；AutoBangumi 也是每個番組 × 字幕組一筆紀錄），**但以作品呈現、完結自動收起、Series 層排除收進進階**。

## 做什麼

1. Series 段以作品分組：作品名（Berth 的顯示語言）、字幕組名、來源（Mikan 的番組與字幕組**名稱**，連到 Mikan 的頁面）、
   Route、「已入庫 x / 下載中 y / 排除 z」、「最近 E12 · 3 天前」（最近一筆**發佈**的 Item，不是 `title_raw`）。
   第一批待確認照 m4/11 的一句話。
2. 每個 Series 展開看它所有的 Item：發佈名、集數、狀態（送出 / 排除 / 重複 / 等待）、對到的 Job。
3. 「最新的 Feed Item」每一列標出 Feed 與 Series（沒綁的寫待綁定）。
4. **已完結**：TMDB 標為完結而且對得到的集數都入庫了，或超過一段時間沒有新 Item（門檻寫進 plan §2.4，拆票時量試跑資料定），
   收進預設收起的「已完結」。紀錄不刪（去重與重新出現時的綁定都要它）；有新 Item 出現就回到清單。
5. Series 層的排除條件收進「進階」，Feed 層的放在明處。
6. Mikan 番組名與字幕組名的來源：已經抓過的番組頁（`_clues`）與 feed 本身帶的；沒有的就不顯示，不為了顯示多打 Mikan。

## 驗收

- [ ] 畫面上不再出現 Mikan 的數字 id（vitest 斷言 + playwright 文字結果）
- [ ] 「最近」是最近發佈的那一筆（整合測試：Item 發佈順序與長出順序不同時）
- [ ] 完結的規則寫成純函式、雙向測試；有新 Item 時回到清單（整合測試）
- [ ] Series 展開的 Item 清單、Feed Item 的來源欄（vitest + playwright，1280 與 390）
- [ ] brief §15、plan §2.4、§6 同步；`pnpm gen:api` 同一個 commit
- [ ] lint、type、test、前端 e2e 綠燈

## Comments
