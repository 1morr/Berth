# 08 — docs-diet 收尾：重量、封存、評估閘門

**Status:** done

**Blocked by:** 01, 02, 03a, 03b, 04a, 04b, 04c, 05a, 05b, 05c, 05d, 05e, 06, 07

**讀:** `.scratch/docs-diet/spec.md`（〈量測〉）；`docs/progress.md`〈寫法與封存〉；各票的 Comments

## 為什麼

每個里程碑都有驗收票，docs-diet 也要有一張：確認目標達到，並照〈寫法與封存〉把 docs-diet 自己的紀錄封存，第一次實際跑封存流程。

## 做什麼

1. **重量**：照 spec〈量測〉的表重量一次，前後並列貼 Comments：每個檔的大小、行數；plan / brief 的歷史標記數；§20 的行數。
2. **必讀範圍**：挑一張 M6 的票（或 plan §11.7），量「CLAUDE.md + progress.md + 票 + 票指到的章節」總共多少字，貼 Comments。讀不完的話，寫明卡在哪一份，問使用者要不要再開票。
3. **評估閘門**：plan / brief 的章節大小要不要加閘門（票 07〈不做〉留下的問題）。建議與理由寫 Comments，由使用者決定；要加就另開票。
4. **封存**：docs-diet 的 session 紀錄與偏差搬到 `docs/archive/docs-diet.md`，用 `scripts/docs_moved_lines.py` 證明；里程碑表 docs-diet 那一列改成「完成，封存於…」。
5. 各票 Comments 裡沒處理的發現彙整成清單貼 Comments，問使用者要不要開票。

## 驗收

- [x] 前後量測表貼 Comments
- [x] 必讀範圍量測與結論貼 Comments
- [x] 閘門評估寫了建議
- [x] `scripts/docs_moved_lines.py` 對 docs-diet 的封存跑出「遺失 0」，輸出貼 Comments
- [x] 全部檢查與 test 綠；commit；不 push

## Comments

### 1. 重量（前 `e4345674`，後 = 本票收尾的 HEAD）

| 檔 | 前 | 後 |
| --- | --- | --- |
| `CLAUDE.md` | 5,915 B、77 行 | 6,438 B、77 行（3,875 字，上限 6,000） |
| `docs/progress.md` | 893,188 B、1,812 行 | 3,123 B、39 行（1,954 字，上限 20,000；封存前 4,682 字） |
| `docs/plan.md` | 437,829 B、1,326 行 | 348,737 B、2,541 行（長表格列拆成條列，所以行數升、位元組降 20%） |
| `docs/design-brief.md` | 397,257 B、1,914 行 | 298,509 B、1,838 行 |
| `docs/development.md` | 85,339 B、830 行 | 10,124 B、152 行；子檔 `docs/development/` 五個共 77,242 B |
| brief §20 | 1,106 行 | 695 行 |
| 歷史標記（`grep -cE '取代原\|原寫\|推翻\|日期\|票 ?N\|MM-DD 改'` 行數） | plan 445、brief 404 | plan 14、brief 193 |

- plan 剩 14 行：研究檔名與連結檔名（05c、05d 逐條說明過）。
- brief 剩 193 行：絕大多數在 §20（各小節標題的「（日期 查證，票 N）」與研究檔引用，票 03a/03b 刻意留作來源指標），§0–§18 只剩 4 行（04b、04c 說明過）。這輪沒有做 §20 小節標題的去日期，因為 `berth/` 引用 §20.x 的號碼，標題日期是查證日，屬於證據。
- 偏差：spec 量測表 plan「每行 330 bytes」現在是 137 bytes。

### 2. 必讀範圍

M6 還沒拆票（`.scratch/m6/` 不存在），用 progress.md 閱讀指引列的拆票前讀：plan §11.7、brief §14、§6.10。

| 份 | 字數 |
| --- | --- |
| `CLAUDE.md` | 3,875 |
| `docs/progress.md` | 4,682（封存前，拆票前讀用的是這個量法）|
| plan §11.7 | 1,237 |
| brief §14 | 2,993 |
| brief §6.10 | 1,800 |
| 合計 | **14,587 字**（約 25 KB） |

前（spec 量測）：progress.md 單一檔就 893 KB。結論：讀得完，沒有卡在哪一份。票本身（約 1–3 KB）加進去仍在 17,000 字內。M6 開始拆票後再用真的票量一次。

### 3. 評估閘門（建議，由使用者決定）

- **不建議**對 plan / brief 章節加大小上限：它們不在必讀範圍內，只讀票指到的章節（本票量到最大的一組是 brief §14，3,000 字）。大小上限逼人縮短措辭，與「不為湊數縮短」衝突。plan 位元組降 20% 但行數翻倍，也說明行數不是好指標。
- **建議**加一個便宜的閘門：`plan.md` 與 `design-brief.md` 的 §0–§19（不含 §20 與封存段）歷史標記數不得高於現值（plan 14、brief 現值（§0–§19 是 5）），守住「只描述現況」。做法：測試數標記行，雙向變異驗證（補一個「2026-xx-xx 改」要紅，改無關字不紅）。§20 排除，因標題日期是證據。
- 要加的話另開票；本票不做。

### 4. 封存

