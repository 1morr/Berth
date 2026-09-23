# `/review` 形狀（M2 票 06，`/impeccable shape`）

2026-09-23。視覺世界沿用 DESIGN.md 的「泊位調度板」，不開新世界；模式是 **Operate**。
直接前例是 `.scratch/m2/issues-shape.md`（`/issues`），這一份只寫與它不同或它沒回答的。

## 這一頁的工作

**誰來**：admin。不是整天盯著 Berth 的人——他被兩種時刻叫來：一筆下載停在待審核（有人在
`/jobs` 看到黃色的「待審核」），或者他想看一眼 Berth 這幾天自己替他決定了什麼（medium 自動入庫）。

**他要做的一件事**：把清單清空。每一列一個決定，決定完那一列消失。**成功的樣子是空清單**，
空的時候說「沒有事在等你」，不是「沒有資料」。

**這裡獨有的真話**：medium 的檔案**已經在媒體庫裡了**，而撤銷幾乎零成本（硬鏈接，complete 裡的
來源不動）。\*arr 生態只有「自動」與「手動」兩種，這一頁是 Berth 在兩者之間的那一格
（PRODUCT.md Positioning、brief §6.5）。

## 排法：三段，需要人動手的排前面（使用者 2026-09-23 拍板）

後端已經照 `REVIEW_PRIORITY` 排好（`plan` / `unmatched` → `audit` / `duplicate` → `issue`，同一級
之內舊的在前）。畫面把這三級各畫成一段：

| 段 | 類 | 抬頭（zh-Hant / en） |
| --- | --- | --- |
| 1 | `plan`、`unmatched` | 要你決定 / Needs a decision |
| 2 | `audit`、`duplicate` | 已入庫，等你看一眼 / In the library, awaiting a look |
| 3 | `issue` | 外面發生的事 / Happened outside Berth |

- 每段一條 `rule-strong` 重橫線抬頭，抬頭後面是那一段的件數（`.value tabular-nums`）。抬頭是
  `h2`，一列的標題是 `h3`。
- **空的段不畫**——這一票只有第 2、3 段有東西，第 1 段要到票 07 才出現。
- 分段由前端照 `kind` 映射，順序照回應的順序；**前端不重排**（排序只有後端一份）。
- 頁首 `h1` 旁是總件數；`total` 大於列數時多一句「只列出最舊的 N 件，共 M 件」——那時候該修的
  是上游，所以話要說出來，不是默默少幾件。

## 一列的共同骨架：`QueueRow`

`/issues` 那一票刻意不抽共用元件，等這一票有兩個真實案例（`IssueRow`、`AuditRow`）再抽。骨架
就是 `IssueRow` 現在的樣子，四格由上到下，全部在 `row-summary`（`well` 底、`border-2 border-rule`）裡：

1. **識別**：中性色塊的類別標籤（`deck` 底，The Role Is Not A State Rule——這一頁每一列都「在等人」，
   塗漆不區分任何東西）＋ 一個 `.value` 標題。
2. **一句話**：理由的 code 由前端翻成一句（`reason.code` + `params`），接一個中點與「多久以前」。
3. **展開**：`<details>` 收著的機器字串（路徑、來源、hash、解析器原文），掃視時不被路徑淹沒。
4. **動作**：照後端的 `actions` 順序畫，第一顆是建議動作。失敗時那一列**留著**，就地多一行
   `Notice signal="blocked"`：`reason` 的句子接 `detail` 原文。

`QueueRow` 只管框、標題、句子、展開、失敗與動作列的版面；每一類自己的元件（`AuditRow`、
`IssueRow`，之後的 `PlanRow`、`UnmatchedRow`）決定填什麼、按鈕打哪一支。

### `audit` 這一列

- 標籤：「待確認」/「Unconfirmed」。
- 標題：作品名（跟 UI 語言，`title` / `title_en`）＋ 季集（`S02E01`、多集 `S01E01–E02`），沒有作品時
  退回檔名。
- 一句話：`medium_auto_imported` →「信心 medium，已自動入庫」。
- 展開：媒體庫路徑、complete 來源、所屬下載（發佈名，連到 `/jobs`）、解析器的理由（英文原文，
  `notes`，逐條一行，標明是原文）。
