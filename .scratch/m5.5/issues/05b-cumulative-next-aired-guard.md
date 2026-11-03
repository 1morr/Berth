# 05b — 累計編號的第一批：下一集已播就不擔保

**Status:** ready-for-agent

**Blocked by:** 04b（同一塊：`parser/first_batch.py`、`parser/airing.py`）

**讀:** 票 05 的 Comments（已知盲點、候選守衛、`next_aired_guard.py` 的數字）；brief §15（第一批、已知盲點）；`parser/first_batch.py` 開頭的條件說明；`scripts/experiments/first_batch_rule.py`、`scripts/experiments/next_aired_guard.py`；`docs/development/experiments.md`

## 為什麼

協調者插的追加票（使用者 2026-11-04 定）。票 05 讓累計編號（夜櫻 40 → S2E13）的第一批由系統確認，閘門擔保錯 0，但證據只有語料兩筆（SPY×FAMILY S3）。05 證實了一個盲點：**TMDB 把前一季多記一集時**，換算往前差一集，加總照樣對得上、播出日比對也不擋，整批擔保錯，Series 被系統確認，之後的集數不再等人看（測試 `test_tmdb_counting_one_episode_more_before_is_a_known_blind_spot` 固定了現況）。

05 量過的守衛「發佈時對到那一集的下一集已經播了就不擔保」擋得住這種情況：多記一集時，下一集就是真正的那一集，一定已經播了。使用者定：**只套在累計編號這條讀法上**，照字面的讀法不受影響（全部套用會讓發得慢的字幕組多擋 22/115 筆）。

## 做什麼

1. 第一批擔保累計編號（`absolute_cumulative`）時多一個條件：發佈時，對到那一集的**下一集**還沒播（TMDB 播出日晚於發佈日；沒有下一集或下一集沒有播出日時，照「還沒播」算，記在 Comments 為什麼）。其他讀法（照字面、`released_ahead_of_airing`）不加這條。
2. `test_tmdb_counting_one_episode_more_before_is_a_known_blind_spot` 改成「不擔保」，名稱跟著改。
3. 擋下時不另開理由：回到現在的「等人確認」即可。若需要讓人看懂為什麼沒自動確認，沿用現有的說明方式，照 `codebase-design` 判斷，記在 Comments。
4. 閘門重跑：`first_batch_rule.py` 的語料、對抗輪與 `--online`（主目錄 `.env` 的 `TMDB_API_KEY`，不印值）擔保錯都要 0；SPY×FAMILY S3 那兩筆仍擔保。貼前後數字。
5. 文件：brief §15 的已知盲點改成「已由守衛擋下」、`parser/first_batch.py` 開頭的條件說明。

## 驗收

- [ ] TMDB 前一季多記一集時，累計編號的那批不擔保；少記一集仍由播出日比對擋（測試）
- [ ] 照字面的讀法不受這條影響（測試）
- [ ] 閘門各輪擔保錯 0，SPY×FAMILY S3 兩筆仍擔保（數字貼在 Comments）
- [ ] `berth bench` 的 `auto_wrong` 不升（貼數字）
- [ ] 全部檢查、pytest 綠；brief §15 已改；progress.md 已更新
