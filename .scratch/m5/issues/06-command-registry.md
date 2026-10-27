# 06 — 命令登錄表

**Status:** done

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

- [x] 登錄表列得出全部可用命令及其欄位（測試）
- [x] 送單、加 Feed、訂閱的 `validate` 擋得下實測那兩種理由（測試）
- [x] 推不出輸入模型的命令讓閘門紅（變異驗證）
- [x] plan §1.2 / §1.3 補登錄表的位置；全部檢查與 pytest 綠；progress.md 已更新

## Comments

- 2026-10-27（票 06 做完）：`services/registry.py`：`commands()`、`collect()`（閘門用）、`dry_run()`；`@command` 多收 `about` / `refusals` / `validate`（`commands.details_of`）。登錄 148 支。
  - **注入參數**依型別（session、client factory、hub、hints、source cache、Jellyfin access、bundled、host resolver）與名字（`actor`、`user_id`、`role`、`now`、`sleep`、`timeout`、`published_port`）認。名字那一半沒有測試守語意：哪天有命令用 `user_id` 指「要操作的那個人」，它會從輸入消失而閘門不紅。票 07 定 actor 與門禁時一起看。
  - **說明與拒絕理由只寫了四支**（送單、加 Feed、兩種訂閱）：其餘是空的，票 13 / 14 把命令登錄成工具時補。拒絕理由是宣告的，不從程式推。
  - **推不出輸入模型的七支**：`first_batch.vouch`、`rss.library_copy`、`issues.still_ignored` 標 `internal`（收 ORM 列或只在別的命令那一輪裡用）；`issues.replan` / `reimport` 的 `JobHints` 改當注入；`inventory.libraries_with_imports` 收 `Sequence`；`jellyfin.LibraryDraft` 從 Protocol 改成 pydantic model，`api.setup.BundledLibraryIn` 繼承它（OpenAPI 不變）。
  - **03b 的問題**：`Flag.INTERNAL` 明寫「身分與門禁」；照它把 `setup.claim_owner`、`sign_in_existing_owner` 也標 `internal`（code-review Spec 軸指出），`NAMED` 跟著改。`mark_played` 不在 services、沒有命令，要當工具時先搬進 services，本票沒動。
  - code-review 修掉的：`registry.dry_run` 沒標（Standards 軸）；送單預覽漏了「索引站報了 hash 而那一筆已在」——`check_submit` 改收 `source`，與 `add_download` 共用 `_before_resolve`（兩軸都指出，`job_removed` 那條測試守）；補 Callable 參數與 validate 多收參數的變異測試、「列出的集合 = 有標記非 `internal` 的全部」、乾跑後 session 不髒。
  - 沒處理的（判斷題）：命令先跑自己的驗證再重算一次 url、kind、rules、series（`add_feed`、`_subscribe`、`subscribe_search`），可以讓驗證函式回傳算好的值；驗證函式命名 `rss._can_*`（私有）與 `jobs.check_submit`（跨模組，公開標 `internal`）不一致；`registry._modules` 與 `test_command_marks.service_modules` 重複一份。
