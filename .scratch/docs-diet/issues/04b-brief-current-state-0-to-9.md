# 04b — brief 去歷史（上）：§0–§9

**Status:** done

**Blocked by:** 04a

**讀:** `.scratch/docs-diet/spec.md`（〈共同規則〉〈改寫規則〉）；brief §0–§9（約 455 行 48 KB）；`docs/adr/` 的索引（brief §19）

## 為什麼

brief 現在混著現況與演變史，讀的人要自己拼出哪句還有效。這張改寫 §0–§9：定位、路徑模型、管線、解析、命名、資料模型、刪除與修復。

## 做什麼

照 spec〈改寫規則〉改寫 §0–§9。章節與小節號不變（§9.1、§6.5、§6.4 等被 `berth/` 引用數十次）。

## 驗收

- [x] 前後大小與歷史標記數貼 Comments；剩下的標記逐條有理由
- [x] 對照表貼 Comments，§0–§9 每個【決定】、規則、數值都對到新版位置或 ADR
- [x] 收尾 code-review 的 Spec 軸照對照表逐節比對舊版，結果貼 Comments
- [x] 發現的矛盾列在 Comments 問使用者，沒有自己挑
- [x] 全部檢查與 test 綠；progress.md 記一列 session；commit；不 push

## Comments

### 前後量測（開工 commit `a29281e1`，§0–§9 = 第 15–469 行）

| | 行數 | 位元組 | 歷史標記（票規定的 regex） |
| --- | --- | --- | --- |
| 舊版 | 455 | 54,501 | 43 |
| 新版 | 549 | 52,364 | 0 |

行數增加是因為長段落拆成清單。剩下的標記 0 條；保留的 `M4`、`M5` 是現行里程碑名（§1.2、§5.2、§6.10 指向後面章節的範圍），`docs/research/profile-effect.md` §4（§6.4）與 `domain/spend.py`、`services/resolver.py`、`deletion.Placed.holds`（程式碼指標）是唯一證據指標，留。章節與小節標題的號碼與【決定】標記逐行 diff 相同（只拿掉標題上的「，2026-09-24 改」「，取代原…」）。

### 對照表（舊版 → 新版，同一節號）

