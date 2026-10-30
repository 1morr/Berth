# 05a — plan 去歷史：§0–§2（慣例、架構、資料模型）

**Status:** done

**Blocked by:** 02, 04a

**讀:** `.scratch/docs-diet/spec.md`（〈共同規則〉〈改寫規則〉）；plan §0–§2（約 165 行 41 KB，§2 資料模型 34 KB）；`docs/adr/` 的索引（brief §19）；改寫時遇到引用 brief 的地方才讀那一節

## 為什麼

plan 每行平均 330 bytes，117 處日期、1,007 處「票 NN」、12 處「推翻」混在規格裡，讀的人要自己拼出現況。plan 太大，按章節拆成 05a–05e，可以並行，後做的先 rebase。

## 做什麼

照 spec〈改寫規則〉改寫 plan §0–§2。章節與小節號不變（`berth/` 引用 §2.2–§2.4 各 30–50 次）。§2 的欄位清單對照 `berth/models/` 確認現況，plan 與程式不符時照程式寫，並列在 Comments。

## 驗收

- [x] 前後大小與歷史標記數貼 Comments；剩下的標記逐條有理由
- [x] 對照表貼 Comments，§0–§2 每個決定、規則、欄位、端點、數值都對到新版位置或 ADR
- [x] 收尾 code-review 的 Spec 軸照對照表逐節比對舊版，結果貼 Comments
- [x] 發現 plan 與 brief 的矛盾列在 Comments 問使用者，沒有自己挑
- [x] 全部檢查與 test 綠；progress.md 記一列 session；commit；不 push

## Comments

開工 commit：`a29281e1`。

### 前後

| | 開工 | 收尾 |
| --- | --- | --- |
| §0–§2 大小 | 44,206 bytes | 約 46 KB（補了程式有、plan 沒寫的欄位與表，用清單取代長段落） |
| 歷史標記（regex） | 118 | 0 |

沒有留下任何標記。大小沒降是因為對照 `berth/models/` 補了缺的內容；歷史敘述全刪。

### 對照表（舊 → 新）

- §0 語言、commit、里程碑、同步文件、型別、測試規則 → §0 同位置（刪「第四輪審計 E7、M4 票 57」）。
- §1.1 單程序、SQLite、SPA、gzip（含 SSE 排除與測試）、port、`CONFIG_ROOT`/`PORT`/`WEB_ROOT`、`/data` 非環境變數、`HOST_DATA_ROOT`、不拆路由 → §1.1 同位置（路由拆分理由補回一半）。
- §1.2 目錄樹、§1.3 依賴方向與六條規則、§1.4 依賴表（含不引入 shadcn）→ 同位置。
- §2.1 users / sessions / settings → §2.1；設定分組依程式重列，加 `search`、`notify`、`berth`、`disk`、`poller`、`notify_sender`、`notify_waiting`、`sweep`；`health`、`ai`、`rss`、`paths`、`setup.*` 規則逐條保留；`parser` 分組刪（程式沒有）。
- §2.2 routes / media / tmdb_cache 全部規則 → §2.2。
- §2.3 jobs / job_files / plans / plan_items / ledger / events → §2.3；新增 `duplicate_of`、`notifications`、`weekly_reports`。已拿掉的欄位（`last_seen_in_client_at`、`release_info_json`、`updated_at`、`source_inode`、`link_mode`）只留仍有用的理由（硬鏈接判 inode）。
- §2.4 rss_feeds / rss_series / rss_items / issues → §2.4；Issue 型別改為十九種分組表，subject 改成表，收尾規則與 `source_missing`/`unlinked` 先例逐條保留。
- §2.6 AI 與 §2.5、§2.6 Proposal → 同位置；加 `ai_runs.kind`、`awaiting_confirmation`、`proposed`；`tool_call_id` 改為非唯一（程式註明）。

### 照程式寫、與舊 plan 不符處

users 的五個通知欄、`plan_items.duplicate_of`、`ai_runs.kind`、`proposals.tool_call_id` 非唯一、`rss_feeds`/`rss_series` 無 `enabled`、`rss_series` 無 `group` 與 `passed_before`、IssueType 十九種（舊文寫十四）、兩張新表。

### Spec 軸比對（opus 子代理，對 `a29281e1`）

掉的內容已補回：路由拆分理由、`rss_feeds.created_at` 用途、`generic` 尚無 adapter、Mikan 另一欄規則、`subgroup` 空字串語意、Proposal `conversation_id` 無外鍵。與程式不符已修：通知欄數、issues subject 表（補 RSS Series / Feed）、`job_without_files` 與 `jellyfin_item_unresolved` 分列、Route 刪除與帳本的說法、通知放棄條件。

### 未處理（留給使用者）

- 無 plan 與 brief 矛盾。
- 子代理指出但沒做：各表 `ON DELETE` 與索引逐一列出（plan 本來沒寫，程式為準）；`setup` 其餘 JSON 欄位；`ai_calls` 等的 `id`；`proposer` 是否含 `system`；§1.2 仍列 `rss/generic`；§1.1 環境變數清單不全（`EXT_ROOT`、各 `*_PORT` 等）。
- §2.6 編號重複（AI 與 Proposal）、§2.6 排在 §2.5 前，按規則 4 沒動。

### 驗證

`uv run pre-commit run --all-files` 全過；`uv run pytest -q`：5280 passed, 1 skipped, 28 deselected。
