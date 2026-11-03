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
- **協調者追加（2026-11-04）：線上輪**（主目錄的 `.env`；`first_batch_rule.py` 多一個依讀法分的計數）：
  - 語料：擔保 12、錯 0，其中累計編號 2（SPY×FAMILY S3 兩份）、錯 0。對抗輪：擔保 11、錯 0，累計編號 2、錯 0。
  - split-cour：第二輪從 01 重數擔保 0（必須是 0），第一輪剛播的擔保 2。沒有累計編號。
  - 真 RSS：128 筆擔保 113、不擔保 15；累計編號 0 筆（連讀成累計編號而沒擔保的也是 0）。這一段沒有標準答案，量不出擔保錯數。
  - 所以沒有一輪擔保錯 > 0，規則留著；但累計編號的證據只有語料那兩筆。
- **協調者追加：TMDB 前一季集數差一**（`TestCumulativeReadings` 兩條測試，真的解析器）：
  - 少記一集（26）：40 換算成 S02E14，比發佈晚一週播，播出日比對擋下；42 換算到沒有播出日的 S02E16，也不擔保。**安全。**
  - 多記一集（28）：40 → S02E12（真的是 S02E13），41 → S02E13，42 → S02E14，**每一集都擔保錯**，Series 被系統確認。測試固定成現況（`== ((2, 12, 12),)`），規則收緊時改成 `is None`。這種情況就算不看第一批，解析器本來也會照錯的集數自動入庫，第一批的 audit 是唯一一次讓人看到的機會。
- **便宜的守衛（沒改規則，給使用者決定）**：
  - **發佈時下一集已經播了就不擔保**：整份最後一集的下一集，TMDB 播出日不晚於發佈日加兩天（`RELEASE_TOLERANCE`）。多記一集時，對到那一集的「下一集」就是真的那一集，一定已經播了（最多早發兩天也算進去），所以擋得住每一筆；手上的資料就夠，不用新欄位。代價是慢發的字幕組改回等人。量法在 `scripts/experiments/next_aired_guard.py`（套在照字面的列上量代價，累計編號在語料只有兩筆、真 RSS 沒有）：語料 10 擋 1（Librarians S02E05，晚發）、對抗輪 9 擋 1、真 RSS 與 split-cour 115 擋 22。只套在累計編號上時，被擋的就是照現在一樣等人，SPY×FAMILY 兩筆不受影響。
  - 「同一批更後面的集號超過這一季的集數」擋不住：多記一集時換算往前，永遠不會超過；它只抓得到少記，而少記已經被播出日比對擋下。
  - 「前一季 TMDB 標示未完結」：快照的季沒有狀態欄，記錯的通常是早就播完的那一季，沒有訊號可用。
