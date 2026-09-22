# 01 — 開工收尾（後端）

**Status:** ready-for-agent

**Blocked by:** 無 —— 可立即開工

**讀:** plan §3.2（`qbit_poller` 那一列與底下關於它的三條）、§6（jobs 群組）、§11.3（票 01 那一列）；brief §20.2

## 做什麼

M2 開工前把五件有 repro、不需要新載體的後端債清掉。它們互相獨立，順序隨意。

1. **兩個會 500 的路徑**。
   - 同一個新使用者**兩次登入同時進來**撞 `users.jellyfin_user_id` 的 unique：`services/auth.py`
     的 `_mirror_user` 沒接 `IntegrityError`。兩條都該拿到同一個鏡像使用者。
   - `check_routes` **跑到一半 Route 被刪**：`api/setup.py` 只接 `ValueError`，SQLAlchemy 的
     `StaleDataError` 裸奔成 500。它該是 plan §6 已經定好的 404 `route_missing`（票 14、14a
     對 `routes/*` 定的同一種拒絕）。
2. **`Season 3 / … Season 3 - 46` 被讀成 `S03E03–E46`**。`berth/parser/release.py` 的
   `_LOOSE_RANGE`（行 67、用在行 217）把 `Season 3 - 46` 這種「季號 - 集號」當成集數範圍。
   走 tdd：先把這一類加進自己的語料 fixture（紅燈），再改規則。改完跑一輪 `berth bench`，
   `auto_wrong` 不得上升（專案 CLAUDE.md 的架構規則）。
3. **`list_jobs` 逐列查詢改批次**。`services/jobs.py:394`，每一筆 job 各查一次關聯，清單長了
   就是 N+1。
4. **`QbitPoller` 補整合測試**。五個背景迴圈裡唯一沒有的，而它扛著 §3.2 那三條實跑換來的規則：
   醒得比問頻繁且間隔每次醒來重算、HTTP client 握著不放（`rid` 增量掛在那條連線上）、推播在
   commit 之後。
5. **兩個沒人引用的 fixture**：`tests/fixtures/http/jellyfin/useritems-resume.restricted.json`
   與 `shows-nextup.restricted.json`（M1.5 票 01 錄的）。補上引用它們的測試，或刪掉——留著
   沒有測試看管的 fixture 會在下一次換版本時被當成還有效的證據。

## 驗收

- [ ] 兩個 500 各有一個先紅後綠的測試：併發登入拿到同一個鏡像使用者；檢查途中 Route 被刪回
      404 `route_missing` 而不是 500
- [ ] `Season 3 - 46` 這一類在語料裡有 fixture，`berth bench` 綠燈且 `auto_wrong` 沒有上升
      （貼改動前後兩次的數字）
- [ ] `list_jobs` 的查詢次數不隨 job 數成長（以查詢計數斷言，不是靠計時）
- [ ] `QbitPoller` 的整合測試涵蓋 §3.2 那三條規則，每一條的變異（把規則改回去）都會讓它紅
- [ ] 兩個 restricted fixture 要嘛有測試引用、要嘛刪掉
- [ ] lint、type、test 綠燈（貼指令輸出）

## Comments
