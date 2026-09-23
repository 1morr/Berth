# 09 — reconciler 其餘十種 + 重新反查

**Status:** done

**Blocked by:** 05（`issues` 表、對帳的一輪與冪等鍵）

**讀:** plan §3.2（`reconciler` 與 `jellyfin_resolver` 兩列）、§2.4（十一種型別與各自的 `subject`）；brief §9.1（那張表逐列）、§20.1、§20.9

## 做什麼

票 05 只做了 `library_link_missing`。這一票把 brief §9.1 那張表的其餘十種補齊——同一支命令的
十個分支，四方（帳本 / qBittorrent / complete / library）各走一次。

**對帳的六種**：`source_missing`、`inode_mismatch`、`orphan_complete`、`unknown_torrent`、
`unmanaged_library_file`、`job_without_files`。每一種的判定與**預設建議動作**照 brief §9.1 那一欄，
不自己發明。`unmanaged_library_file` **只列出、永不自動刪**。

**管線的四種**（`missing_files` / `client_error` / `client_removed` / `jellyfin_item_unresolved`）
票 05 已經在寫表了，這一票補上它們的 resolve 動作。

**重新反查**：`jellyfin_item_unresolved` 的「重新反查 / 重新掃描媒體庫」要真的按得動。順手把
兩件跟反查有關的做掉：

- **`jellyfin_series_id` 回填**：票 13 之前反查完的劇集，卡片一直說「還在掃描」且不會自己更新。
- **Jellyfin 12 合併之後 `jellyfin_item_id` 可能不再是主條目**（brief §20.9）：反查到的 item
  被合併走了，帳本那一欄要跟著更新。

**M0 帶過來的兩條，這一票變成 Issue**（它們現在只是健康頁上的一行字，按不了動作）：

- 媒體庫掛了 TVDB 插件的警告
- 磁碟空間門檻（§3.2：目前只在 Route 的 `hardlink` 纜繩上以 `free=` 顯示實測值，沒有門檻判定。
  門檻要變成一個 Issue 才有用）

## 驗收

- [x] brief §9.1 那張表的**十一種**都偵測得出來，每一種有一個整合測試造出那個破壞並斷言 Issue
      的 `type` 與 `subject`
- [x] 每一種的 resolve 動作都是 brief §9.1 那一欄寫的那幾個，按下去真的修好（各一個整合測試）
      ——**範圍再拆之後的那幾顆**：認領類三顆在票 10、管線三種在票 09c（見 Comments）
- [x] `unmanaged_library_file` 沒有任何自動刪除的路徑（測試斷言：resolve 的動作集合裡沒有「刪除」）
- [x] 每一種的冪等鍵照 §2.4 取 `subject`，同一個破壞連跑兩輪只有一筆 `open`
- [x] `jellyfin_series_id` 回填之後，原本說「還在掃描」的劇集卡片會自己更新（測試斷言那一欄
      從空變成有值，且畫面跟著變）
- [x] Jellyfin 12 合併之後主條目換掉時，帳本的 `jellyfin_item_id` 跟著更新（整合測試以替身
      Jellyfin 造出合併）
- [ ] ~~TVDB 插件警告與磁碟空間門檻是 Issue 而不是健康頁上的一行字；門檻值寫在設定裡而不是常數~~
      → **移到票 09c**（2026-09-23 使用者拍板）
- [x] 四方任一方問不到時跳過那一方並說出來（票 05 立的規則，這一票的十種都遵守）
- [x] lint、type、test 綠燈

## Comments

- **範圍再拆**（2026-09-23 開工時使用者拍板，三題都照建議）：認領類三顆（`orphan_complete` 重新入庫、
  `unknown_torrent` 認領、`unmanaged_library_file` 認領進帳本）移到票 10——它們用的就是目錄版 `reimport`
  與 `rebuild-ledger` 的反查；管線三種（`missing_files` / `client_error` / `client_removed`）的動作與
  TVDB / 磁碟門檻兩種 Issue 移到新開的票 09c，TVDB / 磁碟由 `health_checker` 偵測。這幾種這一票只按得了
  「忽略」（`ISSUE_ACTIONS` 是空 tuple）；`test_issue_types.py::test_what_each_type_offers_this_round`
  是刻意會過期的那一條。
- **「畫面跟著變」驗到 API 那一層**：`read_wall` 的那一張卡從 `searching` 變成 `found`、連結是 Series id
  （`test_reconcile_checks.py::TestTheSeriesIdIsFilledIn`）。前端照 `presence` 畫，沒有另外的前端測試。
- **對帳第五方 Jellyfin、`source_missing` 的帳本語意、`job_without_files` 的兩個例外、「有主」的三個來源**：
  理由都在 progress.md「偏差與決定」與 plan / brief 的同步段落。

### `/code-review` 的發現

兩軸各跑一次。**修掉的五條**：

1. **dispatch 的 `else` 會靜靜跑 `_rescan`**（Standards）：加一顆新的 `IssueAction` 進 `ISSUE_ACTIONS` 而沒
   接上實作時會跑到別顆。改成 `elif RESCAN` + `assert_never`，拿掉一支分支 mypy 紅（實跑確認）。
2. **「無主 torrent」判準寫了兩份**（Standards）：poller 與對帳各寫一次 `managed` + 查 Job。收成
   `services/qbittorrent.unknown_torrents`，內容也是同一份 `unknown_torrent_detail`。
3. **plan §3.1 缺 `imported → completed`**（Spec）：「重新規劃」開了一條表上沒有的出邊。已補。
4. **`job_without_files` 的兩個例外只在程式註解裡**（Spec）：brief §9.1 已補。
5. **走訪到一半讀不到會讓整輪垮掉**（Spec）：complete 的 Route 子目錄在 `is_dir()` 之後讀不到、媒體庫
   `rglob` 途中讀不到。前者整方標成問不到（`orphan_complete` 的下一步是刪除，少看一條就少認一個主），
   後者那一條 Route 跳過並說出原文。兩條測試紅 → 綠。

**看過但沒改的**：

- **forget 例外會漏報**（Spec）：「那一筆有任何一件 resolved 且按的是 forget」就永久不報
  `job_without_files`，所以很久以前 forget 過一個檔案、之後帳本整個消失的那一筆抓不到。精確的判準要數
  「forget 掉的帳本列」是否涵蓋整份 Plan，這一票沒有 repro 說值得；記著。
- **`detail_json.action` 一鍵兩義**（Spec）：偵測時是那一列帳本的 `PlanAction`（`import`），resolve 時被
  覆寫成按下的 `IssueAction`。票 05 就是這樣，forget 例外靠的是覆寫之後的那個值。改鍵名會動到票 05 的
  前端與測試，另開。
- **動帳本的按鈕沒有拿鎖**（Spec）：`_replace_with_link` 在 stat 與 `replace_link` 之間有一個 `await`，
  那一瞬間 audit 撤銷可能拆掉目標。票 05 的重新鏈接也是同一個形狀；單程序 asyncio 下窗口很小，沒有 repro。
- **`RELOOK` 的命名**（Standards）：CONTEXT.md 的 Resolve 詞條避開 `lookup`；識別符往 `resolve` 靠又會撞上
  `resolve_issue`。畫面文案是「重新反查」，合規。
- `_relook` 與 `_rescan` 尾部兩行重複（Standards，判斷題，不動）。
