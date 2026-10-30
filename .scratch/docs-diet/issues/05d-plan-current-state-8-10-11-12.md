# 05d — plan 去歷史：§8、§10、§11.7–§11.9、§12

**Status:** done

**Blocked by:** 02, 04a

**讀:** `.scratch/docs-diet/spec.md`（〈共同規則〉〈改寫規則〉）；plan §8、§10、§11.7–§11.9、§12（約 250 行 47 KB）；`docs/adr/` 的索引（brief §19）；改寫時遇到引用 brief 的地方才讀那一節

## 為什麼

plan 每行平均 330 bytes，117 處日期、1,007 處「票 NN」、12 處「推翻」混在規格裡，讀的人要自己拼出現況。plan 太大，按章節拆成 05a–05e，可以並行，後做的先 rebase。

## 做什麼

照 spec〈改寫規則〉改寫 plan §8、§10、§11.7–§11.9、§12。章節與小節號不變（§8.3 被 `berth/` 引用 35 次）。§11.7–§11.9 是票 02 之後還沒做的里程碑與遺留清單：只去歷史，不改範圍。

## 驗收

- [x] 前後大小與歷史標記數貼 Comments；剩下的標記逐條有理由
- [x] 對照表貼 Comments，§8、§10、§11.7–§11.9、§12 每個決定、規則、欄位、端點、數值都對到新版位置或 ADR
- [x] 收尾 code-review 的 Spec 軸照對照表逐節比對舊版，結果貼 Comments
- [x] 發現 plan 與 brief 的矛盾列在 Comments 問使用者，沒有自己挑
- [x] 全部檢查與 test 綠；progress.md 記一列 session；commit；不 push

## Comments

開工 commit：`e4aaec5b`。

### 前後

| | 開工 | 收尾 |
| --- | --- | --- |
| §8、§10、§11.7–§11.9、§12 大小 | 56,849 bytes、281 行 | 約 56.5 KB、約 585 行（長段拆成條列、§10 的 e2e 表格列拆成小節） |
| 歷史標記（regex，行數 / 次數） | 62 / 107 | 3 / 3 |

剩下的三條都是證據指標，不是歷史：§8.10 的 `agent-sources-ab-2026-10-28.md`、§10 的 `m5-ai-direction-2026-10-27.md` 與 §11.7 的同一份研究檔（檔名帶日期）。

### 對照表（舊 → 新）

- §8.1 → 同節分五個 `####`（送單參數、分類與全域偏好、完成判定與路徑、登入與錯誤映射）；版本鍵、成功形狀、自抓 torrent、`ensure_category`、全域偏好不碰、`stat` 驗證條件、IP 封鎖、`preferences` 表單 `json` 欄、登入不退避、錯誤映射全保留。
- §8.2 → 同節；`items()` 單一入口、瀏覽四支、圖片、掃描三支、`supported`、不呼叫 `DELETE /Items/*` 各成小節或條列。
- §8.3 → 端點、三輪請求、絕對編號、語言與顯示、快取與順序、圖片與速率與憑證各一小節；「兩個 append 拿掉」改成現況敘述。
- §8.4 → 介面、搜尋詞、合併去重與保密、缺集查詢、結果分類與取用、`ProwlarrClient`、逾時；`sites()`、`capabilities()` 拿掉的敘述刪（歷史）。
- §8.5 → 欄位表原樣；自動綁定、鍵、第一輪預覽、去重（含 `_held_back`）、排除條件各一小節。
- §8.6、§8.7、§8.9 → 同節，只去票號。§8.8、§8.10 → 同節；標題去掉「M5 票 NN」，§8.10 的票 16／23d 歷史改成一句現況。
- §10 → 表保留；e2e 兩列的細節移到〈前端 e2e〉〈e2e〉；注入防線表逐字不動，說明改條列（`test_injection_claims.py` 通過）。
- §11.7 → 同範圍；「2026-10-27 改」刪，R11 連 ADR 0016。§11.8、§11.9 無標記，原樣。§12 → 十列原樣，票號與「T0.3」「M3」措辭去掉。

### 照程式寫、與舊 plan 不符處

- 錯誤映射：`CategoryMissingError` 不存在；`raise_for_status` 實際是 429 與 5xx → `ServiceUnavailableError`、其餘 4xx → `ProtocolMismatchError`，另有 `ServiceTimeoutError`、`SchemeMissingError`、`SchemeMismatchError`；各 adapter 共用（不只四個）。
- 前端 e2e：舊寫「只蓋七條」，實際 `web/e2e/` 約 20 個 spec、多數帶 390 寬度列，改成指向 `web/playwright.config.ts`。
- §8.8：`native_web_search` 回清單（非 Anthropic 回空）；`FALLBACK` 目前是空表；R13 補研究檔連結。§8.4「兩個實作」改「每個實作」。

### Spec 軸比對（opus 子代理，對 `e4aaec5b`）

發現 1 處意思被我改掉（§8.1 送錯鍵「照偏好開始或不開始」，brief §20.7 是「就這樣開始下載」）、2 處小缺漏（`overview_en` / `poster_url_en` 欄位存在、「每類各自逐站輪流取」），都已補回。其餘小節比對完整。

### 未處理（留給使用者）

- 無 plan 與 brief 矛盾（上述 §8.1 的一處是我寫錯，已改回與 brief 一致）。