| 節 | 舊版的決定 / 規則 / 數值 | 新版 |
| --- | --- | --- |
| §1.2 | Prowlarr 唯一、Jackett / 單站 Torznab 不支援；2026-10-06 改的說明 | 同列，改成現況一句；歷史在 ADR-0001 |
| §1.2 | M4–M7 排程（2026-09-24 重排） | 「重排」二字刪，內容留 |
| §3 | 2026-10-06 改的引言塊；Prowlarr 列的「M4 票 37 起」 | 引言塊刪；列內改成「沒有 Torznab 端點」 |
| §4.1 | incomplete/complete 根固定、無設定；`downloadPath` 不寫全域 `temp_path`；slug 規則與既有 Route 保留舊 slug；category 預設名 | 同，去票號與「原本寫」 |
| §4.3 | 預選 Berth 路徑；只有一個路徑也不自動選；套件內不用選；其他路徑唯讀；多 Route；slug 與目標不可改、刪除規則 | 同，去票號與「推翻原本的自動選定」 |
| §4.4 | 實際 `link()` 驗證；探針 torrent、ValidatePath、autoTMM、自己的未完成目錄；不退回複製；`/data` 固定；不做 remote path mapping；使用者文件 | 同，拆成清單；刪「原本寫…」 |
| §4.5 | 資料夾名凍結時機兩種（手動送單、RSS 綁定）；TMDB 改名不自動改；字元與 200 bytes | 同，拆成清單 |
| §5.1–5.3 | 狀態機、pre-plan、completed 判定、importing、反查 Jellyfin；事件清單；`jellyfin_item_resolved` 一筆一行、只寫一次；不變量 | 同；刪「照程式碼更正」與票號 |
| §6.1–6.3 | 輸入、分類表、ReleaseInfo 欄位、不解析編碼、CJK 詞典兩段式、對齊 AutoBangumi | 同；刪「M4 票 91 拿掉」 |
| §6.4 | 5 步；絕對編號兩條降 low 的條件（集號 ≤ 第一季集數；播出日不符）、虛擬季（發佈前六週、至多 medium）、split-cour 陷阱、批次一致性、同路徑衝突進 review | 同；拆成清單；刪日期與票號 |
| §6.5 | 三級信心定義、high+medium 自動入庫、audit、low 進 review、benchmark 分報 | 同；刪「owner 決定」 |
| §6.6–6.7 | 多集、多季（兩個季號寫法、`season_end`、不補季號）、系列合集、CD1/CD2；字幕匹配 4 步與語言後綴、`.default` 位置與不產生的原因 | 同；刪票號 |
| §6.8–6.9 | Tag 順序與詞彙表；benchmark 四點 | 同；刪「owner 選英文 token」 |
| §6.10 | 三層漏斗、規則知道沒把握 → AI 任務、有把握卻錯靠程式檢查（播出日、片長、每日檢查、Jellyfin 回驗抓不到）、輸入輸出、執行與影子模式、修正回流、快取鍵、記錄表、**無月預算**改防護、兩種花費提醒（每日值、14 天中位數 5 倍、少於 3 天不比）、未知費用、提醒位置 | 同；刪日期、刪除線、協調者與使用者選定的註；ADR-0008、0016 連結留 |
| §7.1–7.2 | 劇集與電影範例路徑；資料夾加年份與 tmdbid；集標題省略；Season 兩位數；電影多版本需完整 tmdbid、排序規則 | 同；刪「與原提案的差異」「範例是錯的已更正」 |
| §7.3–7.4 | extras；Unmatched 不入庫、三種動作、兩個理由 | 同；刪「取代原 unmatch 資料夾」，兩條理由前面補一句不放 `unmatch/` |
| §7.5 | Title 規則、凍結；顯示跟 UI 語言、海報、媒體庫牆例外 | 同；刪日期與「拆票時決定」 |
| §7.6–7.9 | Specials 三種；多版本並存、Jellyfin 12、版本標籤、命名保證；duplicate、序號標籤、規劃時判斷、同起始集不同結束集；帳本必要性 | 同；刪日期與票號 |
| §8 | 資料模型十一條 | 同；刪「M4 票 95」 |
| §9.1 | 14 種 Issue 表；四組來源；ledger.status 與 Issue 關係；認領類三顆；管線三種動作；忽略有效期（健康檢查兩種、mismatch、unknown_torrent）；刪除前再確認；job_without_files 兩個例外 | 同；原本分散三段的拍板日期與票號刪掉，改依主題分組 |
| §9.2 | 四旗標與順序、預設全不勾、空間估算 stat、對話框位置、路徑守衛、只拆 Berth 放的（`Placed.holds`）、409 `moved_on`、`job_removed` | 同；刪日期與票號 |
| §9.3–9.5 | 重新入庫兩個入口、Import Source 是磁碟上那包、冪等鍵、`rebuild-ledger` 不猜；Rematch；Jellyfin 端刪除 | 同 |

### code-review（Spec 軸，opus，逐節比對 `git show a29281e1:docs/design-brief.md`）

結論：沒有丟決定。指出 4 處，已修：§4.1 舊 slug 可能帶空白（補回）、§7.8 同起始集與 `duplicate` 的連結、「保留兩者」括注位置、§6.10 引入時機語意；§4.5 的「不拖到入庫」理由改回兩種時機共用。

### 發現的矛盾（舊版就有，沒有自己挑，請使用者決定）

1. Issue 種類：brief §9.1 與 plan §2.4 說 14 種，`berth/domain/enums.py:240` 的 `IssueType` 有 19 種（多出每日巡檢的五種，如 `first_batch_stuck`、`feed_poll_failing`）。表與四組來源沒列。
2. `unknown_torrent` 表上歸對帳，實際由 `qbit_poller` 寫（§9.1 後段也說 poller 每 5 秒寫）。
3. `ledger.status` 在 §8 少列 `unlinked`，§9.1、§9.2、plan 有。
4. 資料夾名凍結：§8 只寫「送單那一刻」；plan:125 說 RSS Rule 建立時凍結且有人在場，§4.5 說 RSS 綁定時不一定有人在場。
5. §5.1「高信心 Plan 自動進 importing」對 §6.5「high 與 medium 都自動入庫」。
6. §6.10「超出預算時退回」對同節「沒有月預算上限」。
7. §6.5「low 進 review，並在啟用 AI 時觸發 §6.10」對 §6.10「開 AI 任務，而不是直接進審核」。
8. §6.5 說絕對編號要集號超過第一季才是 medium，§6.4 虛擬季允許集號 ≤ 第一季時至多 medium，§6.5 未提這個例外。

### 驗證

`uv run pre-commit run --all-files` 全過；`pytest tests/unit` 2180 passed。
