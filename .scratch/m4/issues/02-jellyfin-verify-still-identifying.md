# 02 — Jellyfin 回驗：「還在認」不是不一致；版本重排只推同一集

**Status:** done

**Blocked by:** None — can start immediately

**讀:** plan §11.5「M4 之前先做的修補」、§2.4（`issues` 的冪等與系統自收）、§8.2（Jellyfin adapter）；brief §20.1（Episode 的作品 id 看 Series）；`.scratch/m3/issues/17-jellyfin-verify.md`、`.scratch/m1/issues/14b-jellyfin-12.md`（版本名）

## 為什麼

2026-09-26 試跑：BLACK TORCH 一季 12 集入庫後開出 6 件 `jellyfin_item_mismatch`，Jellyfin 那一側是
`season: null, episode_start: null, tmdb: ""`、`name` 是作品名——Jellyfin 還沒認完剛掃進來的檔案。
幾分鐘後同一個 item 讀回來是 `Episode S01E10`，Issue 被收掉，下一輪又重開。事件表裡同一筆 Job 的
`jellyfin_item_resolved` 寫了 5–7 筆。M4 的通知「Issue 新增」建在這上面會一天推好幾次假警報。

讀程式碼的成因：

- `resolver.disagreement`（`berth/services/resolver.py:205-240`）把 Jellyfin 的季、集是 `None` 算不一致
  （docstring 明寫「那正是沒被認成正片的樣子」），Series 沒有 `ProviderIds.Tmdb`（`:389` 取 `""`）也算。
  找到 item 當下就 `resolve_after = None`（`:137`），之後不再反查。這個行為被
  `tests/unit/test_jellyfin_disagreement.py:44`、`tests/integration/test_jellyfin_verify.py:179` 釘著。
- `importer.restate_versions`（`berth/services/importer.py:394-419`）的本意是「同一集的其他版本」重排
  （Jellyfin 12 的版本名會因為多一個版本而改），實作是**同一個資料夾**的所有正片——一季每入庫一集，
  前面每一集都重排一次反查。每次找到都在 `_announce`（`resolver.py:~447`）寫一筆事件，payload 的
  `count` 每輪不同，`record_event` 一分鐘的去重擋不住；48 集那一部約 1100 次反查，而且每次都在新檔
  觸發 Jellyfin 重掃的時候比，正好撞上「還在認」。

## 做什麼

1. **先 repro**：用試跑記下的那一份 item（Name = 作品名、季集 `None`、Series 無 Tmdb）寫紅燈。
2. 「還沒認出」與「認得不一樣」分開：季、集是 `None` 或 Series 的 Tmdb 是空的時候不寫 verdict，照「還沒找到」
   的節奏重排反查；六次都還認不出才落到既有的放棄路徑（`jellyfin_item_unresolved` 或新理由，擇一並寫進 plan §2.4）。
   **先查 Jellyfin 12 認完一個 item 要多久**（試跑的時間線在 progress.md），決定重排間隔夠不夠。
3. `restate_versions` 縮到**同一集**（同 media、同季、集號範圍重疊）；補一條測試守住範圍。
4. `jellyfin_item_resolved` 一筆 Job 只在「它的正片全部找到」時寫一次（M4 的「可以看了」要的就是這個訊號，
   事件名與 payload 在這張票定，寫進 plan §3.1 事件表與 brief §5.2）。

## 驗收

- [x] 試跑那份「還在認」的 item 不開 Issue，之後讀到一致時也沒有收掉又重開（整合測試，雙向：真的認成別的季集仍開）
- [x] 同一季入庫第 N 集時，只有同一集的其他版本被重排反查（測試，雙向）
- [x] 一筆 Job 的「全部找到」事件只寫一次（測試）
- [x] 上面兩個被改掉意義的既有測試改寫而不是刪掉；plan §2.4、§3.1 與 brief §5.2 同步
- [x] 真服務 e2e 的 `test_jellyfin_reading_an_episode_differently_opens_an_issue` 仍綠
- [x] lint、type、test 綠燈

## Comments

2026-09-26 實作：

- **「還在認」的定義**（`resolver.still_identifying`）：Episode 讀不出季號或集號，或帳本有作品而 Jellyfin 那一邊的作品沒有 TMDB id（Series 查不到也算）。電影同一條：自己的 Tmdb 是空的就是還在認（票面只講了 Episode 與 Series，行為一致所以一起）。
- **六次都認不出落到 `jellyfin_item_mismatch`**，不是票面列的 `jellyfin_item_unresolved` 或新理由：Jellyfin 列出了這個檔案，說「沒列出」是錯的；而 mismatch 的 `detail_json` 並排兩邊，正說得出它讀成空的，畫面與「重新反查」都現成。plan §2.4、progress.md 偏差記了。
- **重排間隔**：試跑量到的是上界約 12 分鐘（下一次反查碰巧讀到的時間）。code-review 指出第 3 次之後要等一小時，真服務 e2e 等第一集只等 1200 秒——還在認的改成最晚 10 分鐘再看（同 `SCAN_SETTLE`），六次約 43 分鐘問完。季集讀自檔名、作品讀自 `[tmdbid-…]`，都不必連網。事實補進 brief §20.1。
- **還在認的不提醒 Jellyfin**（票面沒寫）：它已經列出檔案，再請它掃只會從頭認起。
- **對帳那一方遇到還在認的：照樣換新 item / Series id，但不比**（不開不收）。一開始連換新也跳過，結果票 13 的 Series id 補欄與合併後換主條目的測試紅了——那兩件與認沒認完無關。
- **既有測試的 fixture**：`test_reconcile_checks.scanned` 的 Series 預設沒有 Tmdb（票 13 要牆只靠 Series id 認），走反查的兩處（`test_issue_repairs` 的重新反查 / 重新掃描、`test_reimport`）改傳 `SPY`。
- **`jellyfin_item_resolved` 的「找到」**：帳本那一列有 item、不再排反查。認成別的、六次認不出而開了 mismatch 的算（Jellyfin 裡打得開）；放棄的不算。plan §3.1 寫明。

真服務 e2e：https://github.com/1morr/Berth/actions/runs/36241325069（`0b7ed1a`，22 passed，17 分 56 秒）。

code-review（Standards / Spec 兩軸）已修：brief §20.1 補事實、條件式裡的副作用寫明（ruff SIM102 不讓拆成巢狀 if，改用註解說 `_reschedule` 會排下一次）、`_Lookup.identifying` / `_works` 改名 `still_identifying` / `_tmdb_ids`、補「找到之後被排回反查、撞上重掃」的整合測試、還在認最晚 10 分鐘。未處理：

- **`_all_found` 不看 `LedgerEntry.status`**：同一筆 Job 有一列在反查前就被拆掉鏈接（`unlinked`）又永遠沒有 item 時，這筆永遠不寫「全部找到」。刪除範圍拆鏈接是整筆 Job 一起，實際造不出來；有 repro 再改。
- **`ResolveOutcome.retried` 現在含還在認的那幾列**，六次認不出而比了的那一列算 `resolved`（它找到了）。只進 log。
- `_same_episode` 的「集號範圍」寫法（`episode_end or episode_start`）在 `planner` / `plan` / `inventory` 還有三處，沒有抽出來。
