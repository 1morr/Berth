# 51 — 作品頁的 Jellyfin 狀態與媒體庫頁一致

**Status:** done

**Blocked by:** None — can start immediately

**讀:** `docs/research/wizard-audit-2026-10-06.md`（S6 Jellyfin 那列、§3.2 Jellyfin 回驗那列、改進清單 P2-9）；M4 票 02；brief §20.1、§20.8；plan §3.2、§8.2

## 為什麼（2026-10-06 審計，實測）

- 入庫後約 2 分鐘，Jellyfin 已經有這部片：媒體庫頁出現在牆上，作品頁也有「在 Jellyfin 看」。
  同一時間，作品頁的「檔案與版本」卻寫「Jellyfin 還在掃描，下一次查詢 9 分鐘後」，原因是 resolver 的退避。截圖 s6-13、s6-14。

## 做什麼

1. 先定位兩邊讀的是什麼：媒體庫頁直接問 Jellyfin，作品頁讀 resolver 的排程狀態。決定修哪一邊、為什麼，寫在 Comments。
2. 可選的方向：作品頁打開時順便查一次，查到就提前回驗；或在退避中改說「Berth 下一次確認在 N 分鐘後」，不要說 Jellyfin 還在掃。
   回驗的權威來源仍然是 resolver（票 02）。

## 驗收

- [x] 整合測試：Jellyfin 已有該項目、resolver 還在退避時，作品頁不寫「還在掃描」（雙向：Jellyfin 真的還沒有時照舊）
- [x] vitest：作品頁文案（zh-Hant 與 en）
- [x] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈

## Comments

2026-10-07 實作：

- **兩邊讀的是什麼**：媒體庫頁的牆（`inventory.read_wall`）與作品頁的觀看區（`GET /media/{id}/watch`、`watch_area`）都**當下問 Jellyfin**；作品頁的「檔案與版本」讀帳本（`inventory._file_presence`：有 `jellyfin_item_id` 是已收錄、有 `resolve_after` 是還在掃描），也就是 resolver 的排程。審計那一刻是第二次反查（入庫後 2 分 30 秒）剛沒找到，下一次排在 10 分鐘後。
- **修作品頁那一邊，用票面的第一個方向**：作品頁有檔案還在等時，前端送一次 `POST /media/{id}/resolve`（`resolver.resolve_early`），替這部作品還沒到時間的帳本先問一次 Jellyfin。找到而且認完的走 `sweep_resolutions` 找到的同一條路（`_found`、回驗、`jellyfin_item_resolved`），回驗的權威仍是 resolver；沒找到、還在認、問不到的一列都不動——**不算一次、不改排程、不通知**，否則多開幾次頁面就把 6 次用完了。不選「只改文案」：Jellyfin 真的已經有了，說「Berth 下一次確認在 N 分鐘後」仍然是讓人等一個不必等的東西。不放進 `GET /media/{id}`：那一支不問 Jellyfin，Jellyfin 慢或掛時頁面照樣先畫（觀看區同一個取捨）。
- **文案**：還沒列出的那一列照舊說「Jellyfin 還在掃描」，後半改成「Berth 下一次確認在 …」（en: "Berth checks again"），排程是 Berth 的不是 Jellyfin 的。
- **只問還沒到時間的**（code-review spec 軸）：到時間的歸 15 秒醒一次的排程那一輪；兩邊同時寫同一列，「找到了」會被「排下一次」蓋掉。前端一部作品只送一次（`asked`，含 StrictMode 重跑 effect 與詳情被讀回還在等的時候）。
- **演練情境 `late-scan`**（票面沒要求）：替身 Jellyfin 第一次被通知滿 170 秒才列出，重現審計 S6 的時間線，README 情境表加一列。
- 實跑（`late-scan`，playwright 1280）：送到 Anime、約 3 分半後先讀 `GET /media/tv:120089`——三集 `searching`、`resolve_attempts` 2、下一次 08:47:56（約 9 分鐘後），正是審計的狀態；打開作品頁之後三集 `found`、`resolve_attempts` 仍是 2，摘要「Jellyfin 已收錄 3」、整區沒有「掃描」。`import` 情境（替身不會掃）：第一次沒找到之後打開，送了一次 POST、照舊 `searching`、次數不變，列上是「Jellyfin 還在掃描，Berth 下一次確認在 2 分鐘後」；390 寬英文 "Jellyfin is still scanning; Berth checks again in 1 minute"，無橫向捲動。截圖 `.playwright-mcp/t51-found.png`、`t51-searching-1280.png`、`t51-searching-390-en.png`（gitignored）。

code-review（Standards / Spec 兩軸 opus）已修：只問還沒到時間的、前端一次、`lookEarly` 改名（CONTEXT 的 Resolve 避用 lookup）、`Effect.REVERSIBLE` 與 `Any` 補理由、CONTEXT.md 的 Resolve 補一句。未處理：

- **`resolve_early` 與 `sweep_resolutions` 骨架相同**、`_look_up` 的吞錯換成自己的 log：兩處而已，第三個呼叫端出現再抽「一批帳本問一次」。
- **同一筆 Job 的兩列被兩邊在同一刻各找到一列**：兩邊的 `_all_found` 都看不到對方未 commit 的那一列，「全部找到」可能沒人寫（`_announce` 原本的 check-then-insert 也有同類的重複寫）。要排程那一輪剛好在作品頁打開的那一刻問同一筆的另一集；沒有 repro，不修。
- **「還在掃描」在提前那一次問不到 Jellyfin 時沒有驗過**：那時觀看區也問不到，頁上另有「問不到 Jellyfin」；頁面一直開著期間 Jellyfin 掃到了，要重新整理（排程那一輪照常會找到）。
- `user` 也打得了這一支（看詳情的人都會打開作品頁），它寫的只是排程那一輪本來就會寫的東西。
