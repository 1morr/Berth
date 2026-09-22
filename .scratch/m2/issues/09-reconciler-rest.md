# 09 — reconciler 其餘十種 + 重新反查

**Status:** ready-for-agent

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

- [ ] brief §9.1 那張表的**十一種**都偵測得出來，每一種有一個整合測試造出那個破壞並斷言 Issue
      的 `type` 與 `subject`
- [ ] 每一種的 resolve 動作都是 brief §9.1 那一欄寫的那幾個，按下去真的修好（各一個整合測試）
- [ ] `unmanaged_library_file` 沒有任何自動刪除的路徑（測試斷言：resolve 的動作集合裡沒有「刪除」）
- [ ] 每一種的冪等鍵照 §2.4 取 `subject`，同一個破壞連跑兩輪只有一筆 `open`
- [ ] `jellyfin_series_id` 回填之後，原本說「還在掃描」的劇集卡片會自己更新（測試斷言那一欄
      從空變成有值，且畫面跟著變）
- [ ] Jellyfin 12 合併之後主條目換掉時，帳本的 `jellyfin_item_id` 跟著更新（整合測試以替身
      Jellyfin 造出合併）
- [ ] TVDB 插件警告與磁碟空間門檻是 Issue 而不是健康頁上的一行字；門檻值寫在設定裡而不是常數
- [ ] 四方任一方問不到時跳過那一方並說出來（票 05 立的規則，這一票的十種都遵守）
- [ ] lint、type、test 綠燈

## Comments
