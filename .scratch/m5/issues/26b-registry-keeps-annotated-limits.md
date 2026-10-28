# 26b — 命令登錄表推輸入模型時保留 `Annotated` 的限制與說明

**Status:** done

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

- [x] 會紅的測試先紅後綠；拿掉修法會紅（變異）
- [x] 全部命令的輸入模型重推過，多出限制的命令列在 Comments；壞掉的呼叫端已處理
- [x] 全部檢查、pytest、vitest、前端 e2e 綠；`gen:api` 無 diff；progress.md 已更新
- [x] 不發版、不 push

## Comments

### 2026-10-29 實作

- **修法**：`registry._spec` 改用 `typing.get_type_hints(target, include_extras=True)`。`bare_type` 先拆 `Annotated` 再拆 `X | None`：不拆的話，寫成 `Annotated[AsyncSession, ...]` 的注入參數會被當成輸入欄位（code-review 提出；現在沒有命令這樣寫，修之前也不會壞，加了 extras 才會）。`executor._injected` 仍用不帶 extras 的 `get_type_hints`，它只照型別配對注入，不需要 metadata。
- **重推全部 165 個命令的輸入模型，前後比 JSON schema，多了限制的四個**：
  - `anilist.read_season`：`limit` 1–50。
  - `bgm.read_calendar`：`limit` 1–120。
  - `usage.set_spend_alert`：`daily_usd` ≥ 0（簽名用 pydantic 的 `NonNegativeFloat`，本身就是 `Annotated`）。
  - `rss.subscribe_search`：`subgroup` `min_length=1`、`pattern=\S`（本票第 4 點改的，見下）。
- **沒有呼叫端壞掉**：`set_spend_alert` 的 API 與測試都直接呼叫函式，不經登錄表（API 的 body 本來就驗 ≥ 0）；`read_season`、`read_calendar` 經登錄表的只有側面板工具，測試與 e2e 都沒有帶超過上限的 `limit`；工具參數不合時 `agent.py` 本來就把 `ValidationError` 交還給模型，不會中止整輪。
- **票 26 的繞法改回 `Annotated`**：`rss.subscribe_search` 的 `subgroup` 改成 `Annotated[str, Field(min_length=1, pattern=r"\S")]`，函式裡那段「空白就丟 `ValueError`」刪掉。它的呼叫端只有兩條，都過輸入模型：API（`Command("rss.subscribe_search")` → 執行器 `spec.input.model_validate`）與確認卡（`proposals` 提出時逐列 `spec.input.model_validate`）。`_can_subscribe_search` 的說明本來就寫「字幕組只驗不是空的（輸入模型）」。
- **測試**：`test_command_registry.TestAnnotatedLimits` 四條——限制擋 0 與 51、JSON schema 有 `minimum` / `maximum` / 說明、關鍵字訂閱的空白字幕組被輸入模型擋、`Annotated` 的注入參數照舊注入。變異：`_spec` 拿掉 `include_extras` 前三條紅；`bare_type` 拿掉拆 `Annotated` 第四條紅。
- **`gen:api` 無 diff**：API 的 body 是 `berth/api` 自己的 pydantic model，不是登錄表推的。
- **code-review 未處理（記錄）**：
  - 不經登錄表直接呼叫 `subscribe_search(subgroup="  ")` 會 strip 成 `""`，建出「每一組都收」的 Feed（`RssFeed.subgroup` 空字串的意思）。正式的呼叫端都經登錄表，直接呼叫的只有測試；為這個在函式裡再留一道檢查，就回到本票要拿掉的雙重寫法。
  - 卡片那一列 `agent.SearchSubscriptionRow.subgroup` 只有 `min_length=1`、沒有 `pattern`：全空白的字幕組要到 `proposals` 逐列過輸入模型時才擋（之前要到按下確認才丟 `ValueError`），擋下之前搜尋預覽已經讀過一次網路。模型照工具說明給的是發佈名裡的組名，沒有改。
  - 字幕組的限制在 API 的 `SearchSubscriptionIn` 與命令簽名各寫一份（API 要在 body 驗證時回 422）；本票之前就是兩份，沒有抽共用型別。
- **驗證**：`uv run pre-commit run --all-files` 全過；`uv run pytest -m "not e2e"` 5199 passed、1 skipped；`pnpm -C web test` 2316 passed；`pnpm -C web e2e` 72 passed（2.2m）；`pnpm -C web gen:api` 無 diff。
