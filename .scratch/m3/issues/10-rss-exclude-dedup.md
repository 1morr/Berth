# 10 — 排除條件三層 + 去重

**Status:** done

**Blocked by:** 08

**讀:** plan §2.4（`exclude_json`、`rss_items.status`）、§8.5（去重鍵）、§11.4（v2 並存）；brief §7.7、§15（「全部接受，只排除」「處理」）、§18

## 做什麼

**全部接受，只排除**（brief §15）：Feed 裡的項目預設全部下載。排除條件是關鍵字或正則，比對整個標題，分全域（`settings.rss`）、Feed、RSS Series 三層，三層取聯集。

- **預設只排合集**（`release_kind != single`）：搜尋 feed 常夾著「01-13 合集」。合集不是不能解析，只是不自動下載，一次性連結與搜尋仍可手動送。
- **建議項**：720p、简体這類做成一鍵加入，不預設勾。
- 被排除的 item 狀態是 `excluded`，並記下是哪一層的哪一條擋的。

**去重**依序：同 Feed 的 GUID（票 08 已有）→ 跨 Feed 的 info hash（票 07 決定怎麼取得）→ 帳本已有同 Media / 季 / 集 / Tags。**`version` 算在 Tags 裡**：同組同集的 v2 不是重複，兩份都入庫並存，由使用者在 Jellyfin 選版本（brief §7.7、§19，使用者 2026-09-24 拍板）。

排除與去重擋下的都不是錯誤，`/rss` 的 Feed Item 清單要說得出每一筆為什麼沒下載。

## 驗收

- [x] 三層各一條測試；同一條件放在不同層都生效；關掉合集預設之後合集照常送（整合測試）
- [x] 正則寫壞時拒絕儲存並說出原因，不在輪詢時才炸
- [x] 兩個 feed 帶同一個 info hash → 只有一筆 Job
- [x] 同一集兩個字幕組、同組 v1 與 v2：四份都入庫並存（整合測試，對應 M3 驗收第三條）
- [x] 帳本已有同 Media / 季 / 集 / Tags 的不再送
- [x] `/rss` 上每一筆 excluded / 重複的都說得出原因；建議項一鍵加入；playwright 實跑，附結果
- [x] lint、type、test 綠燈

## Comments

**2026-09-25 實作**（`/implement`）。

- 驗收對照：
  - 第 1 條：`tests/integration/test_rss_screen.py::TestThreeLayers`（同一條 `Baha` 放在全域、Feed、RSS Series 三層各擋一次，理由說出是哪一層）、`tests/unit/test_rss_exclusion.py::TestScreening`（三層參數化）；`TestNotSingle::test_with_the_default_off_a_collection_is_sent` 是關掉合集預設之後合集照常送的整合測試。
  - 第 2 條：`TestBrokenRules`（服務層三層都擋，什麼都沒存）、`tests/integration/test_rss_api.py::TestExclusions::test_a_broken_regex_is_422_and_says_why`（422 `rule_invalid`，`detail` 是 `/[简繁/: unterminated character set at position 0`）。
  - 第 3 條：`TestSameTorrent`（聚合 feed 與單一 feed 同一個 hash：12 筆 Job、qBittorrent 收 12 次；綁定之前兩份都留著時也只送一次）。
  - 第 4 條：`TestVersionsLiveSideBySide`（兩個字幕組 × v1 / v2，v2 晚一週才出、那時 v1 已在帳本：四份都入庫、同一個資料夾、四個檔名）。
  - 第 5 條：`TestInLibrary`（同一個發佈換 hash 重新上傳、只有 Tags 可比的帳本列都擋；v2 不擋）。
  - 第 6 條：`web/src/pages/RssPage.test.tsx`（排除、兩種重複的句子與 Job 連結、建議項、合集開關、正則寫壞、Feed 與 Series 兩層）；playwright `web/e2e/rss-exclusions.spec.ts` 1280 與 390 實跑通過，截圖在 `web/test-results/rss-exclusions-*/`：`1-broken-regex`（欄位下「存不進去：/[简繁/: unterminated character set at position 0」、打的字留著）、`2-global-rule`（聚合 feed 的 5 筆 ANi 標「已排除」、「全域的排除條件「Baha」擋下」）、`3-duplicates`（單一 feed 的 11、12 標「重複」連到聚合 feed 送出的那兩筆下載，1–10 是「這個 RSS Series 的排除條件……擋下」）。
  - 第 7 條：見 progress.md 同日的 session 紀錄。
- 規則格式照 Sonarr 的 release profile（brief §20.12 附來源）。建議項：720p、简体、简日、繁體、繁日。
- code-review 修掉的（紅 → 綠）：Item 被記成**自己那筆 Job** 的重複（Job commit 之後中斷、綁定與輪詢同時送；`_sent_before`）；送單算出的 hash 沒寫回 `rss_items.info_hash`（plan §8.5）；讀不出字幕組的兩個標題空 Tags 對空 Tags 被當成同一個版本；解除綁定不把 `in_library` 的重複放回待綁定；三支 `set_*exclusions` 原本標 `inverse=` 自己，但收緊時擋下的放不回來，改成沒有單一反向命令。另收了 `_screen` 重複、命名（`_normalized_rules`、`_EPISODE_SIZE`、`decide`）、前端 `RulesProps` 與 `SUGGESTED_RULES` 的位置。
- code-review 未處理：
  - `_rescreen` 先讀再寫：讀出 `unbound` / `matched` 之後、commit 之前輪詢剛好把其中一筆送出去，會被改回 `excluded`（Job 照跑）。失效條件寫得出，但做不出確定性的重現；要修就改成條件式 `UPDATE … WHERE status IN (unbound, matched)`。
  - `_in_library` 與 `services/plan._duplicate_of` 的比對形狀相近（同一個資料夾、起訖集、Tags）。刻意不合併：這一層多比 Job 的發佈名，而且範圍衝突那一種在這裡不擋（交給規劃時送審核）。
  - `RulesToggle` 自己畫展開鍵（`+` / `−`）；DESIGN.md 的 `ExpandHint` 規則針對 `<details>` 的摘要列，這裡不是。規則一格一個 `×` 的樣式 DESIGN.md 還沒記，里程碑收尾跑 impeccable `document` 時補。
