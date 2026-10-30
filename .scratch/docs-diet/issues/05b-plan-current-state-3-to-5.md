# 05b — plan 去歷史：§3–§5（狀態機、解析器、命名引擎）

**Status:** done

**Blocked by:** 02, 04a

**讀:** `.scratch/docs-diet/spec.md`（〈共同規則〉〈改寫規則〉）；plan §3–§5（約 230 行 72 KB）；`docs/adr/` 的索引（brief §19）；改寫時遇到引用 brief 的地方才讀那一節

## 為什麼

plan 每行平均 330 bytes，117 處日期、1,007 處「票 NN」、12 處「推翻」混在規格裡，讀的人要自己拼出現況。plan 太大，按章節拆成 05a–05e，可以並行，後做的先 rebase。

## 做什麼

照 spec〈改寫規則〉改寫 plan §3–§5。章節與小節號不變（§3.1、§3.2 被 `berth/` 引用 130–140 次）。解析器規則若與 `berth bench` 的 fixture 說法不同，照程式與 fixture 寫，列在 Comments。

## 驗收

- [x] 前後大小與歷史標記數貼 Comments；剩下的標記逐條有理由
- [x] 對照表貼 Comments，§3–§5 每個決定、規則、欄位、端點、數值都對到新版位置或 ADR
- [x] 收尾 code-review 的 Spec 軸照對照表逐節比對舊版，結果貼 Comments
- [x] 發現 plan 與 brief 的矛盾列在 Comments 問使用者，沒有自己挑
- [x] 全部檢查與 test 綠；progress.md 記一列 session；commit；不 push

## Comments

開工 commit：`8fa5d3e4`。

### 前後

| | 開工 | 收尾 |
| --- | --- | --- |
| §3–§5 大小 | 75,586 bytes、230 行 | 72,798 bytes、455 行（長表格列與長段落拆成清單） |
| 歷史標記（regex） | 79 | 1 |

剩下的一條：§4.4 絕對編號換算裡的 `2015-05-24`，是 `150524` 讀法的範例值，不是日期標記。另留 `nyaa 1957100`（Re:Zero 反例的唯一證據指標）、`2022 年的 Spy x Family`／千年血戰篇例句（例子成立的條件）。大小沒降多少：§3.2 把八個迴圈的巨型表格列拆成條列，內容沒刪。

### 對照表（舊 → 新）

- §3.1 表每一列 → 同表同列；超長的列抽成 `####`：送單失敗的暫時與否、自動重送（退避 1m/10m/1h/6h、停機不花次數、收手、鎖後重讀）、刪除（CAS、`moved_on`、`unmanaged`、守衛根）。其後的 bullet（帳本以來源冪等、CAS、`asyncio.Lock`、`round_failed`、一輪多步、多集檔送 review、壞掉優先、`stalled` 10 分鐘）→ 〈其他規則〉。
- §3.2 表 → 摘要表加八個 `####`（qbit_poller、jellyfin_resolver、reconciler、rss_poller、health_checker、notify_sender、sweeper、所有迴圈）；表後六條 bullet（寫自己那一列、醒得比問頻繁、握 client、commit 後推播、補漏滾動、請求預算、有限重認、磁碟、健康檢查不退避、喚醒訊號）→ 各迴圈小節或〈所有迴圈〉；請求預算的理由 → ADR 0014。
- §3.3 → 同位置，全保留。
- §4.1 階段表與片長驗證 → 同位置，`classify`／`normalize_cjk`／`match_subtitle`／`plan` 的長格移成 `####`。
- §4.2、§4.3 → 同位置；§4.4 各條 → 同位置分 `####`；§4.5 → 同位置；§4.6 → 同位置，語料筆數改指向 `tests/fixtures/parser/README.md`。§5 → 同位置。

### 照程式寫、與舊 plan 不符處

- §4.5：`AiPlanner` 介面已刪，改寫成「已刪、M6 重新設計」。
- 識別符：`claims.reimport_hash`（舊寫 `adopted_hash`）、`jobs._check_disk`、`_program_checks`、`RESOLVE_DELAYS`；`ReasonCode` 的值串列其實是 `MappingStrategy` 的，改指向 `berth/domain/parser.py`。
- 語料筆數舊寫 32 筆，實為 40 筆，改指向 README。

### Spec 軸比對（opus 子代理，對 `8fa5d3e4`）

漏掉的已補回：resolver 排程的 11.5／21.5 分鐘、§11.2 T1.6 出處、One Piece 例子、2022 年例句、「找 item」與「找到之後」的次序。意思不符已修：§4.5、千年血戰篇例句。識別符五處已修。其餘小節比對完整。

### 未處理（留給使用者）

- 無 plan 與 brief 矛盾。
- ADR 0014 沒寫 migration id `c1d7e4a9b302`（舊 plan 寫了，檔案仍可 grep）；新版 plan 沒留，未補到 ADR。
