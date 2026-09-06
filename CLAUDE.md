# Berth

自託管媒體取得與入庫協調器：索引站 / RSS → qBittorrent → 解析 → 硬鏈接入 Jellyfin。文件是唯一的記憶，對話不是。

## 文件

- `docs/design-brief.md`：需求、決定、查證過的事實（§20，附來源）。決定衝突時以它為準。
- `docs/plan.md`：架構、資料模型、狀態機、解析器、API、里程碑任務與驗收（§11）。
- `docs/progress.md`：任務狀態與 session 紀錄。每個 session 的起點與終點。
- `PRODUCT.md`、`DESIGN.md`：impeccable 維護的產品與設計脈絡（第一個 UI 任務起）。

## 每個 session 的流程

一個 session 只做一個任務。

1. 讀 `docs/progress.md`，取第一個 `todo` 任務；只讀它列出的 plan / brief 章節，其他章節按需讀。
2. 任務標「大」的先進 plan mode 拆成子任務寫回 progress.md，再做第一個子任務。
3. 實作與測試同一輪；行為以 plan §11 該任務的驗收欄為準。
4. 驗證：跑 lint、type、test；貼指令輸出。
5. 實作若推翻 plan 或 brief，同一 commit 改文件，並在 progress.md「偏差與決定」記一行。
6. 更新 progress.md（狀態、做了什麼、下一步），commit，結束並提醒使用者開新 session。

完成標準：驗收達成、lint / type / test 綠燈、progress.md 已更新、已 commit。四項缺一就還沒完成。

## 事實與查證

- 外部服務的端點、參數、版本行為只信兩處：brief §20，以及 context7 / OpenAPI 現查。brief 沒寫的先查再用，查到的補進 brief §20 並附來源。
- 程式庫 API 用 context7 查，或寫最小測試驗證。
- 現況以指令為準：`git log`、`git status`、測試輸出。progress.md 與 repo 不符時以 repo 為準並修 progress.md。

## 上下文紀律

- 讀大檔案、查文件、跑實驗交給子代理回摘要（模型規則見全域 CLAUDE.md）。
- brief 與 plan 各 500+ 行，只讀任務指到的章節。
- 對話已長或一個任務碰了十幾個檔案：把進度與下一步寫進 progress.md，結束 session。

## 架構規則（細節在 plan §1）

- 依賴方向 `api → services → domain / parser / naming / adapters / models`；`pipeline → services`；`parser` 與 `naming` 是純函式；`adapters` 不 import `services`。import-linter 強制。
- 改狀態的操作都是 `services` 內的命令函式；API 與 pipeline 只呼叫 services。
- 解析器改動必跑 `berth bench`，`auto_wrong` 不得上升。
- 檔名 token、log、識別符英文；UI 文案繁中，走 i18n key。

## UI

- 所有前端頁面走 `/impeccable`：第一次做 UI 前 `init`；新頁面先 `shape` 再實作；設定精靈用 `onboard`；每個里程碑 UI 收尾前 `critique`、`audit`、`polish`；設計系統定稿後 `document`。
- 第一個 UI 任務開頭執行 `/impeccable hooks on`。
- UI 改動用 playwright 實跑驗證，附截圖或文字結果。

## Skills

- `parser`、`naming`、`domain`、`services` 的新功能與修 bug：`mattpocock-skills:tdd`（紅 → 綠 → 重構，benchmark fixture 就是紅燈）。
- 設計 adapter 介面、解析器階段、services 命令的邊界：`mattpocock-skills:codebase-design`。
- 用實驗回答設計問題（T0.3 的 Jellyfin 命名實測這類）：`mattpocock-skills:prototype`，結論寫回 brief，原型不留。
- 查證外部事實：`mattpocock-skills:research`，輸出放 `docs/research/`，結論摘進 brief §20 並連結。
- 里程碑收尾：`mattpocock-skills:code-review`（對照 plan §11 驗收與本檔規範）；難 bug 或效能退化：`mattpocock-skills:diagnosing-bugs`。
- 改本檔或 progress.md 的流程段：`mattpocock-skills:writing-for-agents`。

## 指令

README 是指令的單一來源（T0.1 建立）。

## Agent skills

### Issue tracker

Local markdown：票與 spec 以檔案存在 `.scratch/<feature-slug>/`。See `docs/agents/issue-tracker.md`.

### Triage labels

五個預設角色標籤，字串與角色名相同。See `docs/agents/triage-labels.md`.

### Domain docs

Single-context：根目錄 `CONTEXT.md` + `docs/adr/`。See `docs/agents/domain.md`.
