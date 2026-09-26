# 02 — Jellyfin 回驗：「還在認」不是不一致；版本重排只推同一集

**Status:** ready-for-agent

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

- [ ] 試跑那份「還在認」的 item 不開 Issue，之後讀到一致時也沒有收掉又重開（整合測試，雙向：真的認成別的季集仍開）
- [ ] 同一季入庫第 N 集時，只有同一集的其他版本被重排反查（測試，雙向）
- [ ] 一筆 Job 的「全部找到」事件只寫一次（測試）
- [ ] 上面兩個被改掉意義的既有測試改寫而不是刪掉；plan §2.4、§3.1 與 brief §5.2 同步
- [ ] 真服務 e2e 的 `test_jellyfin_reading_an_episode_differently_opens_an_issue` 仍綠
- [ ] lint、type、test 綠燈

## Comments
