# 02 — 通知連結的作品頁路徑閘門

**Status:** done

**Blocked by:** None — can start immediately

**讀:** plan §11.5〈M5 開工前的審查補記〉第一條、§7；M4 票 124 的 Comments；後端 `deeplink.MEDIA_PAGE` 與前端的路由表

## 為什麼

通知裡「可以看了」的連結由後端以 `deeplink.MEDIA_PAGE`（`/media/{media_id}`）組成，前端的作品頁路由是 `/media/$mediaId`。兩邊今天只靠註解綁在一起：前端改路由時，通知連結會靜靜指到 404，沒有任何測試會紅。M5 的結果卡與 M7 的 Discord embed 也要連回作品頁，連結會變多，先把這道門補上。

## 做什麼

1. 讓兩邊讀同一份事實，或讓一邊的測試讀另一邊的定義：例如前端測試從 OpenAPI 或後端匯出的常數取路徑模板，對照路由表解析得到作品頁。挑最不需要新機制的做法，說明採用的理由。
2. 若後端還有其他組前端網址的地方（Job、Issue 頁），一起納入同一道閘門。
3. 雙向變異驗證：改前端路由會紅，改無關的路由或排版不紅。

## 驗收

- [x] 前端作品頁路由與後端連結模板不一致時測試紅（造違規證明）
- [x] 改無關路由不紅
- [x] 全部檢查、pytest、vitest 綠；progress.md 已更新

## Comments

- 2026-10-24 實作（session 紀錄見 progress.md）。
- **做法：後端的頁面集合經 OpenAPI 進 `schema.d.ts`，前端測試拿真的路由表解析**。五條常數改成 `deeplink.BerthPage`（StrEnum：`/media/{media_id}`、`/review`、`/issues`、`/rss`、`/weekly/{report_id}`），`main._document_pages` 照 FastAPI 文件〈Extending OpenAPI〉換掉 `app.openapi`、把它放進 components；`web/src/berthPages.test.ts` 的 `PAGES: Record<BerthPage, RoutePath>` 寫明每一條落在哪一條路由，代入樣本值後用 `router.getMatchedRoutes` 解析。**為什麼選它**：後端封閉集合 → OpenAPI → 產出型別 → 前端 `tsc` 是 repo 已經在用的那一條（拒絕理由、`JobState`），過期有 `pytest`（`TestBerthPages`）與 CI 的 `git diff` 兩道；前端測試不需要 Python 環境（與 `schema.d.ts` 進版控同一個理由）。沒選的：前端測試用正規式讀 `deeplink.py`（後端改排版就會讀錯，過不了「改排版不紅」）；另立一份兩邊都讀的 JSON（新的檔案格式與載入，而且前端路由要字面型別、讀不了 JSON，最後一樣是測試去對）；只斷言「解析得到某一條路由」（之後加接住一切的 404 路由就每一條都算過）。
- **第 2 項**：後端組前端網址的只有 `notify.py`（作品頁、週報、經 `waiting.LIST_PAGE` 的三份清單）與 `waiting.py`（清單頁加錨點），五條全進 `BerthPage`；目前沒有組 Job 頁的。
- **雙向變異（實跑，改完還原）**：真的 `routes.tsx` 把 `/media/$mediaId` 改成 `/title/$mediaId` → vitest `1 failed | 6 passed`、`tsc` 紅在 `PAGES`；改名並同時把 `PAGES` 的值改成 `/title/$mediaId` → vitest 照樣紅（模板 `/media/…` 解析不到）、`tsc` 綠；`/library` 改成 `/inventory` → vitest `7 passed`、`berthPages.test.ts` 沒有型別錯；後端加 `JOB = "/jobs/{hash}"` → `TestBerthPages` `1 failed`，重跑 `gen:api` 後 `tsc` 紅在 `PAGES` 少鍵。檔內另有一組小路由表的自測，留下「作品頁改名紅、無關路由改名不紅」兩個方向。
- code-review 已改：`waiting_now` 的錨點改從 `LIST_PAGE` 取（原本「來源 → 頁」有兩份）；`development.md` 原寫「只從 `BerthPage` 來」，改成說明那是慣例、沒有閘門；plan §11.5 的舊名 `MEDIA_PAGE` 改成新名。
- code-review 未處理：
  - 錨點（`#issue-5`、`#series-7`、`#audit-12`）不在閘門裡：後端 `waiting.py` 與前端各清單頁的 vitest 各寫一份同形的字串。錨點錯了頁面照樣開，只是不捲到那一列。
  - `berth_link(public_url, path: str)` 收任意字串，繞過 `BerthPage` 手組的路徑沒有閘門；收窄型別要另立「已代入參數的頁面」型別，現在只有兩處呼叫，沒做。
  - `BerthPage.MEDIA.format(media_id=…)` 的參數名沒有閘門；改模板的參數名時 notify 的測試會在執行時 `KeyError`，不會靜靜錯。
  - `_document_pages` 放在 `main.py`（app factory），審查建議搬到 `api` 層；現在只有這一個 components 擴充，沒搬。
  - commit type 用了 `test(links)`，實際上 services 也有重構；已 commit，沒改寫。
