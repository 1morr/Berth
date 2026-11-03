# 05 — 第一批收累計編號

**Status:** done

**Blocked by:** 04

**讀:** spec〈範圍〉「第一批擔保收累計編號」；brief §15、§20.27；`docs/research/review-queue-2026-11-01.md`；`scripts/experiments/first_batch_rule.py`

## 為什麼

審核佇列另外 17 件是第一批確認，其中累計編號的（夜櫻 40 → S2E13）讀法其實是確定的，但第一批現在不擔保。量過才收。

## 做什麼

1. 第一批擔保的條件多一種讀法，其餘條件不變：理由是 `absolute_cumulative`、季號寫明、Series 沒設季號與 offset、檔名集號剛好等於前面各季集數加對到的集號，而且那一集剛播（上緣維持兩天）。其他絕對編號與重數推測仍不擔保。
2. **閘門**：`scripts/experiments/first_batch_rule.py` 的語料與對抗輪都要擔保錯 0。不是 0 就不收這一條、回報使用者，這張票視為做完（結果記在 Comments 與 brief §15）。
3. 已入庫的舊列不另外掃：下一集自動落地時，整批照 `first_batch.vouch` 一起看。已經完結、不會再有下一集的，留給人按確認。
4. 文件：brief §15、`parser/first_batch.py` 開頭的條件說明。

## 驗收

- [x] 閘門跑完、數字貼在 Comments（語料與對抗輪的擔保錯數）
- [x] 閘門過了：累計編號的（夜櫻 40 → S2E13）由系統確認；重數推測與其他絕對編號仍要人確認（測試）。沒過：程式不改，已回報使用者
- [x] `berth bench` 的 `auto_wrong` 不升（貼前後數字）
- [x] 全部檢查、pytest 綠；progress.md 已更新

## Comments

- **閘門過了**（`scripts/experiments/first_batch_rule.py`，離線兩輪）：語料 36 份擔保 10 → 12、擔保錯 0 → 0；對抗輪 30 份擔保 9 → 11、擔保錯 0 → 0。多的兩份是 `anime/spy-x-family-s3-ani`（S03E13）與 `-dynamis`（S03E10），都對。`--online` 的 split-cour 與真 RSS 兩段沒跑：這個 worktree 沒有 `.env` / TMDB key，票的閘門只要求前兩輪。
- **`berth bench`**：前後相同，`auto_wrong` 0 → 0（40 份、904 檔，high 0/112、medium 0/143 錯）。
- **條件**（`parser/first_batch._counted_from_first_season`，另一份白名單 `_CUMULATIVE`）：理由有 `absolute_cumulative`、寫明的季號（發佈名或資料夾）**而且它的 `season` 就是對到的那一季**（code-review 補的：解析器本來只在相同時產生，這裡不靠它）、檔名集號 = 前面各正規季 `length` 加對到的集號、信心不是 low、剛播用兩天的窗口。地上波先行、`absolute_group`、`absolute_within_first_season`、重數推測（`air_date_run`、`published_in_run`）、`season_from_job` 一出現就不算。`services/first_batch.vouch` 沒改：本批與同伴兩處都叫 `vouch_first_batch`，系統確認自動走新規則。
- **季的集數**收成 `SeasonSnapshot.length`：`mapping._length` 與 `search._known_episodes` 是同一個式子，這張票要第三份，就搬到 domain、刪掉兩份舊的。
- **已知盲點**（寫進 brief §15 與模組開頭）：字幕組與 TMDB 的前幾季集數差一集（總集篇只有一邊算）時，換算仍落在寫明的季、晚一週仍在六週之內，會擔保差一集的。票說其餘條件不變，沒有收緊「剛播」的下緣；要收緊的話是另一張票。
- **變異驗證**：上緣改成九天、拿掉寫明季號、拿掉集數加總、拿掉白名單、季號不比對，各自有測試變紅。
- **code-review 未處理的發現**：沒有走 `services` 的整合測試證明累計編號的 Series 發出 `series_confirmed`（services 沒改，`tests/integration/test_first_batch.py` 的 fixture 是只寫集號的單季作品，要另造一份兩季、寫明季號的 feed）；夜櫻本身不在語料裡，只用手造的 TMDB 快照驗；「正片季 = `season_number > 0`」在 `mapping._regular`、`literal._first_season` 與這裡各寫一次；`_counted_from_first_season` 開頭與 `is_literal` 同形。