- 動作：**確認**（ghost，不確認，只改旗標）、**撤銷**（就地確認，見下）。

### `issue` 這一列

就是 `/issues` 的 `IssueRow`，改成套 `QueueRow` 之後兩頁畫的是同一個元件、同一份 `IssueOut`。
按完後兩份清單（`['review']`、`['issues']`）一起重問。

## 破壞性動作：撤銷就地確認（使用者 2026-09-23 拍板）

撤銷會讓 Jellyfin 立刻少一集，而且那筆下載回到待審核——它是 PRODUCT 原則 2 說的破壞性動作。
沿用 `ConfirmAction`：按「撤銷」在那一列裡展開一句後果——「會從媒體庫拿掉這一集；complete 裡的
檔案不動，這筆下載回到待審核。」——再按「確定撤銷」才執行。取消把焦點送回「撤銷」那一顆。

**確認不確認**：它只清一個旗標，檔案不動。

## 狀態與範圍

| 狀態 | 畫面 |
| --- | --- |
| 讀取中 | 兩列靜態佔位（同 `/issues` 的 `Loading()`，沒有動畫） |
| 空 | 「沒有事在等你。」一句 |
| 一般 | 0–20 列。典型是一兩件 audit 加零到幾件 Issue |
| 多 | 上限 200 列（後端截）。**不分頁**，說出「只列出最舊的 200 件，共 M 件」 |
| 動作中 | 那一列的按鈕換成「處理中…」並 `disabled`（同 `IssueRow`） |
| 動作失敗 | 那一列留著，就地 `Notice`：句子 + `detail` 原文（`unlink_failed` 的原文是系統錯誤） |
| 另一個分頁先按了 | 409 `not_audited` / 404 `ledger_missing` 的句子，然後重問清單，那一列自己消失 |

## `user` 那一側：「等管理員審核」

`/review` 只有 admin 進得來（後端 403，導覽列不給 `user` 入口）。`user` 碰到停在 `review` 的那一筆
只能等，所以那句話在他看得到的兩處：

- **`/jobs`**：狀態色塊仍是 `assigned` 的「待審核」（狀態本身沒變），摘要列多一句中性小字
  「等管理員審核」。admin 看到的是一條到 `/review` 的連結而不是這句（票 07 起 plan 那一類才進佇列；
  這一票先只改 `user` 那一側）。
- **Media 詳情**：這部作品有停在 `review` 的下載時，季表上方一行 `Notice`（中性）「N 筆下載等管理員
  審核」。只對 `user` 畫。

## 媒體庫的子集（票 14 用，這一票不做）

媒體庫頁的「待審 / 對不到」清單用**同一個列元件**，只放這個媒體庫作品的 `plan` 與 `unmatched`
兩類（使用者 2026-09-23 拍板）：

- 兩類同屬第 1 段，所以**不畫段落抬頭**；列本身與 `/review` 一模一樣、就地按。
- 清單下方一句連到 `/review`：「審核佇列裡還有 N 件」。
- 所以 `QueueRow` 不能假設自己在分段裡：段落是 `ReviewPage` 的事，列不知道自己在哪一段。

## 邊界

- **不碰**：`/issues` 的頁面結構與對帳橫幅（只把 `IssueRow` 換成套 `QueueRow`）、Job 詳情頁（票 12）。
- **不做**：篩選、排序切換、分頁、批次選取與批次核准（brief §13 的「批次核准」等票 07 的 plan 列
  出現再回答）。
- **不做**：已確認 / 已撤銷的歷史檢視。那在時間線上（`audit_confirmed`、`audit_undone`）。

## 約束

- 文案全走 i18n key，zh-Hant 與 en 並列；件數用 `_one` / `_other`。
- 類別、理由 code、動作名、拒絕理由都是**封閉集合**，從 OpenAPI 產的型別取；拒絕理由的執行期表
  是 `ReasonSet<ReviewRefusal>`。
- WCAG 2.2 AA：純鍵盤走得完、確認區收起時焦點送回觸發鍵、狀態不只靠顏色（標籤是字）、動作結果
  有 `aria-live`。
- 窄版（390px）：標題換行不截斷（`wrap-anywhere`），動作列換行，不橫向捲動。
