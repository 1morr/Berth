# 62 — Jellyfin 掃描收斂：只刷新 Berth 的媒體庫，第一次入庫不再等 2.5 分鐘

**Status:** done

**Blocked by:** None — can start immediately

**讀:** `docs/research/usability-audit-2026-10-07.md` §2 E2、§3 S1（入庫後 2 分 35 秒）、S3（同樣 2.5 分鐘）、§5.2、§8 P1-9；brief §20.1（路徑通知對空媒體庫無效）、§16.4 物件表；plan §8.2 / resolver 的退避

## 為什麼

- 入庫當下 Berth 會通知 Jellyfin 路徑變更；但 Jellyfin 對從沒掃到過內容的媒體庫，收到通知不會有反應（brief §20.1）。
- Berth 要等兩次反查都沒找到，才改請 Jellyfin 跑「掃描媒體庫」排程任務；S1、S3 實測都晚了約 2.5 分鐘。這段時間作品頁寫「Jellyfin 還在掃描」，實際上還沒請它掃。
- 那個排程任務會掃**整台伺服器的所有媒體庫**。對既有 Jellyfin（可能很大）這是 D1 清單外的寫入，文件與閘門都沒列（E2）。
- 使用者拍板 E2：收斂成只刷新 Berth 寫入的那個媒體庫；做不到時，把全庫掃描寫進 §16.4 物件表與既有服務的卡片。

## 做什麼

1. **先查證**：Jellyfin 12.x 的 OpenAPI 有沒有「只刷新單一媒體庫（或單一資料夾項目）」的端點，以及它對空媒體庫有沒有效。
   - 寫最小實驗放 `scripts/experiments/`，對真的 Jellyfin 12.1 跑；結論與來源補進 brief §20.1。
2. 查證可行：
   - 反查的後備改成只刷新那條 Route 的媒體庫；
   - **媒體庫還沒有任何項目時，第一次入庫就直接刷新**，不等兩次沒找到；
   - Issue「重新掃描媒體庫」的按鈕也改成只掃那一個。
3. 查證不可行：保留全庫掃描，但 brief §16.4 物件表、既有 Jellyfin 卡片、Issue 按鈕都寫明「會掃整台伺服器」；第一次入庫的「空媒體庫」情況照樣提早觸發。
4. 作品頁在 Berth 還沒請 Jellyfin 掃描前，不說「還在掃描」；說「已通知 Jellyfin，等它認」之類的準確說法。

## 驗收

- [x] 實驗腳本與結論（brief §20.1 附來源）：`scripts/experiments/jellyfin_scan_scope.py`，對 12.1.0
- [x] 整合測試：空媒體庫第一次入庫立即刷新；刷新的範圍是那一個媒體庫（或照查證結果，雙向）
- [x] 實跑：全新套件內入庫一部，Jellyfin 認到的時間與文案，附截圖與時間戳（`62-jellyfin-scan-scope/`，見 Comments）
- [x] 全部檢查、test、真服務 e2e 綠燈；brief §16.4、plan、CHANGELOG 同步；progress.md 記一行

## Comments

- 2026-10-08 票 55 補（`docs/research/unraid-trial-2026-10-08.md` §3.3、§6 U8）：Unraid 上空媒體庫第一次入庫到「Jellyfin 已收錄」12 分 34 秒。Berth 在 18:55:52 請整庫掃描的同時把下一次反查排到 10 分鐘後（`resolve_after`），Jellyfin 的掃描 12 秒就完成了。改掃描範圍時一起看「請掃描之後多久再問」。

- 2026-10-13 實作（session 結論）：**查證結果是「部分可行」**。`POST /Items/{媒體庫}/Refresh`（兩個 `Default`，控制台「掃描媒體庫」同一支）只掃那一個媒體庫，實測另一個媒體庫同時放的新檔沒被掃到；但它只看得到 Jellyfin 已經有的實體資料夾，**第一次全庫掃描時空著的路徑只有全庫掃描建得出來**（空媒體庫、兩個路徑的媒體庫裡空的那個，單一刷新與路徑通知各等 90 秒都是 0）。所以照第 2、3 點合併：Berth 的路徑已被列出過 → 等第二次沒找到只刷新那個媒體庫；還沒列出過 → 第一次沒找到就全庫掃描，§16.4、既有 Jellyfin 卡片、待處理那一件都寫明。
- 實跑（真服務 e2e 的 M1 段，全新套件內、三個空媒體庫，UTC）：15:15:34 三筆入庫並通知 → 15:16:08 `asked jellyfin to scan`（`scope: server`）→ 15:17:08 三筆都寫下 `jellyfin_item_resolved`，**入庫到「Jellyfin 已收錄」1 分 34 秒**（之前 S1 2 分 35 秒、Unraid 12 分 34 秒）。截圖：`62-jellyfin-scan-scope/1-waiting-151608.png`（「已通知 Jellyfin，等它收錄；Berth 下一次確認在 4 秒前」）、`2-found-151711.png`（「Jellyfin 已收錄」）。e2e 24 passed、16 分 35 秒（原本約 20 分鐘）。
- **請掃描之後多久再問**：全庫掃描那條在第一次沒找到時請，接著是排程的第二次——改成 1 分鐘（原本 2 分鐘）。只刷新媒體庫那條仍是第二次沒找到才請、之後最晚 10 分鐘（`SCAN_SETTLE`）：列過的路徑平常路徑通知就夠（brief §20.1 量到 100 秒內），刷新只是後備；把間隔縮短會在大的媒體庫上幾分鐘內燒完 6 次反查，開出一件假的 `jellyfin_item_unresolved`。
- code-review 沒處理的：(1) Issue 那一件只能寫條件句（平常只刷新；沒列出過時掃整台），按下去之前說不出這一次是哪一種——要說得先在讀清單時問一次 Jellyfin；(2) 路徑還沒被列出之前，每一次沒找到都會再請一次全庫掃描（共 6 次，原本 5 次）；執行中再請是空操作，Jellyfin 看不到那條路徑（沒掛 `/data`）時大的既有 Jellyfin 會被掃 6 次，§16.4 已寫明；(3) 「入庫當下」就掃（importer 通知完就判斷）會再快 30 秒，但要多一個呼叫端與一次列清單，沒做；(4) `_rescan` 問 `Series,Movie`、resolver 照媒體庫類型只問一種，結果相同，沒收成一份。
- 順手看到、不在這張票：作品頁的「Berth 下一次確認在 4 秒前」——`resolve_after` 已過、排程那一輪（15 秒一次）還沒跑到時，說的是過去的時間；e2e 的 berth log 在 15:19:34 有一行 asyncio「Task was destroyed but it is pending」（`Queue.get`，看來是 SSE 訂閱者），與掃描無關。
