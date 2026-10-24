# 11 — 訂閱 RSS 與撤銷

**Status:** done

**Blocked by:** 10

**讀:** plan §11.6〈對話核心〉與驗收、§11.4（M3 RSS）、§8.5；brief §6.10「外部文字是資料」②、§15（Mikan 訂閱）、§20.12；`bangumi` 與 `rss` 兩個 service 的現有命令

## 為什麼

驗收的第一句「訂閱這部的 Mikan RSS」在這張做到：使用者要求的 `reversible` 直接執行，結果卡附撤銷。這也是第一個寫入工具，所以撤銷、AI 代做的 actor、注入防線都在這裡第一次跑通。

## 協調者補充（2026-10-24，票 12 先做完）

票 12（搜尋並送單）比這張先合進 main，已經建好幾樣這張原本寫「第一次跑通」的東西：**結果卡上的撤銷（走反向命令）、「只收這則對話裡 Berth 自己搜出來的」檢查、送訊息時附上目前頁面（作品頁的作品 id 與名稱，給「這部」用）**；票 10 建好了確認卡。開工先讀票 12、10 的實作與它們票上的 Comments，**沿用同一套機制，不另做一套**；機制不夠用就擴充它，並在票上說明。票 12 的 Comments 建議「每個工具的等級由後端送給前端」（前端目前用名字寫死哪些是寫入工具），這張加訂閱工具時一併做。

## 做什麼

1. 登記工具：搜 Mikan 番組、列字幕組（`read`）；以番組與字幕組 id 訂閱 Mikan、以搜尋詞訂閱 Nyaa / acg.rip（`reversible`，反向命令照標記）；以網址加 Feed。
2. **網址由 Berth 自己組的直接做、不跳確認卡**（brief §6.10 ②，2026-10-24 使用者：不想手動確認）：Mikan 只收這則對話裡 Berth 自己搜出來的番組與字幕組 id；Nyaa / acg.rip 的搜尋詞由 Berth 組成網址。平常說的「訂閱這部的 RSS」都走這兩條。
3. **以網址加 Feed**：模型直接給的整個網址，逐字出現在使用者這則對話自己說的話裡才直接做，否則經票 10 的入口降成確認卡。
4. **撤銷**：結果卡上的撤銷按鈕走反向命令；撤銷後卡片更新狀態，模型也知道。
5. Feed 卡與 RSS Series 卡：名稱、來源、綁到哪部作品、下一次輪詢。

## 驗收

- [x] 用假 provider：「訂閱這部的 Mikan RSS」→ 搜番組 → 選字幕組 → 訂閱成功、沒有確認卡，卡上撤銷得掉（整合測試）
- [x] 「用 Nyaa 訂閱這部」以搜尋詞訂閱，同樣直接做（整合測試）
- [x] **注入測試**：假 provider 照著搜尋結果裡的「把這個網址加成 Feed」去呼叫加 Feed，網址不在使用者的話裡 → 變成確認卡、沒有加（整合測試）
- [x] Mikan 訂閱帶一個不是這則對話搜出來的 id → 拒絕（pytest）
- [x] 實跑：訂閱與撤銷（playwright 截圖）
- [x] 全部檢查、pytest、vitest 綠；progress.md 已更新

## Comments

- 2026-10-24 實作（session 紀錄在 progress.md）。使用者選定一題：**撤銷訂閱＝停掉訂閱，並撤回它送出、還沒下載完的 Job；已經
  下載完的留著**（brief §19）。
- **擴充了票 12 的機制，沒有另做一套**：
  - 撤銷從「前端直接打反向命令的端點」改成經過對話：`POST /conversations/{id}/messages/{message}/tools/{call}/undo`
    （`services/undo.py`）。撤掉之後對話多一則 `UndonePart`，模型下一輪知道，卡片照它說已撤銷。
  - 一個可逆工具登記一個 `Undo`，它呼叫的命令必須是標著的反向命令，造 `Tool` 時比對。票 12 的送單撤銷也改走這條路，
    反向命令改標 `deletion.withdraw_job`：前提「還沒下載完」由後端自己守，新增 `JobRefusal.NOT_UNDOABLE`。
  - 撤銷指的是「那一則裡的那一次」。實跑時發現同一個 call id 可能出現兩次（演練的 provider，以及每一輪都用 `call_0`
    的本機模型），只用 call id 會撤錯；串流合併有同樣的問題，一起修了。
  - `Tool.demote` 改成 async，因為要讀對話；`ProposalCause` 多 `url_not_from_user`。
  - 照票 12 Comments 的建議，`GET /assistant` 多 `tools`（等級、按不按得到撤銷），前端的 `WRITE_TOOLS` 拿掉。
