# 05b — 累計編號的第一批：下一集已播就不擔保

**Status:** done

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

- [x] TMDB 前一季多記一集時，累計編號的那批不擔保；少記一集仍由播出日比對擋（測試）
- [x] 照字面的讀法不受這條影響（測試）
- [x] 閘門各輪擔保錯 0，SPY×FAMILY S3 兩筆仍擔保（數字貼在 Comments）
- [x] `berth bench` 的 `auto_wrong` 不升（貼數字）
- [x] 全部檢查、pytest 綠；brief §15 已改；progress.md 已更新

## Comments

- **條件**（`parser/first_batch._next_aired`，模組開頭第 7 條）：一份裡有累計編號的列時，整份最後一集的下一集，TMDB 播出日要**晚於發佈日加 `RELEASE_TOLERANCE`（兩天）**。票面寫「晚於發佈日」，這裡照票 05 量過的那一個守衛（`next_aired_guard.py`）加了兩天：累計編號的「剛播」上緣也是兩天，多記一集而字幕組早發兩天以內時，真的那一集還沒播，不加寬限就擋不下。閘門數字就是用這個定義量的。
- **只看整份最後一集**（與實驗相同）：一份多集時，前幾集的下一集就在這一份裡，逐列看會自己擋自己。「最後一集」取季號最大、再取結束集最大的那一列（code-review 補：直接 `max` 會取到起點最大的列）。兩條測試守。
- **沒有下一集、下一集沒有播出日算還沒播**：第一批最常見的就是最新一集，TMDB 上它往往是最後一集或下一集還沒排日期；擋下它們會讓累計編號的第一批幾乎全回等人。多記一集時真的那一集已經播了，TMDB 通常有它的播出日；沒有的話這一條擋不下，寫在模組開頭。
- **擋下時不另記理由**（照 `codebase-design` 判斷）：`vouch_first_batch` 的介面是「擔保了哪幾集 / `None`」，加理由要讓 parser 回一個新型別、services 多一條時間線事件，只為一個罕見的邊角。審核頁與作品頁的「在問什麼」已經對這一批說「絕對編號換算」（`services/first_batch.basis_of` 看 `absolute_cumulative` 回 `FirstBatchBasis.ABSOLUTE`），人看得出要核對什麼。
- **閘門**（`first_batch_rule.py --online`，主目錄 `.env`；前 = `f16c1d23`、後 = 本票，兩次數字完全相同）：
  - 語料：擔保 12（照字面 10、累計編號 2）、擔保錯 0 → 0。SPY×FAMILY S3 ANi（S03E13）與 DYNAMIS（S03E10）仍擔保。
  - 對抗輪：擔保 11（累計編號 2）、擔保錯 0 → 0。
  - split-cour：第二輪從 01 重數擔保 0 → 0，第一輪剛播 2 → 2。
  - 真 RSS：128 筆擔保 113、不擔保 15，前後相同；沒有累計編號。
  - `next_aired_guard.py`（離線兩輪）：累計編號「會擋」0，照字面 1（Librarians S02E05，就是不套在照字面上省下的那一筆）。腳本改成直接呼叫 parser 那一支，不再留一份副本。
- **`berth bench`**：`auto_wrong` 0 → 0（40 份、904 檔，high 0/112、medium 0/143 錯）。
- **變異驗證**：拿掉守衛、套到照字面、拿掉兩天寬限、沒有播出日當已播、沒有下一集當已播、直接 `max`、只看第一列，各自有測試變紅。
- **code-review 未處理的發現**：`_reading` 回 `Literal["literal", "cumulative"]`，而 `_just_aired` 收 `literal: bool`、`scripts/experiments/first_batch_rule.py` 的 `_reading` 也回同樣兩個字串（判定依據不同）——同一個概念三種寫法，沒有收成 enum（只在 parser 內部用，現在只有一個呼叫端在問「是不是累計編號」）。一份裡混了照字面與累計編號的列時，這一條也套到照字面那幾列；實務上一份 torrent 不會混兩種讀法，沒另外處理。
