# 06 — 命令登錄表

**Status:** ready-for-agent

**Blocked by:** 03, 03b, 04

**讀:** plan §11.6〈分段〉第 2 段、§1.3（依賴方向）；brief §14〈API-first〉；`docs/research/m5-ai-direction-2026-10-27.md` C2〈卡片的原則〉、C4 第 4 點；brief §20.24 的「卡片預覽要先跑命令的驗證」；`berth/services/commands.py`；mattpocock-skills:codebase-design

## 為什麼

AI 的工具、確認卡、M7 的 MCP server，都要從同一份清單知道一個命令叫什麼、收什麼、回什麼、會被什麼理由拒絕、要不要人。實測發現卡片預覽沒有先驗證，按了確認才被 Berth 擋下，所以登錄表要能乾跑。

## 做什麼

1. `CommandSpec`：名稱（`"<模組>.<函式>"`）、pydantic 輸入模型、結果型別、拒絕理由、Effect、inverse、旗標、給模型的說明。
   - **輸入模型由簽名推出**：注入的依賴（session、client factory、source cache、actor）不進輸入。
   - **給模型的說明**：要寫給模型看的就明寫，不從 docstring 硬抓。
   - **只收要給人或 AI 用的命令**：`INTERNAL` 的不收。
2. **`validate`（乾跑）**：命令可以註冊一個驗證函式，回「可以做 / 為什麼不行」，不改任何狀態。
   - 先做送單、加 Feed、訂閱這幾支：實測抓到 `route_required`、`route_kind_mismatch`（brief §20.24）。
   - 沒註冊的命令，預覽只顯示參數。
3. 登錄表放在 `services` 層，import-linter 照舊守依賴方向。
4. 閘門：每個有標記、非 `INTERNAL` 的命令都要能註冊成功（推得出輸入模型），失敗就紅。照規則做雙向變異驗證。
5. 介面先用 codebase-design 想清楚再寫：登錄表是 M5–M7 三個介面共用的深模組。

## 驗收

- [ ] 登錄表列得出全部可用命令及其欄位（測試）
- [ ] 送單、加 Feed、訂閱的 `validate` 擋得下實測那兩種理由（測試）
- [ ] 推不出輸入模型的命令讓閘門紅（變異驗證）
- [ ] plan §1.2 / §1.3 補登錄表的位置；全部檢查與 pytest 綠；progress.md 已更新

## Comments
