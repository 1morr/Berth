# 02 — plan §11 已驗收的 M0–M5 小節封存，遺留項目歸位

**Status:** done

**Blocked by:** 01

**讀:** `.scratch/docs-diet/spec.md`；plan §11（§11.1–§11.6 搬走，§11.7、§11.8 留）；brief §17、§18；`docs/progress.md` 里程碑表

## 為什麼

plan §11 有 432 行。M0–M5 的六節（§11.1–§11.6，約 374 行 85 KB）都已驗收，拆票後以票為準，沒人再讀。但其中有些「延後」「遺留」的項目還沒做，搬走就沒人看得到了。

## 做什麼

1. **搬**：§11.1–§11.6 全文搬到 `docs/archive/<里程碑>.md` 新的 `## plan §11` 段（§11.2b → `m1.5.md`）。
2. **留標題**：plan 每節留標題加一行「已驗收（日期），內容在 `docs/archive/mX.md`」。`berth/`、`web/` 引用 §11.1–§11.6 共 84 處，標題號碼不能變。
3. **遺留項目**：逐條掃六節裡「延後」「遺留」「之後」「M6」「不做」這類標記的項目，對 `.scratch/` 票的 `Status:` 與 `git log` 判斷做了沒有。
   - 沒做、屬於 M6 範圍的 → §11.7；其餘 → 新節 §11.9「不排里程碑」（號碼接在 §11.8 後）。
   - 每條附原出處（archive 的位置）。
   - 判不出做了沒有的不搬，列在 Comments 問使用者。
4. **改引用**：progress.md 里程碑表的「拆票前讀」欄、`CLAUDE.md`、brief §17 裡指到已封存小節的，改指 archive。舊票與 research 不改（標題那一行接住）。

## 驗收

- [x] `scripts/docs_moved_lines.py` 對 `docs/plan.md` → `docs/archive/*.md` 跑出「遺失 0」，輸出貼 Comments（遺留項目是複製到 §11.7 / §11.9，原文也在 archive）
- [x] 遺留清單表（項目、原出處、做了沒、證據、去處）貼 Comments
- [x] plan §11.1–§11.6 只剩標題加一行，號碼不變
- [x] 全部檢查與 test 綠；progress.md 記一列 session；commit；不 push

## Comments

`scripts/docs_moved_lines.py 81360460 docs/plan.md -- docs/archive/*.md`：`removed 290 lines, found 290, missing 0`。§11.9 的 11 條是複製（原文也在 archive）。

### 遺留清單（掃描由子代理做，我抽查 ROUTE_CHECKS、AccountDisabledError、whenText、SHORT_FEATURE 仍在程式碼裡）

| 項目 | 原出處 | 做了沒 | 證據 | 去處 |
| --- | --- | --- | --- | --- |
| 卡住而沒有 Issue 的三種 Job 開 Issue（R11） | m5 §11.6 | 沒做 | 實作 commit 只在放棄的備份分支，`.scratch/` 無 m6 | §11.7 已列，不動 |
| 背景 AI、影子模式、接管開關、AI 活動頁 | m5 §11.6 | 沒做 | 無 m6 票 | §11.7 已涵蓋 |
| Discord、個人 token、MCP | m5 §11.6 | 沒做 | 無 m7 票 | §11.8 已涵蓋 |
| 缺集分批；qB 5.x recheck；管線 Issue 自動收；磁碟門檻與 `submit_failed` 重送；held_proposal 比帳本 | m2–m4 | 做了 | M3 票 20、M3 票 02/03、M5 票 05 | 不搬 |
| §11.9 的 11 條 | m2 D/C 組、m3 收尾 | 沒做 | 程式碼現況（如 `schemas.ts:57`、`jellyfin_access.py:133`、`classify.py:78`） | §11.9 |
| 永久不做（內嵌播放器、品質升級替換、字幕組白名單、頻道 webhook、log 遮罩只遮 query） | 多處 | 非遺留 | plan 原文已寫理由 | 不搬 |

### 判不出，沒搬，請使用者決定
- 精靈左欄剖面與右欄纜繩列兩份實作（m2 B/D 組）：M4 重做精靈後可能已消失。
- EN 子分頁 `Library paths` vs `Routes`（m2 B 組）：M4 票 132 改回 `Library paths`，可能已取代。
- m2 B 組十餘個小 UI 項（`<h1>`、Tab 停留點等）。
- m3：`prime_feed` 撞 unique 冒 500；`QUEUE_LIMIT` 截斷時「全部確認」；`QBITTORRENT_WEBUI_PORT` 改後仍連舊位址；「以發佈時間推測虛擬季」使用者未追認。
- m4：約二十條「不排里程碑」（如 `?page=1e20` 回 500，疑未修）、票 22 `downloadPath`、週報 P2/P3、通知設定 P3、全站頁面標題都是 Berth（疑未修）。
- 規劃資料夾 `docs/research/m5-ai-direction-2026-10-27/02-leftovers-m0-m3.md`、`03-…` 有 502 條歸類可對。

引用：CLAUDE.md、progress.md 里程碑表、brief §17 都沒有指到 §11.1–§11.6，無需改。

### code-review（`81360460`..`5c1bbc68`）處理

- **已修（commit 後補）**：測試改讀 archive 會讓「注入的防線」表凍結成快照。表是現況契約，改複製到 plan §10 末，`test_injection_claims.py` 改回讀 `docs/plan.md`（archive 保留原文，遺失 0 不變）。
- **已修**：「全站頁面標題都是 Berth」確認沒做（`web/src` 無 `document.title`），補進 §11.9。
- **未處理，請使用者決定**：
  - m4 §11.5：規劃與輪詢的解析 CPU 跑在事件迴圈上（原文「先量再決定」），只有 mediainfo 有 `to_thread`，疑未做，未量測。
  - m5 §11.6「不在 M5」：TMDB discover / recommendations / collection 新端點，找不到實作也沒歸位。
  - m4 約 40 條仍列「判不出」，逐條判定留給後續（對照 `docs/research/m5-ai-direction-2026-10-27/03-leftovers-m4-and-deviations.md`）。
  - m3 Jellyfin 帳密錯訊息（票 06h）：i18n 有 `invalid_credentials`，判為做了，原本漏列於遺留表。
- **未處理（範圍外）**：`docs/development.md` 有 4 處引用 §11.3–§11.5 小節內文（第 99、265、270、600 行），現在落到標題那一行，歸票 06。archive 開頭說明只寫自 progress.md 封存，未提 plan §11 段，可接受。
- Standards 軸其餘項目（stub 的日期、`PLAN` 命名）為判斷題，不處理。
