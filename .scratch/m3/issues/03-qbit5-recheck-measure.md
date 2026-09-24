# 03 — 【研究】qBittorrent 5.x 停住的 torrent 做 `recheck` → `start`

**Status:** done

**Blocked by:** None — can start immediately

**讀:** plan §3.1（`missing_files` / `client_error` 的「重新校驗」那一列）、§8.1、§11.3 D 組第 5 條；brief §20.2、§20.7（qBittorrent 版本矩陣）

## 做什麼

M2 票 09c 的「重新校驗」對 qBittorrent 送 `recheck` + `start`，**只在 4.4 上量過**。§11.3 D 組把 5.x 延到「下一次有真的 5.x 時量」，但這個前提不成立：compose 預設就是 5.x，所以使用者按的正是沒量過的那一條路。

`mattpocock-skills:prototype` 的形狀：實驗腳本放 `scripts/experiments/`（plan §10：一次性但保留腳本，下一次換版本要重量），在一次性的 5.x 容器上實測：

- 停住（`stopped`）的 torrent 送 `recheck` 之後，狀態怎麼走？會不會自己開始？
- 接著送 `start` 之後，是否回到下載或做種，而且 Berth 的 poller 認得出來？
- 缺檔的 torrent（刪掉 complete 裡的一個檔）校驗完是什麼狀態？

結論寫回 brief §20.2（附量測方式與版本），plan §11.3 D 組那一條劃掉或改寫。**行為與 09c 的假設不同時**，在同一票修 `services` 那一段並補測試，不另開票；修補量超出一個 session 時停下來，改開一張票。

## 驗收

- [x] 腳本在 `scripts/experiments/`，可以重跑，README 或腳本開頭寫明怎麼跑
- [x] brief §20.2 有 5.x 的實測結果（版本號、三種情境各自的狀態序列）
- [x] plan §11.3 D 組第 5 條已處理
- [x] 若行為與假設不同：修正附紅 → 綠的測試；若相同：票的 Comments 寫明「照舊」
- [x] 一次性容器與 volume 已刪（貼過濾結果）

## Comments

- 2026-09-24：**行為與 09c 的假設不同，同一票修了**。5.2.3（當天的 `:latest` 也是它）上停住的 torrent
  recheck → start 校驗完又停住：資料齊的停在 `stoppedUP`，缺檔的停在 `stoppedDL`，Job 卡在「下載中」、
  不開 Issue。4.4.5 兩種順序都成立。`services/issues._restart` 改成 start → recheck，紅 → 綠的是
  `test_pipeline_issue_actions.py::TestRecheck::test_it_restarts_rechecks_and_the_poller_takes_it_from_there`
  （替身的 `rechecked` / `started` 合成一條依到達順序的 `restarts`）。八種情境的序列在 brief §20.2。
- 一次性容器與 volume 的過濾結果（三輪最後一輪之後，另有一輪重構後的冒煙）：
  `docker ps -a --filter name=berth-exp-recheck: []`、`docker volume ls --filter name=berth-exp-recheck: []`、
  `docker network ls --filter name=berth-exp-recheck: []`。
- code-review 未處理：新腳本的 `docker()` 是 experiments 目錄裡第三份近拷貝（`jellyfin_permissions.py`、
  `large_library.py`），只有這一份要 `stdin`。下一支再要時收進 `lib.py`。