`python3 scripts/docs_moved_lines.py HEAD docs/progress.md -- docs/archive/docs-diet.md`（封存編輯前的 HEAD `1d0efda5`）輸出：

```
removed 17 lines, found 17, missing 0
```

docs-diet 的 15 列 session 紀錄、1 條偏差、1 列閱讀指引搬到 `docs/archive/docs-diet.md`，本票的 session 紀錄一併寫在那邊（progress.md 只留 M0–M5 與 docs-diet 的一行說明，里程碑表那一列已改）。

### 5. 各票遺留，請使用者決定要不要開票

**plan 與 brief 的矛盾（沒有自己挑）**
- 04b：Issue 種類 14 vs `IssueType` 19；`unknown_torrent` 歸屬；`ledger.status` 缺 `unlinked`；資料夾名凍結時機；§5.1 高信心自動入庫 vs §6.5；§6.10「超出預算退回」vs「沒有月預算上限」；§6.5 low 進 review vs §6.10 開 AI 任務；絕對編號 medium 的例外（8 條）。
- 04c：§18 AI 助理的里程碑（M6 / M7 vs 側面板在 M5）；§18「AI 解析｜M5」我的推論待確認；§20.1「第一階段」說法。
- 05e：偵測用語（plan §9.2 vs brief §16.3）；`COMPOSE_PROFILES` 在哪一頁給；換台時「一鍵移除空分類」vs 勾選；精靈 qBittorrent 頁「已預置」；換台清單缺免密白名單；ADR-0011 的「第 6 步」頁碼。
- 05c：精靈頁碼，我寫成「Route 那一頁」，以 §9.3 為準。

**程式與文件可能不符（02）**：m4 解析 CPU 在事件迴圈上（疑未做）；m5「不在 M5」的 TMDB discover / recommendations / collection 端點無歸位；m4 約 40 條遺留「判不出」。

**05a 子代理指出沒做**：各表 `ON DELETE` 與索引、`setup` 其餘 JSON 欄位、`ai_calls` 的 `id`、`proposer` 是否含 `system`、§1.2 仍列 `rss/generic`、§1.1 環境變數清單不全。

**03b**：(a) §20.24 `outcome='retried'` 替代寫法與 §20.14「admin 但另設密碼」但書只在研究檔；(b) `berth/adapters/prowlarr/fake.py:17` 的「berth-trial」只在研究檔；(c) 追加段落在 11 個既有研究檔違反「歷史快照」字面（03a 有先例）；(d) 意譯條目與研究檔概要重複；(e) §20.14、§20.24 只縮 35–37%。

**07 轉來、06 的後續**（8 條）：`docs_moved_lines.py` 連結正規化忽略 `../` 深度可能掩蓋指向不同檔的連結；`commands.md:24,99`、`e2e.md:79` 跨檔引用沒連結；`docs/research/` 與 `.scratch/m5` 仍指 development.md 已不存在的章節（歷史快照不改）；`development.md:82` 沒寫正規化；子檔 `#` 直接接 `###`；`development.md:3` 沒指到 `commands.md`；連結檢查只 glob 一層；`scripts/experiments/README.md:3` 「單一來源」措辭。

**06**：驗收「遺失 0」字面是 13（原因見該票）。

### 6. 協調者追加：§19 列名舊引用

票 04a 把 §19 改成 ADR 索引後，沒人接手的舊引用在本票處理：
- brief §20：6 處加 3 處（§20.7 兩處、§20.8 兩處、§20.12–§20.13 起）共 9 處「§19 …」改連對應 ADR（0001、0002、0004、0009、0010、0012、0014）。
- `berth/` 41 處註解與 docstring 的「brief §19 …」改成 `ADR-00NN`，只動註解文字，不動邏輯。
- 對應是我依 ADR 的〈來源〉列判的；`D5`、`D7` 沒有 ADR（只在 brief §16.3 與 archive/m4），審查指出後改指 brief §16.3。`⑤`（介面密碼加鹽雜湊）歸 ADR-0010，`Policy` 與 session 的歸 ADR-0004 / 0012。

### 7. code-review（`/code-review 1d0efda5`）

Standards 軸已處理：D5、D7 改指 brief §16.3；brief §20.8 的 `Policy` 改連 ADR-0004；progress.md 重複的一句刪掉；封存檔頭註明最後一列是直接寫的。`berth/` 29 個 `.py` 的 AST（去 docstring）前後相同。
**未處理**：`tests/` 約 20 處、`web/src` 22 處仍有「brief §19 …」舊引用（spec 範圍規則 5 不許動 `web/`，`tests/` 的也沒在協調者指示內），請決定要不要開票；`03857521` 單看 test 紅、`3606359c` 才綠（已知，未改歷史）。

### 8. 最終驗證（`3606359c`，其後只有註解與文件的指標修正）

- `uv run pytest -q`（含 integration）：5282 passed, 1 skipped, 28 deselected。
- `uv run pre-commit run --all-files`：13 項全 Passed。
- 之後的修正 commit 再跑 `pre-commit run --all-files` 全過、`pytest tests/unit` 2182 passed。
- Spec 軸審查已處理：brief §20.8 改連 ADR-0004；D5、D7 改指 brief §16.3；重量表數字更正。
