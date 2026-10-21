# 128 — 管道故障：重試、放棄、健康頁

**Status:** done

**Blocked by:** 123

**讀:** plan §11.5〈通知〉的「故障」、§3.2（`health_checker`）；brief §20.23 與票 121 的實測結論；`berth/pipeline/health.py`、健康頁前端；票 123 的送出迴圈

## 為什麼

Discord 會限速、會掛、token 會被重設、使用者會關私訊或退出伺服器。通知壞了不能拖累任何管線，也不能無聲失敗——人不在 Berth 頁面上，通知不到就等於沒說。

## 做什麼

1. 429：照 `retry_after` 延後那一則（全域的照全域延後整個管道）。5xx 與連不上：退避重試；超過一個上限（時間或次數，開工時定一個並寫進 plan §11.5）就標成放棄、留下原因。
2. 收件人層的錯誤（票 121 實測：沒有共同伺服器與關了私訊都是 `403` / `50278`，分不出；`50007`「不能傳訊息給這位使用者」沒量到，照樣歸這一類）：那一則直接放棄，並在那位使用者的通知設定上說出原因與補法（把 bot 加進同一個伺服器、打開私訊）。
3. token 失效（401）：整個管道暫停，健康頁「通知」卡變紅並說出原因；修好 token 後自動恢復送出。
4. 寫入通知永遠不讓觸發它的狀態變更失敗；送出迴圈一個例外不拖累下一則。

## 驗收

- [x] 429 照 `retry_after` 延後（pytest，契約錄的回應）
- [x] 5xx 退避、超過上限標成放棄並記原因（pytest）
- [x] 收件人層錯誤：那一則放棄、使用者的通知設定上說出原因（pytest＋vitest）
- [x] 401：健康頁通知卡紅、停送；換好 token 後恢復（pytest＋vitest）
- [x] Discord 整個連不上時，一筆 Job 從送單到入庫照樣走完（integration pytest）
- [x] 全部檢查、pytest、vitest 綠；plan §11.5 記下放棄的上限；CHANGELOG、progress.md 已更新

## Comments

- 2026-10-21 實作（session 紀錄見 progress.md）。截圖在本票目錄（演練後端 `healthy`：健康頁通知卡未設定／已設定，設定頁收件人到不了重新整理後仍在、換 ID 後收掉；1280 與 390）。token 被拒的健康卡在演練替身上演不出來（存 token 時就被拒），由 vitest 守。
- **開工時定的**（寫進 plan §11.5「故障」）：放棄上限是時間，`not_before` 起 24 小時；連不上是管道層級退避，30 秒起加倍到 1 小時；`401` 存被拒 token 的指紋（換了就恢復，送的那幾秒換了新的也不會被蓋成被拒）；收件人到不了記在 `users.notify_unreachable_*`（migration `e3a9c6f1b207`），送到一則（含測試）或換 ID 清掉；`400` 超長與組不成句子當場放棄；通知卡不算進 `degraded`。
- 票 123 留給這張的兩條：太舊的不送（`_give_up_stale`）做了；「一輪不控速」沒另做——單則的 `429` 延後那一則並停這一輪，下一輪接著（理由在 plan §11.5、progress 偏差）。
- 變異手跑（`send_due` 一帶 11 條，各紅一條以上）：拿掉放棄、token 從不算被拒、被拒只記旗標不比 token、忽略 global、忽略單則 429、收件人到不了照重試、不退避、queue 的例外往上丟、組字的例外往上丟、送到不清收件人記號、換 ID 不清。
- 測試抓到一個真 bug：`queue_ready` 的 log 原本寫 `extra={"job": …}`，撞上 `berth.logs` 的 record factory（`KeyError: Attempt to overwrite 'job'`），只在 logging 設定過之後才爆。改用 `job_context`。**`services/series_review.py:377` 有同樣的寫法沒改**（不在這張的範圍，沒有 repro）。
- code-review 已改：token 被拒時卡片外框也換 `rule-strong`（DESIGN.md〈健康頁的卡片〉）；`_reachable` 改名 `_clear_unreachable`（它會改資料）；plan 寫準「單則 429 也停這一輪」；設定頁「沒送到」與時間之間隔一個點（截圖看到黏字）。
- code-review 未處理：
  - 「連續失敗」數字是 `text-blocked-ink`，照 `PollerCard` 的前例；兩張卡要不要一起改成中性，留給 M4 UI 收尾（票 132）的 critique。
  - 「24 小時」寫在 `GIVE_UP_AFTER` 之外還寫死在 i18n 兩處（中英）與 CHANGELOG，沒有閘門；改常數時要一起改。
  - `notify.backoff` 與 `downloads.backoff` 同一個形狀（加倍到上限），沒抽共用。
  - `queue_ready` 的 try 只包住讀與組內容，`session.add` 的 flush 在呼叫端 commit；內容是純 JSON 原始型別，沒有失效條件。
  - 退避中按「測試」送到了不清管道的退避：健康頁照說「連不上」到退避結束（照「測試不動管道退避」的決定）。
  - `DESIGN.md` 的卡片清單還沒列通知卡，里程碑收尾 `/impeccable document` 時補。