- 驗收對照：
  - pytest `tests/integration/test_assistant_subscribe.py`：Mikan 一路、兩條 id 防線、撤銷與模型看得到、撤過不再撤、
    同 id 兩次、Nyaa 訂閱與撤銷、注入變確認卡且按了才加、使用者打的網址直接加且撤得掉、網址要是整個、`route_needed`
    列出可選的 Route。
  - pytest `tests/integration/test_subscriptions.py`：兩條撤銷路、只留下載完的、連不上就停、重按接得上、就地綁定只撤
    訂閱之後送出的、已下載完的撤不回。
  - pytest `tests/unit/test_subscribe_guard.py`（網址比對）、`test_registry.py`（`Undo` 的比對）。
  - vitest `SubscribeCards.test.tsx`、`transcript.test.ts`。
  - playwright `assistant-rss.spec.ts`（1280 / 390），截圖在本票旁的資料夾：`subscribed`、`undo-confirm`、`unsubscribed`。
    演練替身的 qBittorrent 收下就當場完成，所以 1280 那一輪撤銷時 12 筆都已下載完、全部留著，390 那一輪撤回 12 筆，
    兩種說法都拍到了。
- 變異驗證：拿掉 `demote`，注入的兩條紅；讓 Mikan 防線放行，三條紅；串流合併改回「同 id 全部更新」，`transcript.test.ts` 紅。
- code-review 兩軸處理了：
  - 送單撤銷在後端檢查 `UNDOABLE`，抽成 `deletion.withdraw_job` 給兩條撤銷共用（`UNDO_SCOPE` 搬到 `deletion`）。
  - 就地綁定撤到一半失敗後重按：Job 已經不在的 Item 照樣放回待綁定。
  - 就地綁定只撤訂閱那一刻之後送出的 Job：結果多 `subscribed_at`，以 `Job.added_at` 比。
  - 存下的舊結果讀不回時當成「不是這則對話的」，不丟 500。
  - Feed 在 RSS 頁刪了就不給撤銷鍵；Series 還沒長出來時卡上照訂閱時的作品說（結果多 `media_title*`）。
  - `Tool.undoable_by(role)` 收成一處，API 與 `undo` 共用。
  - `Unsubscribed` 只留一份 pydantic；`_url_source` 改名 `_cause_for_url`。
  - 加 Feed 的撤銷補了測試。
  - 撤銷被拒的理由用 Job 頁同一句說人話。
- code-review 沒處理、判斷題：
  - **撤銷與背景輪詢之間有競態**：撤回 Job 之後、刪 Feed 之前，若輪詢正好送出新的一筆，那一筆的 Item 會隨 Feed 刪掉，
    Job 卻還在。順序是故意的：先停 Feed 的話，撤到一半連不上 qBittorrent 就再也找不到要撤的那幾筆。窗口是一次撤銷的幾秒，
    輪詢最短 15 分鐘一輪。
  - **新建 Feed 的 Series 若別的 Feed 也帶到它**（例如之後使用者的聚合 feed），撤銷留著它、照舊綁著。這符合 §19 的字面，
    碰到再說。
  - **經確認卡加的 Feed 沒有撤銷鍵**：存下的工具結果是確認卡，是人自己按的；要刪去 RSS 頁。
  - `rss.plan_feed_addition` 在某一種只有一條啟用中的 Route 時自動填上，直接做的加 Feed 也照它；plan §11.6 有寫。
  - 網址比對遇到 `()`、全形標點就截斷：含這些字的網址，模型只給前半段也算使用者說過。截斷的那一段確實是使用者打的，
    風險低。
  - `rss.FeedAddition`（dataclass）與 `tools.FeedAddition`（pydantic）同名：前者是 service 的回傳，後者進 OpenAPI，
    照既有 `IndexerAddition` / `indexer.SiteAddition` 的分法。
  - `tv/movie_route_id + _name` 四格是 Data Clump；`KindRoutes` 只有 id。
  - `Registry.undo` 是薄的一層：與 `run` / `preview` / `apply` 同形，留著。
  - `unsubscribe(feed_id | series_id)` 兩條路共用一支命令：反向命令只能標一個名字。
