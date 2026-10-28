# 26b — 命令登錄表推輸入模型時保留 `Annotated` 的限制與說明

**Status:** ready-for-agent

**Blocked by:** 26

**讀:** `berth/services/registry.py`（推輸入模型那一段，`create_model`、`get_type_hints`）；`berth/services/commands.py`；`tests/unit/test_command_registry.py`；票 26 Comments 的「未處理（記錄）」；CLAUDE.md〈架構規則〉命令登錄表那一條

## 為什麼

票 26 發現：登錄表用 `typing.get_type_hints` 推命令的 pydantic 輸入模型時沒帶 `include_extras=True`，命令簽名上 `Annotated[..., Field(...)]` 的限制與說明全被丟掉。例：`anilist.read_season` 的 `limit` 寫了 `ge=1, le=50`，模型（AI）傳 500 照收。影響所有用 `Annotated` 寫限制的命令：AI 工具的參數 schema 少了上下限與說明，伺服器也不驗。使用者 2026-10-29 決定開修復票。

## 做什麼

1. 先寫**會紅的測試**：一個帶 `Annotated[int, Field(ge=1, le=50)]` 的命令，推出的輸入模型拒收 0 與 51、JSON schema 有 `minimum` / `maximum` 與說明。
2. 修登錄表：保留 `Annotated` 的 metadata（`include_extras=True` 或等效寫法）；確認既有的特殊處理（`typing.get_origin(hint) is typing.Annotated` 那段、伺服器注入的參數）照舊。
3. 修好之後全部命令的輸入模型重推一次：哪些命令的參數多了限制（列進票 Comments）；有沒有既有呼叫端（API、測試、Fake 後端、e2e）因為限制開始生效而壞掉——壞的照限制的本意修呼叫端或修限制，寫理由。
4. 票 26 為了繞開而改成「一般參數加入口檢查」的地方，若改回 `Annotated` 更簡單就改回，否則留著並在 Comments 說明。
5. `gen:api` 若有 diff（API 的 schema 也走同一套）一併提交。

## 驗收

- [ ] 會紅的測試先紅後綠；拿掉修法會紅（變異）
- [ ] 全部命令的輸入模型重推過，多出限制的命令列在 Comments；壞掉的呼叫端已處理
- [ ] 全部檢查、pytest、vitest、前端 e2e 綠；`gen:api` 無 diff；progress.md 已更新
- [ ] 不發版、不 push

## Comments
