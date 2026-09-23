# 09c — 管線三種 Issue 的動作 + TVDB / 磁碟門檻變成 Issue

**Status:** done

**Blocked by:** 09（十一種的動作表、`ACTION_DELETES`、Issue 列的確認總表）

**讀:** brief §9.1（`missing_files` / `client_error` / `client_removed` 三列）、§20.2（qBittorrent
Web API）、§16.4（TVDB 警告）；plan §3.1（`missing_files` / `client_error` / `client_removed` 的出邊）、
§3.2（`health_checker` 的磁碟空間那一條）

## 為什麼有這一張

2026-09-23 票 09 開工時使用者拍板拆出來：票 09 的份量是一般票的兩倍，而這一半有兩件票 09 不需要的
前置——qBittorrent adapter 要新增端點（brief §20.2 沒寫，v4 與 v5 有差異要先查），以及兩種新的 Issue
型別（十一種 → 十三種，plan §2.4 / brief §9.1 / CONTEXT.md 都要改）。

## 做什麼

**管線三種的 resolve 動作**（brief §9.1 那一欄）。票 05 起它們已經在寫 `issues` 表，現在只按得了「忽略」：

- `missing_files`：重新 recheck / 承認遺失
- `client_error`：重試 / 忽略
- `client_removed`：重新送單 / 承認移除

先查 qBittorrent 的 `torrents/recheck`、`torrents/start`（v5）/ `torrents/resume`（v4）在 4.4.5 與
5.2.3 的差異，結論補進 brief §20.2 並附來源（專案 CLAUDE.md 的「事實與查證」）。按下去之後 Job 回到
哪個狀態、poller 怎麼接手，照 plan §3.1 的轉換表；表上沒有的出邊要先補進 plan §3.1。

**M0 帶過來的兩條變成 Issue**（使用者 2026-09-23 拍板：由 `health_checker` 偵測，不由對帳）：

- **媒體庫掛了 TVDB 插件**：現在只是 Route 設定頁與精靈上的一行字（`uses_tvdb`）。
- **磁碟空間門檻**：現在只在 Route 的 `hardlink` 纜繩上以 `free=` 顯示實測值，沒有門檻判定。
  **門檻值寫在設定裡而不是常數**；先看成熟產品怎麼做（Sonarr 的 Minimum Free Space）再定形狀。

`health_checker` 每 5 分鐘本來就在量這兩件事；條件解除時那一件自動收掉（`resolved_by = system`），
因為它們沒有 Berth 按得了的修法——使用者在 Jellyfin 或磁碟上修好之後，Issue 不該還開著。
新型別要回答 `SUBJECT_OF`、`ISSUE_ACTIONS`、`ACTION_DELETES`（`tests/unit/test_issue_types.py` 守著）。

## 驗收

- [x] 三種管線 Issue 的每一顆 resolve 動作按下去真的修好（各一個整合測試，對 qBittorrent 替身）
- [x] qBittorrent 新端點的版本差異寫進 brief §20.2，附來源；adapter 契約測試對錄下來的回應
- [x] TVDB 插件警告與磁碟空間門檻是 Issue 而不是健康頁上的一行字；門檻值寫在設定裡而不是常數
- [x] 兩種新型別的條件解除時 Issue 自動收掉（整合測試）
- [x] 十三種型別在 plan §2.4、brief §9.1、CONTEXT.md 的 Issue 詞條一致
- [x] 問不到 qBittorrent / Jellyfin 時按鈕說得出為什麼，Issue 留著 `open`
- [x] lint、type、test 綠燈

## Comments

- 2026-09-23 code-review 未處理的發現：
  - Spec：Job 被別的路徑推走之後（Job 頁上重試成功、另一個分頁按過），那件管線 Issue 會停在 `open`、
    按鈕歸零、只剩「忽略」。票只要求健康檢查那兩種自動收；要不要讓 poller 在 Job 離開壞掉狀態時一起收掉，
    留給之後有 repro 的時候決定。
  - Standards（判斷題）：`IssueRow.tsx` 對 `issue.type` 的分支散在四處（標題三元、`PATH_TERM`、`Measured`、
    `CONFIRM`）；`services/jobs._reachable` 與 `services/issues._restart` 的「sign_in → 呼叫 → aclose」形狀重複。
    都只有兩三處，沒有收。
  - 沒有實測到的：5.x 上對**停住的** torrent recheck → start 會不會被 `FilesChecked` 再停下來（實驗四包都是
    `missingFiles` 而不是停住的）。`client_error` 的重試只送 start，不受影響。
