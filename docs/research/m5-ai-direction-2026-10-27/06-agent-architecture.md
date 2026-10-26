# 06 Agent 架構：claw 類專案、Agent SDK、MCP、串流 UI、多頻道，以及三種架構的含意

查證日期：2026-10-27（未另註者都是這天查的；沿用舊檔的標「沿用」並註明原檔）。目的：M5 要做 (1) 背景 AI 任務接管人工審核點、(2) 每頁都開得到的對話側面板（用對話新增 RSS 訂閱、indexer、下載，結果是卡片，要確認的動作在卡片上按確認；tool / skill / MCP、自動壓縮、`/compact`）、(3) 之後 Discord 上跟同一個 agent 對話。本檔只陳述事實與分析，不拍板；最後一節比較三種架構。

來源標記 `[n]` 對應文末「來源」清單，每條都附 URL 與查證日期。「分析」「推論」是我的判斷，不是查得的事實。

## 0. 前提與沿用說明

### 0.1 Berth 現況（讀 repo 得到，2026-10-27）

- 後端 Python >=3.13，FastAPI、SQLAlchemy asyncio、`sse-starlette`、`httpx>=0.28.1` 已是依賴 [55]。
- services 命令已有 `@command(Effect, inverse=)` 標記，共 81 處（`grep -rn "@command(" berth | wc -l`）；`Effect` 三級 `READ` / `REVERSIBLE` / `IRREVERSIBLE`；標記是掛在函式上的 `CommandMark`，**登錄表本身還沒做**；命令簽名吃 session 與 factory、拒絕是各模組自己的例外，離「pydantic 輸入」還有一段（plan §11.6 自己這樣寫）[55]。
- 前端 `web/package.json`：React 19.2、TanStack Router 與 Query、Tailwind 4、i18next、Vite 8、vitest、Playwright；**沒有任何元件庫或聊天 UI 庫**；型別由 `openapi-typescript` 從後端產生 [55]。所以第 4 節只推薦 React 相容的方案，Vue / Svelte 專用的不列。
- 既有決定（brief §14、plan §11.6–11.8）：Proposal 只用在不可逆與沒把握的事；`ai_tasks` + `ai_worker`；影子模式；M7 同一個 bot 收訊息、身分用個人 API token、命令登錄表另外包成 MCP server [55]。
- Discord 現況：M4 是 bot 私訊的純 REST 通知；互動（按鈕、slash）只能走 gateway 的 `INTERACTION_CREATE` 或公開的 Interactions Endpoint URL，家用伺服器沒有公開網址時只能 gateway（brief §20.23）[55]。

### 0.2 沿用與新查（詳見第 8 節）

repo 內已有三份相關研究，我只讀 `git show`、沒動分支：

- [P1] `bk:docs/research/claw-references.md`（2026-10-26）：nanoclaw、openclaw、pydantic-ai、Claude Agent SDK 對照。本檔對 nanoclaw / openclaw 的原始碼層結論**沿用**，只做現況驗證與補充。
- [P2] `bk:docs/research/ai-provider-and-tools.md`（2026-10-26）：SDK 版本、模型價格、搜尋工具、MCP client、Discord 長度限制。**沿用**。
- [P3] `backup/m5-attempt-1-20261024:docs/research/ai-providers.md` 及 `ai-providers/{anthropic,openai-compatible}.md`（2026-10-24）：Anthropic Messages 與 OpenAI 相容格式、串流事件、錯誤、`usage` 欄位。**沿用**，本檔不重查。

我沒有讀那次已撤銷的 M5 實作嘗試的程式碼與撤銷原因，只讀了它的研究檔。

---

## 1. claw 類專案

### 1.1 一張表

| 專案 | 語言 | 規模 / 維護（2026-10-27） | agent loop | 頻道 | 工具確認 | 壓縮 | 安全模型 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **openclaw** | TypeScript | 393,155 star，MIT，最近 push 2026-10-26，release `v2026.10.7`（10-24），OpenClaw Foundation 維護 [5] | 自有（`packages/agent-core`，舊 runtime id `pi` 是別名）[P1] | 單一 Gateway 承載 20+ 頻道（WhatsApp、Telegram、Slack、Discord、Signal、iMessage、WebChat…）[5][6] | exec approvals：`allow-once / allow-always / deny`，綁確切 argv、cwd；頻道各有 approver 清單，沒按鈕的頻道退回文字 `/approve <id> <decision>` [8][P1] | 自有摘要，固定段落、overflow 重試、失敗保留原歷史 [P1] | 應用層（allowlist、配對碼、approver）；沙盒可選、預設關 [5][P1] |
| **nanoclaw** | TypeScript（host Node，容器內 Bun） | 31,024 star，MIT，最近 push 2026-10-26，release `v2026.10.0`（10-09）[1] | 不自寫：容器內用 Claude Agent SDK `query()` [2][P1] | 主幹只有 registry 與 Chat SDK bridge；Discord、Slack、Telegram、WhatsApp… 以 `/add-<channel>` skill 複製進 fork [2][3] | `ask_user_question`（阻塞 tool、預設 300 秒）+ 特權動作的 `pending_approvals` 卡片，approver 依 `user_roles` 挑 [P1][3] | 靠 Claude Code 自動壓縮 + `PreCompact` hook 注入規則 [P1] | OS 層：每 session 一個 Docker 容器，憑證不進容器（credential gateway）[2][4] |
| **pi**（`earendil-works/pi`，舊名 `badlogic/pi-mono`） | TypeScript | 118,022 star，MIT，最近 push 2026-10-26，`v1.4.0`（10-21）[11] | 自有 `pi-agent-core`（事件流、`beforeToolCall` / `afterToolCall` hook、`transformContext`）[12] | 核心無頻道；`pi-chat` 擴充把 Discord / Telegram 接到沙盒化的 pi session（每頻道一個 Gondolin micro-VM）[14] | **README 明說沒有內建權限系統**，要自己 containerize 或寫 extension [11] | 自有：`contextTokens > contextWindow - reserveTokens`（預設 16,384）觸發，保留近 20k token，`/compact [instructions]` [13] | 無（交給容器 / VM）[11] |
| **Hermes Agent**（Nous Research） | **Python** | 257,401 star，MIT，最近 push 2026-10-26，GitHub release `v0.22.5`（10-23）；PyPI 只到 0.19.0（07-20）[15][19] | 自有同步 `AIAgent`（loop 在 `agent/conversation_loop.py`）[16] | 單一 gateway 行程，25+ platform adapter，DM 配對與 allowlist [16][15] | `approval.py` 偵測危險指令、終端 callback [16] | 可換的 `ContextEngine` ABC，預設 lossy 摘要中段 turn；session 存 SQLite + FTS5 [16] | 預設本機執行，可選 Docker / SSH / Modal 等 backend [15] |
| **nanobot**（HKUDS） | **Python**（>=3.11） | 49,420 star，MIT，`v0.3.5`（2026-09-15），PyPI `nanobot-ai` 0.3.5 [17][19] | `MessageBus → AgentLoop → AgentRunner`；Runner 負責 provider / tool 迴圈 [18] | Telegram、Discord、Slack、Teams、Email…，channel 是自成一包的 package，自動發現；WebUI 也是一個 websocket channel [17][18] | 本次未查 | `/compact`；WebUI 時間線顯示壓縮 [17] | 應用層（DM pairing、allowlist）[17] |

另有 zeroclaw（Rust，33,050 star）、picoclaw（Go，30,080 star）、ironclaw（Rust，12,678 star）；只從 `gh search` 看到規模，**沒有讀內容**，不下結論 [47]。

### 1.2 各專案值得知道的細節

**openclaw**（沿用 [P1]，補現況）

- 頻道抽象是一個大契約 `ChannelPlugin`（20 多個可選 adapter 欄位）；回覆固定回到來源頻道，模型不選頻道；`webchat` 是內部頻道，與外部頻道共用 session / 指令 / 確認流程 [P1][6]。
- 斜線指令分三類：Commands（單獨成一則訊息，Gateway 處理）、Directives（`/think /model /queue` 等，進模型前剝除）、Inline shortcuts；`/compact [instructions]`、`/approve <id> <decision>`、`/stop`、`/usage`、`/context` 都在表內 [7]。
- 新查：approval 的授權與「訊息顯示在哪」是兩件事。官方文件：「Session delivery only controls where the prompt appears. It does not by itself authorize every participant in that chat to approve」，Discord / Telegram / Matrix / Slack 的原生核准用各自解析出的 approver 清單授權 [8]。
- 新查（反面教材）：兩個 issue 暴露了抽象的洞。(a) 在沒有 typed-approval encoder 的頻道（Feishu），核准卡的三顆按鈕退化成不能點也不能打字的純文字標籤 [9]；(b) `DiscordExecApprovalHandler.shouldHandle()` 沒檢查 `turnSourceChannel`，從 webchat 發起的核准也會寄到 Discord DM [10]。對 Berth：卡片能力要宣告、不能假設；核准要路由回發起的表面，但狀態只能有一個權威（資料庫那一列）。
- 規模：repo 約 62,700 個路徑 [P1]，只能參考概念。

**nanoclaw**（沿用 [P1]，補現況）

- 「Everything is a message」：host 與容器只靠兩個 SQLite 檔（`inbound.db` / `outbound.db`）溝通，一檔一個 writer [3][P1]。
- 頻道走 Vercel 的 Chat SDK bridge（npm `chat` 4.43.0 與 `@chat-adapter/discord` 4.43.0，2026-10-19）[46]。文件列出 Discord 能力：embeds、buttons、串流用「post + edit」；平台不支援卡片時降級成文字 [3]。Chat SDK 是 TypeScript，Python 不能直接用。
- 斜線指令在 host 端 `command-gate` 先分類：admin-only（`/clear /compact /context /cost /usage /stats /files /reset /new /upload-trace`，查 `user_roles`）、filtered（`/help /login /doctor /config /settings…` 靜默丟棄）、其餘放行 [P1][3]。實作細節：admin / 放行指令只有作為一次 query 的第一個輸入才會被 SDK 當指令，中途推入會變純文字，所以偵測到時 `query.abort()` [P1]。
- 壓縮會吃掉規則，nanoclaw 的對策是壓縮前（`PreCompact` hook）與壓縮後（注入提醒）都重申規則 [P1]。
- 容器隔離換來的是「agent 可以有 shell 與檔案工具也不怕」；它自己的 README 也說 openclaw 的安全是應用層、同一個 Node 程序共用記憶體 [2]。

**pi**（全新）

- pi-agent-core 是 TS 函式庫：`Agent` + `subscribe()` 事件流（`message_update`、`tool_execution_start/end`、`turn_end`、`agent_end`），`transformContext()`（裁剪 / 注入）與 `convertToLlm()` 兩段轉換，`beforeToolCall` 可擋、可帶 `terminate: true` [12]。
- compaction 文件值得抄的點：壓縮請求**關掉 prompt-cache 寫入**（一次性 prompt 不會被重用）；檢查點在工具結果附加後、下一次回應開始前；provider 回 context-overflow 時選一次「壓縮並重試」[13]。
- 官方立場是不做權限、不做 sub-agent、不做 plan mode，「要的話自己用 extension 建」[11]；對 Berth 的意義是：pi 當**外部 agent**（架構 B）可行，當**內建 agent 參考**只有 loop / compaction 的細節可抄。
- `pi-chat`（430 star，最近 push 2026-06-05，較不活躍）：Discord 要開 Message Content Intent；串流預覽用 edit-in-place；`stop / compact / new / status` 是遠端控制指令 [14]。
- 同 monorepo 還有 `pi-durable`（"Durable conversation, task, and document runtime"）與 `pi-ai`（多 provider 統一 LLM API）[11]；本次未讀，不評。

**Hermes Agent**（全新，Python，值得看）

- 架構：CLI / Gateway / ACP 都進同一個 `AIAgent`；`hermes_cli/commands.py` 的 **`COMMAND_REGISTRY` 是中央的斜線指令定義**，CLI 與 gateway 共用（`model_switch.py` 的 `/model` 邏輯也是 CLI + gateway 共用）；session 存 SQLite + FTS5，有壓縮造成的 parent/child lineage [16]。
- 壓縮：`ContextEngine` 是可換的 ABC，預設 `context_compressor.py` 摘要中段 turn；另有 `prompt_caching.py` 管 Anthropic cache [16]。
- 規模警告：repo 根目錄有上百個 `hermes_state_*.py`（`gh api .../contents` 看到的檔名）；PyPI 套件依賴精確釘死（`openai==2.24.0`、`pydantic==2.13.4`、`requests==2.33.0`…）且 `Python <3.14` [19]。它是一個應用，不是可嵌入的函式庫。
- 它的「自我進化」功能（agent 自己建立並改良 skill、記憶 nudges）是 Berth 不想要的（見 1.4）。

**nanobot**（全新，Python）

- 分層乾淨：`AgentLoop`（頻道面：session、workspace、context、發佈 outbound）與 `AgentRunner`（模型面：provider 呼叫、串流、tool 執行、終止條件）分開；channel 與 loop 之間隔一個 `MessageBus`（`InboundMessage` / `OutboundMessage`）[18]。這是把「多頻道一個核心」做成最小形狀的好範例。
- MCP 連線是應用層擁有的基礎設施：組合根建立 `MCPProvider`，與 `AgentLoop` 共用同一個 `ToolRegistry`，並保證 `aclose()` [18]。
- 提供 WebUI（打包在 wheel 內）、OpenAI 相容 API、Python SDK；PyPI 套件基礎依賴 61 條（含 `ddgs`、`openpyxl`、`prompt-toolkit`…）[17][19]，同樣是應用不是函式庫。

### 1.3 哪些設計值得 Berth 抄

| 設計 | 出處 | 為什麼對 Berth 有用 |
| --- | --- | --- |
| 待核准請求是**持久化的一列**（id、參數、過期、sweep），不是記憶體裡的 coroutine | nanoclaw `pending_approvals` / `pending_questions` [3]；pydantic-ai `DeferredToolRequests` [26]；OpenAI Agents `RunState` 可序列化 [36] | 卡片可能由側面板或 Discord 任一邊按、隔很久、中間重啟；對上 Berth 已決定的 `proposals` 表 |
| 授權（誰能按）與投遞（卡片出現在哪）分開 | openclaw approver 清單 [8]；nanoclaw `user_roles` [P1] | Discord 頻道裡所有人看得到卡片，但只有對得到 Berth 使用者且有角色的人能按 |
| 沒按鈕的表面用文字指令備援 | openclaw `/approve <id> <decision>` [7][9] | 頻道能力不同；且按鈕失效時使用者仍能完成 |
| 斜線指令在 host 端、進模型之前攔截；一份中央登錄表給所有表面 | Hermes `COMMAND_REGISTRY` [16]；nanoclaw `command-gate` [P1]；openclaw 三類指令 [7] | 不花 token、不被外部內容（RSS 標題）裡的 `/xxx` 觸發 |
| 壓縮：完整歷史留在儲存層、只改變送給模型的視圖；切點保持 tool call / result 成對；失敗保留原歷史；摘要固定段落；壓縮前後重申規則 | openclaw [P1]；nanoclaw [P1]；pi [13] | 見 6.2 |
| 重複呼叫偵測（同工具、同參數、同錯誤連續 3 次就停） | openclaw `loop-detection` [P1] | 無人值守的背景任務會燒錢 |
| 外部內容用邊界標記包裝 | openclaw `prompt-injection.md` [P1] | RSS 標題、種子名稱、字幕組備註是最大的不可信來源 |
| channel 與 loop 之間只隔一條 bus | nanobot [18] | 側面板（SSE）與 Discord 對核心看起來一樣 |

### 1.4 哪些不適合

- **容器隔離與 shell / 檔案工具**：它們的安全邊界是「agent 能跑任意指令，所以關進容器」。Berth 的 agent 工具只有命令登錄表，沒有 shell 與檔案系統，邊界是「能做的事 = 登錄表命令 + 確認卡」[P1 §5.2]。多開一個 Node / Bun 容器對 NAS 使用者是純成本。
- **agent 改自己的 skills / 設定 / MCP**：openclaw Skill Workshop 與 `/learn`、Hermes 自主建立 skill、nanoclaw `add_mcp_server` / `install_packages` [P1][15]。注入內容可以藉此擴大影響面；Berth 的「記憶」已決定是結構化資料（brief §14），不是 agent 自寫的檔案。
- **20+ 頻道契約、sub-agent、ACP、dreaming、plugin hooks 全集**：規模不符 [P1]。
- **「通用電腦操作」的預設值**：openclaw 預設 agent 逾時 48 小時、迴圈偵測預設關、沒有硬性費用上限 [P1]；Berth 的背景任務必須每個 run 都有上限。
- nanoclaw 的帳號 / 社群入口（portal.nanoclaw.dev）、遙測 [2]：Berth 是自架，不需要。

---

## 2. Agent loop SDK（Python 能用的）

### 2.1 版本與依賴（PyPI JSON API，2026-10-27）[19]

| 套件 | 最新版（發佈日） | 授權 | Python | 基礎依賴 | star（GitHub）[47] |
| --- | --- | --- | --- | --- | --- |
| `claude-agent-sdk` | 0.2.174（10-24） | PyPI 標 MIT，但使用受 Commercial Terms 規範 [20] | >=3.10 | `anyio`、`jsonschema`、`mcp<3`、`sniffio`、`typing-extensions`；**wheel 115.9–129.4 MB**（內含 Claude Code 原生執行檔）| 8,357 |
| `anthropic` | 2.3.0（10-23） | Apache-2.0 | >=3.10 | 8 條：`anyio`、`httpx2`、`jiter`、`pydantic`、`docstring-parser`、`opentelemetry-api`… | 4,009 |
| `pydantic-ai-slim` | 2.61.0（10-24） | MIT | >=3.11 | 8 條：`pydantic`、`pydantic-graph`、`httpx2`、`genai-prices`、`opentelemetry-api`…；provider / UI / MCP 走 extras（`anthropic`、`openai`、`google`、`ui`、`ag-ui`、`mcp`、`web`…）| 20,888 |
| `pydantic-ai-harness` | 0.61.0（10-24） | MIT | >=3.11 | 官方 capability 函式庫；**0.x，API 可能在 minor 間變動** [32] | 957 |
| `openai-agents` | 0.24.0（10-15） | MIT | >=3.10 | 12 條：`openai>=3`、`httpx2`、`mcp`、`starlette`、`websockets`、`requests`、`pyjwt`…；多 provider 走 extras `litellm` / `any-llm` | 30,305 |
| `litellm` | 1.106.4（10-25） | PyPI 標 MIT（GitHub 顯示 NOASSERTION） | >=3.10,<3.15 | 重：`openai<3`、`boto3`、`tokenizers`、`huggingface-hub`、`tiktoken`、`aiohttp`、`jinja2`、`httpx`… | 62,082 |
| `langgraph` | 1.2.18（10-26） | MIT | >=3.10 | `langchain-core`、`langgraph-checkpoint`… | 43,940 |

注意兩點：
- `anthropic` 2.x、`pydantic-ai`、`mcp` 2.x、`openai-agents`、`fastmcp` 4.x 都改用 **`httpx2`**；Berth 目前是 `httpx` + `respx`，且 `pyproject.toml` 註解寫明 Starlette 的 TestClient 也不跟著分裂 [55][19]。引入任何一個，環境裡就有兩套 HTTP 庫。
- `litellm` 要求 `openai<3`，`openai-agents` 要求 `openai>=3`（PyPI metadata）[19]：兩者不能無縫同環境。

### 2.2 Claude Agent SDK（Python）

- 本質：函式庫會**起一個 `claude` CLI 子行程並用 stdio 溝通**，一個 agent session 對一個子行程，子行程擁有 shell、工作目錄與磁碟上的 session 檔 [21]。官方 overview 把它描述為「A library that runs the Claude Code binary」[23]。
- 執行環境（**修正 [P2]**）：[P2] 說「文件頁沒有明說是否需要另外裝 Node」。現在的 hosting 頁寫明：「Both the TypeScript and Python SDKs bundle a native Claude Code binary for most installs, and the spawned CLI needs no separate Node.js install」；Python SDK 只要 Python 3.10+；README 也說 CLI 自動隨套件附帶，`cli_path` 可指定自備 [20][21]。
- Docker 要求：官方建議起點「1 GiB RAM、5 GiB disk、1 CPU per agent」，記憶體隨 session 長度成長，不設 session 逾時（要靠 `max_turns` 限制）；平台別 wheel（glibc / musl、架構要對）否則 `CLIConnectionError: failed to start Claude Code` [21]。
- 授權與金鑰：README「Use of this SDK is governed by Anthropic's Commercial Terms of Service, including when you use it to power products and services that you make available to your own customers and end users」；overview「Anthropic does not allow third party developers to offer claude.ai login or rate limits for their products... Use the API key authentication methods」；品牌規定不得稱 "Claude Code" [20][23]。所以**使用者填自己的 API key 是被允許的路徑**；Berth 作為 MIT 開源專案散佈、使用者自行安裝時 Commercial Terms 怎麼適用，我沒有結論，**需要人讀條款**。
- 只給自訂工具、不給檔案系統 / bash：可以。`tools: []`「All built-ins are removed. Claude can only use your MCP tools」；自訂工具用 `@tool` + `create_sdk_mcp_server()` 變成行程內 MCP server；`setting_sources=[]` 關掉讀 `~/.claude` 與專案設定；`CLAUDE_CODE_DISABLE_AUTO_MEMORY=1` 關掉自動記憶 [21][22]。但子行程本身仍擁有 shell 與磁碟（只是工具不給模型）[21]。Python 的 `tools` 選項名稱我沒有逐一核對 Python 參考頁（文件表格是通用寫法）。
- 工具註解：`@tool(..., annotations=ToolAnnotations(readOnlyHint=True))`；預設值 `readOnlyHint=false`、`destructiveHint=true`、`idempotentHint=false`、`openWorldHint=true`；「Annotations are metadata, not enforcement」[22]。
- 權限 / hooks：評估順序 hooks → deny 規則 → permission mode → allow 規則 → `canUseTool` callback（只在落到「詢問」時才呼叫）；Python 版是 `can_use_tool`、`PreToolUse` hook 可回 `deny` [24][P1]。這是 **run 內阻塞**的核准模型，不是 deferred（[P1] 已指出對 SQLite + 多入口不理想）。
- Compaction：由 CLI 自動處理與 `/compact`；`ClaudeAgentOptions` 沒有 `compaction_control`（claude-code issue #19686）；`context_management` 也還在被要求加成一級參數（issue #581）[25][P1]。要自訂摘要格式只能用 `PreCompact` hook（nanoclaw 就這樣做）。
- Session 持久化：預設存本機 `~/.claude/projects/`；跨主機要實作 `SessionStore` adapter（官方有物件儲存 / KV / 資料庫的參考實作；寫入是 best-effort 的鏡像，失敗會丟 `mirror_error` 訊息）[21]。
- Provider：官方說明的路徑是 Anthropic API、Bedrock、Google Cloud；也可用 `ANTHROPIC_BASE_URL` 指到 proxy [21]。**推論**：非 Anthropic 模型只能靠「Anthropic 相容的 gateway」，且 Claude Code 的 harness 針對 Claude 調過，我沒有查證其他模型的實際表現。
- 另一個選項：Managed Agents（Anthropic 代管 agent loop，工具跑在 Anthropic 管理的雲端沙盒或自架 sandbox）[21]。Berth 的工具是 LAN 內的服務，本次沒深查。

### 2.3 `anthropic` Python SDK（tool runner 與原生 context management）

- Tool runner（`client.beta.messages.tool_runner` + `@beta_tool`）仍在 beta 命名空間。`stop_reason` 為 `tool_use` 時自動執行工具、`pause_turn` 或 `compaction` 時把該 turn 原樣送回 [25]。**沿用 [P2]**：官方 tool runner 文件建議需要 human-in-the-loop 核可時改用 manual loop；與 Claude API skill 的說法有出入，實作前用最小測試確認。
- Compaction（server-side，Claude 專用）：`compact-2026-09-04`（on demand，由你決定何時壓縮，`runner.compact_before_next_turn()`）與 `compact-2026-01-12`（門檻觸發，`context_management.edits=[{"type":"compact_20260112","trigger":{"type":"input_tokens","value":N}}]`，門檻至少 50,000 token；選項 `pause_after_compaction`、自訂 `instructions`）；舊的 client-side `tool_runner(compaction_control=...)` 已在 2.0 移除 [25]。
- 其餘（prompt caching 斷點、`usage` 欄位、錯誤、串流事件、價格）**沿用 [P2][P3]**，不重查。

### 2.4 pydantic-ai（2.61.0）+ pydantic-ai-harness（0.61.0）

這是本次最重要的新發現，因為 [P2] 把 pydantic-ai 的 human-in-the-loop 與 compaction 標為「未驗證」，而 [P1] 只驗證到 deferred tools 與 `ProcessHistory`。

- **Deferred tools（人在迴圈）**：工具標 `requires_approval=True`（或在工具內 `raise ApprovalRequired`），run 以 `DeferredToolRequests` 結束（`approvals` 帶 `ToolCallPart`：工具名、驗證過的參數、tool call id），呼叫方帶 `message_history` 與 `DeferredToolResults`（`True` / `ToolDenied(...)` / `ToolApproved(override_args=...)`）再 run 一次 [26]。也可以用 `HandleDeferredToolCalls` capability 在同一次 run 內解決 [26]。**沿用 [P1] 的結論並重新驗證現況仍在**（文件版本從 v2.0.0 升到 2.61.0）。
- **UI adapter**：`pydantic_ai.ui.vercel_ai.VercelAIAdapter` 與 `pydantic_ai.ui.ag_ui.AGUIAdapter`，`dispatch_request(request, agent=...)` 直接接 FastAPI / Starlette；`sdk_version` 接受 5、6、7（原始碼註解：「`sdk_version=7` emits the same wire as 6」），6 起才有 tool approval 串流（`tool-approval-request` / `tool-output-denied`）[27][28][29]。官方警語：「Tool approval responses are trusted from the request by design」；若要把核准決定綁在伺服器狀態，要攔 `DeferredToolRequests`、把 approval id 存在伺服器、resume 時傳明確的 `deferred_tool_results` [27]。這正是 Berth `proposals` 表的角色。
- **Compaction**：核心有 `ProcessHistory(fn)`，`ctx.context_window_used`（0–1 比例）可寫「超過 80% 就壓縮」的處理器 [30]；`AnthropicCompaction(token_threshold=150_000 預設, 下限 50_000, instructions, pause_after_compaction)` 包 server-side compaction；`OpenAICompaction` 包 OpenAI Responses 的 compaction [31]；harness 的 `Compaction` 是「model-agnostic strategies: tool-result clearing, sliding-window trimming, LLM summarization, tiered; all window-relative, with live usage reporting」[32]。
- **harness 還有**（0.x）：`Memory`、`Skills`（載入 `SKILL.md`）、`Spend Limits`（跨視窗 USD / token 預算、per model / per tenant）、`Guardrails`（擋 / 遮蔽輸入、工具呼叫、工具結果、輸出）、`Prompt Injection Defender`（分類本地工具結果）、`Ask User`、`Approval Reviewer`（第二個模型對每個待核准呼叫回答一個風險問題，低風險自動通過，其餘留給人）、`Warn On Cache Busts`（偵測 prompt cache 前綴塌掉）[32][33]。注意 harness 官方警告 0.x API 可能在 minor 間變動 [32]。
- **MCP client**：`MCPToolset(url, http_client=httpx2.AsyncClient(...), prefer_tasks=...)`，`toolset.approval_required()` 讓整組 MCP 工具都走 deferred approval [35]。`mcp` extra 依賴 `fastmcp-slim[client]<5,>=3.3.0` [19]。
- **測試**：`TestModel` / `FunctionModel` + `Agent.override(...)` + `models.ALLOW_MODEL_REQUESTS = False`，不需要攔 HTTP [34]。這**部分削弱 [P3] 的論點**：[P3] 反對用官方 SDK 的理由之一是 `respx` 攔不到 `httpx2`；用 pydantic-ai 時單元測試可以完全不碰 HTTP（只有 provider 層的契約測試仍需要處理）。[P3] 的其他理由（內建重試與 brief「provider 失敗交給人」相反、錯誤要自己分類）對 pydantic-ai 是否成立，我沒有查它的重試設定，**未驗證**。
- **持久化 / durable**：官方 durable execution 走 Temporal、DBOS、Prefect；harness 的 `pgtask`、`Absurd` 需要 Postgres [32]。SQLite 沒有現成 durable engine；但 deferred tools 的「結束 run、存訊息、之後帶結果恢復」本身就是一種手動 durability，不需要引擎。
- **ag-ui extra 的版本落差**：`pydantic-ai-slim[ag-ui]` 要求 `ag-ui-protocol<1,>=0.1.10`，而 AG-UI 1.0 已於 2026-09-17（PyPI `ag-ui-protocol` 1.0.0）與 2026-09-30（規格）釋出 [19][49]。用 AG-UI 路線前要確認這個落差（Vercel 路線不受影響）。
- 多 provider：extras 涵蓋 anthropic、openai、google、groq、mistral、bedrock、openrouter、xai、cerebras、huggingface 等 [19]；本地模型走 OpenAI 相容端點（Ollama、vLLM）[P2]。

### 2.5 OpenAI Agents SDK（Python）

- MIT、0.24.0（2026-10-15）、30,305 star [19][47]。仍是 0.x。
- Human-in-the-loop：工具 `needs_approval`（bool 或 callable），run 暫停並回傳 `interruptions`，`result.to_state()` 取得**可序列化**的 `RunState`，`state.approve()` / `state.reject()` 後 `Runner.run(agent, state)` 繼續；巢狀 `Agent.as_tool()` 的核准也浮到外層 run [36]。形狀與 pydantic-ai deferred tools 同構。
- Session：`sqlalchemy` extra 等；壓縮有 `call_model_input_filter`、`session_input_callback`、opt-in 的 `ToolOutputTrimmer`，以及 **OpenAI Responses 專用**的 `OpenAIResponsesCompactionSession`（第三方整理，二手 [37]）。
- 多 provider 靠 `litellm` 或 `any-llm` extra，也就是間接帶進 LiteLLM 的風險（見 2.6）。MCP 內建（依賴 `mcp`）。基礎依賴比 pydantic-ai slim 重（`starlette`、`websockets`、`requests`、`pyjwt`）[19]。
- 本次**沒有找到**它輸出 Vercel / AG-UI 串流格式的官方 adapter。

### 2.6 LiteLLM（多 provider）

- **供應鏈事件（新發現，對自架專案是重要風險）**：2026-03 惡意版本 1.82.7、1.82.8 上了 PyPI（`.pth` 憑證竊取）[38]；2026-10-21 版本 1.107.0 在 PyPI 與官方 Docker image 約 2–3 小時，裝了 infostealer 與 RAT，約 49,000 次下載；這是 2026 年第二次 [39]。PyPI 現在的最新版標示 1.106.4（10-25），我沒有查它與 1.107.0 的版本關係。
- 重量：基礎依賴含 `boto3`、`tokenizers`、`huggingface-hub`、`tiktoken` [19]。沿用 [P2] 的判斷：不要為了多 provider 把它嵌進單一程序；要用就讓使用者自己跑 LiteLLM proxy，Berth 只打 OpenAI 相容端點。

### 2.7 其他

- LangGraph 1.2.18：有 interrupt / checkpointer 的人在迴圈模型 [47]；依賴 `langchain-core`；**本次沒有深查**，不評。
- Skills 標準：`SKILL.md`（YAML frontmatter + markdown）、漸進式揭露（啟動時只載 name + description），2025-12-18 作為開放標準發佈，宣稱 26+ 平台採用（二手整理 [56]）。pydantic-ai-harness 的 `Skills` 與 Claude Agent SDK 都支援這格式 [32]；Hermes 也宣稱相容 [15]。

### 2.8 比較表

| 面向 | Claude Agent SDK | `anthropic` 手寫 loop | pydantic-ai (+harness) | OpenAI Agents SDK | LiteLLM |
| --- | --- | --- | --- | --- | --- |
| loop 位置 | CLI 子行程 | 自己 | 行程內 | 行程內 | 不是 agent 框架，只是 provider 層 |
| 多 provider | 實質只有 Claude（靠 Anthropic 相容 gateway）| 只有 Claude；其他格式自己加（[P3]）| 是（extras）| 是（litellm / any-llm extra）| 是（核心功能）|
| 依賴重量 | wheel 116–129 MB，每 agent 約 1 GiB RAM 起跳 [21] | 輕（8 條）| 輕（slim 8 條 + extras）| 中（12 條，含 starlette、websockets）| 重，且有供應鏈事件 [39] |
| 串流 | 有（`ClaudeSDKClient`）| 自己做 SSE 解析（[P3]）| 有；`VercelAIAdapter` / `AGUIAdapter` 直接輸出 [27] | 有（`run_streamed`）| 有 |
| 工具確認 | `can_use_tool` 阻塞回呼 / hooks [24] | 自己做（manual loop）| **deferred tools**（結束 run、帶結果恢復）[26] | `needs_approval` + 可序列化 `RunState` [36] | 無 |
| 自動壓縮 | CLI 內建 + `/compact`，只能用 `PreCompact` hook 調整 | `compact-2026-*` server-side beta（Claude 專用）[25] | `ProcessHistory`、`AnthropicCompaction`、`OpenAICompaction`、harness `Compaction`（0.x）[30][31][32] | `OpenAIResponsesCompactionSession`（OpenAI 專用）[37] | 無 |
| Session 持久化 | 本機磁碟 + `SessionStore` adapter [21] | 自己 | 自己存訊息（`message_history`）| `sessions`（SQLAlchemy 等）| 無 |
| 授權 / 成熟度 | Commercial Terms，0.x | Apache-2.0，2.x | MIT，2.x（harness 0.x）| MIT，0.x | MIT（metadata），事件頻繁 |

---

## 3. MCP

### 3.1 現況（2026-10-27）

- 規格：目前版本 **2026-07-28**（2026-07-28 發佈）：stateless 協定核心、Extensions 框架、Tasks 移到官方 extension `io.modelcontextprotocol/tasks`、MCP Apps、授權強化（以 Client ID Metadata Documents 取代 Dynamic Client Registration）、正式的 12 個月 deprecation 政策 [41]。
- Python SDK：`mcp` 2.3.0（2026-10-02，MIT，24,677 star）；FastMCP 4.1.4（2026-10-26，Apache-2.0，PrefectHQ，28,212 star）[19][47]。兩者都用 `httpx2`。`mcp` v1 與 v2 有 breaking changes，**沿用 [P2]**：Streamable HTTP client 改成 `streamable_http_client(url, http_client=httpx2.AsyncClient(...))`，預設 timeout 只有 5 秒要自設。

### 3.2 把命令登錄表匯出成 MCP server

- FastMCP 官方整合文件：`mcp = FastMCP("…")`，`@mcp.tool` 註冊工具，`mcp_app = mcp.http_app(path="/")` 取得 ASGI app，`FastAPI(lifespan=mcp_app.lifespan)` 然後 `api.mount("/mcp", mcp_app)`；**必須傳 lifespan**，否則 Streamable HTTP 的 session manager 不會初始化 [42]。Berth 已經是 FastAPI，所以是掛一個子應用，不需要另開 port。
- `FastMCP.from_fastapi(app)` / `from_openapi(...)` 可以把 REST 路由一行轉成 MCP [42]。分析：這會把 REST API 的形狀（而不是 `Effect` 與 inverse）暴露給外部 agent，不適合；應該從命令登錄表逐一註冊。動態註冊（迴圈 `add_tool`）的 API 名稱我**沒有在本次核對**。
- 認證：FastMCP 支援 `JWTVerifier`、`OAuthProxy`、自訂 `TokenVerifier`，工具內可用 `CurrentAccessToken()` 依賴取得 `AccessToken`（含 claims）[43]。Berth 的「個人 API token」是不透明 token，應包成自訂 verifier，把 token 對到使用者與角色，使 MCP 與 web 走同一道門禁（plan §11.8 本來就要求「同一組個人 API token 與門禁」[55]）。新規格偏向 OAuth + CIMD，與本機 / LAN 的「貼一個 token」不同；兩條路的支援度要看 client（Claude Code、Claude Desktop）各自實作，本次沒有逐一驗證。

### 3.3 Tool annotations 對應 read / reversible / irreversible

規格與 SDK 文件 [40][22]：`readOnlyHint`（預設 false）、`destructiveHint`（預設 true）、`idempotentHint`（預設 false）、`openWorldHint`（預設 true）；「For trust & safety and security, clients MUST consider tool annotations to be untrusted unless they come from trusted servers」[40]；「Annotations are metadata, not enforcement」[22]。

| Berth `Effect` | 建議註解（分析）| 意義 |
| --- | --- | --- |
| `READ` | `readOnlyHint: true`，`idempotentHint: true` | client 可平行呼叫、可自動核准 |
| `REVERSIBLE` | `readOnlyHint: false`，`destructiveHint: false`；有 inverse 的另外在 description 或 `_meta` 寫出反向命令名稱 | client 可能仍會詢問，但 Berth 允許直接執行並提供撤銷 |
| `IRREVERSIBLE` | `readOnlyHint: false`，`destructiveHint: true` | client 預期要人確認 |

**但註解不能當門禁**：規格要求 client 不信任它，client 也可能設成自動核准。所以不可逆命令經 MCP 呼叫時，伺服器端仍要做成 Proposal（回傳「已建立待確認的 proposal id」，由人在 Berth 網頁或 Discord 確認），而不是「靠 MCP client 彈窗」。這與 brief 的「永遠要人」一致。MCP 的 elicitation（server 向 client 要使用者輸入）能否用來在 MCP client 內確認，本次**沒有查**。

另外 `Effect` 只有三級，MCP 還有 `openWorldHint`（會碰外部系統）：Berth 的搜尋 indexer、TMDB 是 open world，可以標，但這不是 Berth 現有的概念。

### 3.4 內建 agent 作為 MCP client（例如 Tavily MCP）

- Tavily 提供遠端 MCP server，OAuth 為選填，也可把 API key 放 URL query（`?tavilyApiKey=`）或 `Authorization: Bearer` header；可用 `DEFAULT_PARAMETERS` header 設預設參數 [44]。分析：header 比 URL query 好（URL 會進 log）。
- pydantic-ai：`MCPToolset('<url>', http_client=...)` 加 `.approval_required()`；Claude Agent SDK：`mcp_servers`；OpenAI Agents SDK：內建 MCP；nanobot：`MCPProvider` + 共用 `ToolRegistry` [35][22][36][18]。
- **沿用 [P2] 的風險清單**：stdio = 在容器內執行使用者填的指令（RCE 同級）；工具描述與回傳內容是 prompt injection 入口；子行程繼承環境變數；SSRF；工具清單動態變動會破壞 prompt cache 前綴；MCP 工具預設視為「會改狀態」。建議的最小版：只支援 Streamable HTTP、預設關閉、管理員新增、固定工具 allowlist [P2 §5.3]。
- 搜尋這件事本身，Tavily REST API 與 Tavily MCP 的選擇：MCP 多一層協定與動態工具清單，REST 工具可以由 Berth 自己包成一個固定的 `web_search` 工具，註冊時就是登錄表的一員（`READ`）。這是分析，不是查得的事實。

### 3.5 比較表

| 項目 | 事實 / 分析 |
| --- | --- |
| 規格版本 | 2026-07-28 [41] |
| Python server SDK | FastMCP 4.1.4（Apache-2.0）；官方 `mcp` 2.3.0（MIT）[19] |
| 掛進既有 FastAPI | `mount` + 傳 lifespan [42] |
| 認證 | 自訂 `TokenVerifier` 可對到 Berth 個人 token；規格方向是 OAuth + CIMD [41][43] |
| 註解 → Effect | 可對應，但 client 必須視為不可信 [40]；門禁必須在伺服器 |
| client 端 | pydantic-ai `MCPToolset` + `approval_required()`；風險沿用 [P2] |

---

## 4. 串流對話 UI（React 19 + TanStack）

### 4.1 候選方案（npm registry，2026-10-27）[48]

| 方案 | 版本 / 授權 | 與 Berth 前端的相容性 | 後端需要什麼 | 人在迴圈 / 卡片 |
| --- | --- | --- | --- | --- |
| **AI SDK UI**（`ai` 7.0.154、`@ai-sdk/react` 4.0.158，Apache-2.0，Vercel）| React `^19.2.1` 在 peer 範圍內 | SSE，每個事件一個 JSON part，結尾 `data: [DONE]`；自訂後端（FastAPI）**必須**回 header `x-vercel-ai-ui-message-stream: v1` [46][57] | `tool-input-available`、`tool-approval-request`（帶 `approvalId`、`reason`、`approvalDescriptor`）、`tool-approval-response`、`tool-output-available` 等 part；`useChat` 的 `addToolApprovalResponse`；AI Elements 有現成 `Confirmation` 元件（pydantic-ai 文件所述）[46][27]。AI SDK 7 的 changelog：工具核准邏輯移到 `toolApproval`、UI 訊息支援自動核准回應與核准重播 [45] |
| **assistant-ui**（`@assistant-ui/react` 0.15.31，MIT，12,762 star）| peer `react ^18 \|\| ^19`；依賴 `radix-ui`、`zustand`、`zod` | 後端 runtime 選項：`LocalRuntime`（簡單 fetch）、`ExternalStoreRuntime`（訊息放在 redux / zustand / **tanstack-query**）、`DataStream`（後端吐 data stream protocol）、`AssistantTransport`（後端吐 agent state 快照）；也有 AI SDK 的 adapter（`@assistant-ui/react-ai-sdk` 1.4.20）[50][48] | 提供 thread、composer、tool UI 元件；0.x |
| **TanStack AI**（`@tanstack/ai` 1.0.0，2026-10-22，MIT）| `@tanstack/ai-react` peer `react>=18`；與 Berth 已用的 Router / Query 同一個生態 | `useChat({ connection: fetchServerSentEvents('/api/chat') })`；事件基於 AG-UI；1.0 把 `addToolApprovalResponse()` 移除，改成直接解決 tool-approval interrupt [48] | 伺服器端函式庫是 TS；Python 後端要自己吐 AG-UI 事件（可考慮 pydantic-ai `AGUIAdapter`，**端到端未驗證**）；**才發布 5 天**，另有實驗性的 `@tanstack/ai-harness` |
| **AG-UI + CopilotKit**（`@copilotkit/react-core` 1.80.0，MIT，38,252 star；`@ag-ui/client` 1.0.3；AG-UI 規格 1.0 於 2026-09-30）| React `^18 \|\| ^19` | AG-UI 的 JSON Schema 生成 TS / Python / .NET SDK；1.0 新增 human-in-the-loop interrupts [49]；Python 有 `ag-ui-protocol` 1.0.0 與 `copilotkit` 0.1.96（依賴 langgraph / langchain）[19] | CopilotKit 全套帶 UI 元件與雲端導向的產品；`@ag-ui/client` 只是協定客戶端 |
| **自己做**（`sse-starlette` 已是依賴）| — | 事件 schema 與 React 元件都要自己寫（含 markdown 渲染、tool 狀態、重連、取消、i18n）| 無額外依賴 | 完全自訂 |

### 4.2 Python 後端怎麼接

- 最短路徑（若用 pydantic-ai）：`VercelAIAdapter.dispatch_request(request, agent=agent, sdk_version=7)` 一個 FastAPI 路由就吐出符合 AI SDK UI 的 SSE 與核准 chunk [27][28]。
- 若自寫 loop：照 data stream protocol 的 part 格式手動吐 SSE（格式見 [46]：`data: {"type":"tool-approval-request",...}`），`sse-starlette` 可用。
- Vercel 協定的演進是風險：v5 → v6（核准）→ v7（pydantic-ai 說 v7 與 v6 同線格式）[28]；開源社群有 v6 beta 期間的核准流程 bug（`no tool invocation found`，issue #10196），已有後續修補 PR [46 的搜尋結果]。
- **Generative UI 卡片**：在 AI SDK 路線上，卡片 = 依 tool part 的名稱與狀態 render 不同元件（`input-available` 顯示參數、`approval-requested` 顯示確認卡、`output-available` 顯示結果）。分析：Berth 的確認卡內容必須由伺服器依實際參數產生（沿用 [P1] 建議 4），不要讓模型自己寫描述，而這在任何路線上都一樣。
- 核准的權威：AI SDK 協定的核准回應是「隨下一個請求帶回」，pydantic-ai 明說是信任 request 的 [27]；Berth 若要「Discord 與網頁都能按同一張卡」，權威必須是 `proposals` 列，前端的 `addToolApprovalResponse` 只是其中一個觸發點。

### 4.3 比較

| 面向 | AI SDK UI | assistant-ui | TanStack AI | AG-UI / CopilotKit | 自己做 |
| --- | --- | --- | --- | --- | --- |
| 成熟度 | 最成熟，但每個大版本都改協定 | 0.x | 1.0 剛發佈 | 規格 1.0，框架大 | — |
| Python 後端現成度 | 高（pydantic-ai adapter 到 sdk 7）| 中（DataStream / AI SDK adapter）| 低 | 中（需注意 pydantic-ai ag-ui extra 版本落差）| 無 |
| 和 Berth 前端棧一致 | 中（不衝突，但風格獨立）| 中（可用 TanStack Query 當 store）| **高** | 低（帶自己的 UI 與雲端導向）| 高 |
| 新增前端依賴 | `ai`、`@ai-sdk/react`（+ swr 等）| `@assistant-ui/react`（+ radix、zustand）| `@tanstack/ai`、`ai-react` | `@ag-ui/client` 或 CopilotKit 全套 | 無 |
| 確認卡 | 協定原生 + `Confirmation` 元件 | tool UI 元件 | interrupt | interrupt | 自己畫 |

---

## 5. 多頻道（Discord）

### 5.1 一個核心服務多個表面

- openclaw：單一 Gateway 擁有所有表面；回覆固定回到來源頻道；`webchat` 是內部頻道；session key 決定 context bucket 與併發；DM 預設收斂成一個 main session，可改 per-peer / per-channel-peer [6][P1]。
- nanoclaw：`users → messaging groups → agent groups → sessions`，`supportsThreads` 決定粒度（Discord / Slack 一個 thread 一個 session，Telegram / WhatsApp 丟掉 thread id）；`ChannelAdapter` 只有約 6 個必要方法（`setup/teardown/isConnected/deliver` 與可選項）[P1]。
- nanobot：channel ↔ `MessageBus` ↔ `AgentLoop`，WebUI 本身就是一個 websocket channel，與 Telegram / Discord 平起平坐 [18]。
- Hermes：gateway + `COMMAND_REGISTRY` 共用於 CLI 與所有平台 [16]。
- 沿用 [P1]：在 Berth 現有 Discord 通知 adapter 上補 `deliver(target, message[card+actions])`、`on_interaction`、`supports_threads`，側面板當內部頻道。分析：關鍵不變量只有兩個，**核心只吐「結構化事件」（文字增量、工具呼叫、proposal 卡），各表面自己負責降級渲染**；**使用者身分與角色在核心之前就解析好**。

### 5.2 Discord 的具體限制

- 互動逾時（**修正使用者的描述**）：互動 token 有效 15 分鐘，**但必須在 3 秒內給初始回應，否則 token 作廢**；15 分鐘是 follow-up / 編輯原始回應的視窗 [52]。按鈕本身不會過期：discord.py 的 persistent view 條件是 View `timeout=None` 且每個 item 都有 `custom_id`（≤100 字元），重啟後仍可用；`DynamicItem` 可以把狀態編進 `custom_id`（用 regex 解析）[53]。分析：確認卡的 `custom_id` 放一個伺服器產生的 proposal id + 一次性 nonce，點擊時 (a) 立即 `defer` 或 update 回應（3 秒內）、(b) 驗證點擊者是不是綁定的 Berth 使用者且有權限、(c) 檢查 proposal 還沒過期 / 被處理、(d) 執行命令、(e) 編輯原訊息停用按鈕。卡片的有效期因此由 Berth 的 `proposals.expires_at` 決定，不由 Discord 決定。
- 訊息：`content` ≤ 2,000 字元；每則最多 10 個 embed、所有 embed 文字合計 ≤ 6,000（brief §20.23 實測過）；按鈕一個 Action Row 最多 5 個；Components V2 一旦設定無法移除，且該訊息就不能再有 `content` / `embeds`（沿用 [P2]）。
- 收訊息：與 bot 的 DM 內容**不需要** `MESSAGE_CONTENT` privileged intent（沿用 [P2]）。pi-chat 的伺服器頻道版本需要 [14]，因為它讀一般頻道訊息；Berth 若限定私訊與 @mention 就不需要。
- 串流輸出：nanoclaw（"streaming via post+edit"）與 pi-chat（"streamed preview with edit-in-place"）都用編輯訊息模擬串流 [3][14]。編輯的速率限制我**沒有查**；[P2] 建議保守做法是回答完整後一次送出、長回答切成多則。
- 持續連線：發通知只是 REST；要收訊息與按鈕必須跑 gateway websocket，是一個新的長連線（重連、heartbeat、resume）[55]。

### 5.3 Python 函式庫現況

| 函式庫 | 版本（日期）| 維護訊號 |
| --- | --- | --- |
| `discord.py` | 2.7.1（2026-03-03），MIT，aiohttp 依賴 | GitHub master 最近 commit 2026-09-01（修 gateway 500 重連），16,202 star；**距上個 release 近 8 個月**，但 commit 持續 [54][19] |
| `py-cord` | 2.8.1（2026-07-25），MIT，Python >=3.10 | 2,963 star，最近 push 2026-10-26 [19][47] |
| `hikari` | 2.7.0（2026-10-25），MIT，Python >=3.11 | 本次未查細節 [19] |
| `disnake` | 2.12.2（2026-10-08），MIT | 本次未查細節 [19] |

discord.py 2.x 有 View / Button、persistent view、`DynamicItem`、Components V2 的 `LayoutView`（2025-08 起加入 commit 紀錄）[53]。**沿用 [P2] 的建議**：用 `discord.py`，不手刻 gateway；新增 `aiohttp` 依賴。

### 5.4 比較

| 面向 | 做法 | 備註 |
| --- | --- | --- |
| 核心 ↔ 表面 | bus / 事件流（nanobot）、小 adapter 介面（nanoclaw）| openclaw 的大契約不適合 |
| 身分 | Discord user id ↔ Berth 使用者（M4 已存）+ 角色 | 陌生發送者預設丟棄（nanoclaw `unknown_sender_policy`）|
| 確認卡 | embed（伺服器產生）+ 按鈕（proposal id + nonce）+ 文字備援 `/approve <id>` | 能力宣告，不要假設（openclaw issue [9]）|
| 斜線指令 | 文字 `/compact` 在 host 先攔截；是否另註冊 Discord application command 是 UX 選擇 | Hermes / nanoclaw 都用文字攔截 |
| 串流 | post + edit 或整段送出 | 編輯限速未查 |

---

## 6. 自己做 claw 的難處

難度是我的判斷（低 / 中 / 高），「現成」欄是查得的套件。

| 項目 | 難度 | 難在哪 | 現成套件 |
| --- | --- | --- | --- |
| **Agent loop** | 低–中 | loop 本身很小；難在 provider 差異（工具參數是物件還是 JSON 字串）、串流下的 tool-call 組裝、錯誤分類（串流中途 overloaded 是 HTTP 200）、取消、終止條件、`tool_choice` 限制，[P3] 已經逐項列出 | pydantic-ai；`anthropic` tool runner（beta）；OpenAI Agents SDK |
| **上下文壓縮** | 中 | 摘要本身簡單；難在 (a) 切點保持 tool call / result 成對；(b) 失敗保留原歷史、拒收被截斷的摘要；(c) 待確認的 proposal id 不能被壓縮掉；(d) 壓縮後規則重申；(e) 壓縮破壞 prompt cache 前綴；(f) 壓縮請求本身要關 cache 寫入（pi）；(g) Anthropic thinking block 綁定前綴的 append-only 約束（沿用 [P2]）| Anthropic server-side compaction（Claude 專用）；`AnthropicCompaction` / `OpenAICompaction`；harness `Compaction`（0.x，model-agnostic）；openclaw 的摘要 prompt 與段落可抄 |
| **串流 UI** | 中 | 訊息 part 模型、tool 狀態機、重連續傳、取消、markdown 渲染、a11y、i18n（zh-Hant + en）、手機版面；這些是長尾 | AI SDK UI、assistant-ui、TanStack AI、CopilotKit（見第 4 節）|
| **工具權限 / 確認** | **中–高** | 不是 UI 問題而是狀態機：pending 持久化、過期、參數綁定（核准後不能換參數）、誰能按、重放保護、多表面一致、重啟存活、拒絕理由回給 agent。Berth 的 `Effect` / inverse 已經解決「分類」，缺的是 Proposal 這一層與登錄表 | pydantic-ai deferred tools（資料形狀）；OpenAI `RunState`；harness `ApprovalReviewer`（用模型自動放行低風險；Berth 的準則是 `Effect`，不是模型判斷）|
| **多頻道** | 中 | Discord 單一頻道低–中；難在身分映射、卡片降級、長度切分、互動 3 秒 / 15 分鐘、gateway 長連線管理。**沒有 Python 的現成頻道抽象層**（Chat SDK 是 TS）| `discord.py` / `py-cord` / `hikari`；nanobot 的 channel package 設計可參考 |
| **Session 持久化** | 低–中 | SQLite 存訊息 part 不難；難在 schema 演進、與壓縮共存（原始歷史保留、視圖改變）、thinking / preserved block 的原樣回傳、cache 前綴穩定 | pydantic-ai 的 `message_history`（序列化方式本次未驗證）；OpenAI `sessions`；Claude `SessionStore` |
| **斜線指令** | 低 | 一份中央 registry、host 端攔截、角色門禁；陷阱是「只有人類訊息開頭的 `/` 才算」| 無需套件；Hermes `COMMAND_REGISTRY` 與 nanoclaw `command-gate` 當範本 |
| **Skills** | 低–中 | `SKILL.md` 載入器 + 漸進式揭露（system prompt 只放 name + description，需要時用唯讀工具載 body）；風險是 skill 變成執行入口，Berth v1 只做純指令型 | harness `Skills`；agentskills 規格 [56] |
| **預算 / 失控防護 / 可觀測性** | 中 | 每 run 上限、重複偵測、費用記帳、cache 命中率（沿用 [P1] §5.1 第 10、12 點）| `UsageLimits`、harness `Spend Limits`、`Warn On Cache Busts` |
| **不可信內容（注入）** | 中 | RSS 標題、種子名稱、字幕組備註都進模型；能力邊界優先、內容標記為輔（沿用 [P1]）| harness `Prompt Injection Defender` / `Guardrails`（0.x）|
| **背景任務 + 影子模式** | 中 | `ai_worker`、資料包、驗證、影子記錄與一致率統計；這部分沒有現成物 | — |

一個值得記下的結構性觀察（**分析**）：pydantic-ai 的 deferred tools 讓「所有工具都 `requires_approval`、run 以 `DeferredToolRequests` 結束」成為**影子模式的天然形狀**——run 的輸出就是「AI 會怎麼做」，不執行即可記錄、之後與人的決定比對。這個形狀在 `can_use_tool` 阻塞式模型裡要另外模擬。

---

## 7. 對三種架構的含意

先說前提：三種架構共用同一個地基——**命令登錄表 + Proposal 表 + 使用者身分 / 角色門禁**。這三者不管選哪條都要做（plan §11.6 已列），差別只在上面接什麼。

### 7.1 A. Berth 內建 agent

A 又分三個實作選項：

- **A1 自寫 loop**（直接用 httpx，[P3] 的結論）：依賴最少、完全掌控；要自己做 SSE 解析、兩種 provider 格式、壓縮、核准恢復、UI 協定。
- **A2 以 pydantic-ai 為 loop**（slim + extras）：核准形狀（deferred tools）、Vercel / AG-UI adapter、`ProcessHistory`、`UsageLimits`、MCP client、測試用 `TestModel` 現成；要自己補 Proposal 表、頻道、壓縮策略的細節（或用 harness 0.x）。多 provider 免費。
- **A3 以 Claude Agent SDK 為 loop**：壓縮、skills、MCP、斜線指令、subagent 都是 Claude Code 現成的；代價是 116–129 MB wheel、每 agent 約 1 GiB RAM、只有 Claude、核准是阻塞回呼、session 檔在磁碟、Commercial Terms 的適用性待確認。nanoclaw 走這條，但它有容器隔離撐腰 [2][21]。

### 7.2 B. 只提供 MCP server / CLI + skills 給外部 agent

Berth 只做 FastMCP 掛載、個人 token 認證、skills 文件，使用者用 Claude Code / Codex / pi / openclaw / Hermes / nanobot 去操作。這些外部 agent 本身就有 MCP client 與 skills（openclaw `mcp.servers` [P1]、nanobot [18]、pi 有 `mcp.md` 與 `skills.md` [11]、Hermes 有 optional-mcps / agentskills.io [15]）。

### 7.3 C. 混合

登錄表同時匯出 MCP，內建輕量 agent 處理背景任務與側面板。這就是 brief/plan 目前寫的 M5–M7 形狀 [55]。

### 7.4 比較

| 面向 | A 內建 | B 只提供 MCP/CLI + skills | C 混合 |
| --- | --- | --- | --- |
| **實作難度** | 高。A2 比 A1 低很多；A3 在壓縮 / skills 上最省，但把 Claude Code 當依賴 | **最低**：FastMCP 掛載 + token verifier + 把登錄表轉成工具；真正的工作量在登錄表（A、B、C 都要）| A + B 的總和，但 B 的增量很小（登錄表已存在）|
| **維護成本** | 持續追 SDK 與協定（pydantic-ai 2.x 每週版、Vercel AI SDK 大版本改協定、provider 價格 / 參數變動，例如 2026-10-21 起 `temperature` 回 400 [P2]）| 追 MCP 規格（2026-07-28 剛大改）與 `mcp` / `fastmcp` 大版本；其餘由外部 agent 的維護者承擔 | A 的成本 + B 的成本 |
| **使用體驗** | 側面板在 Berth 裡、卡片與頁面脈絡整合、使用者不需另外裝任何 agent | **沒有側面板**（使用者要求 (2) 不成立）；體驗取決於使用者選的 agent，Berth 不控制；對已有 Claude Code 的進階使用者很好 | 最完整：進階使用者可自帶 agent，一般使用者用內建 |
| **背景 AI 接管人工審核點與影子模式** | 可行：`ai_worker` 在行程內、工具集可收窄、deferred 形狀天然適合影子記錄 | **做不到**（分析）：背景任務要有常駐的 AI 觸發者；外部 agent 要人手動或另外排程叫起，且 Berth 看不到「AI 本來會怎麼做」的影子，除非每個呼叫都經過 Berth 的 shadow 模式 | 可行，同 A |
| **Discord** | 需自己做 gateway client、身分映射、卡片、斜線指令（第 5 節）| 不由 Berth 提供；但使用者可以讓 openclaw / Hermes / nanobot（它們本身有 Discord 頻道）掛 Berth 的 MCP，得到 Discord 對話而 Berth 不寫頻道碼（代價：體驗與核准流程由那個 agent 決定；卡片按鈕是它的、不是 Berth 的 Proposal 卡）| 內建 Discord 對話走同一個核心與 Proposal；另外也允許外部 agent |
| **安全性** | 能力邊界由登錄表決定，agent 沒有 shell / 檔案；風險在不可信內容進模型、費用失控、Proposal 繞過（需整合測試）| **風險面最大**：外部 agent 帶它自己的 shell / 檔案工具與提示詞注入面，Berth 只能守好伺服器端門禁；註解不可信 [40]，不可逆命令必須在伺服器做成 Proposal；MCP 暴露在 LAN 的 token 管理 | 兩者的風險都在，但內建 agent 的工具集可以比 MCP 窄；同一道門禁 |

### 7.5 我的看法（事實導向，不是最終推薦）

1. **B 單獨不能滿足三個需求中的兩個**（側面板、背景接管），它只能當附加項目。這不是品質問題，是它沒有 Berth 自己的 UI 與常駐觸發者。
2. **C 的增量成本在 B 這側很小**，因為登錄表與門禁本來就要做；真正決定工作量的是 A 用什麼 loop。所以架構問題其實可以收斂成「A1 / A2 / A3 選哪個」，C 與 B 是在它旁邊加一個薄層。
3. **A3（Claude Agent SDK）是三個內建選項裡與 Berth 約束最不合的**：116–129 MB wheel、每 agent 約 1 GiB RAM 起跳、只有 Claude、核准是阻塞式、session 檔在磁碟要靠 `SessionStore` 鏡像；它的優勢（壓縮、skills、`/compact`、MCP）在 A2 + harness 與自寫之間也補得起來，只是要自己寫或用 0.x 套件。
4. **A2 是目前查到唯一同時提供「deferred 核准 + Vercel/AG-UI adapter + 多 provider + MCP client + 不用 HTTP 的測試」的函式庫**，且 SQLite 友善（不需要 Postgres durable engine）。代價是 harness 還是 0.x、`ag-ui` extra 的版本落差、httpx2 並存、以及你要把自己的 Proposal 表接在 `DeferredToolRequests` 後面。這些都是**未實測**的整合風險。
5. **A1（自寫）仍然成立**：[P3] 的理由大部分（內建重試與 brief 衝突、httpx2/respx、錯誤自己分類）對 `anthropic` / `openai` 官方 SDK 成立；對 pydantic-ai 的重試設定我沒查。自寫的主要成本會落在壓縮、UI 協定與核准恢復，這三項正好是 A2 現成的。
6. **LiteLLM 不建議進單一程序**：兩次供應鏈事件（2026-03 與 2026-10-21）加上重依賴 [38][39]。
7. **UI 協定先選 Vercel data stream（經 pydantic-ai adapter）或自己做 SSE，AG-UI / TanStack AI 剛 1.0**，兩者都才幾天到幾週；TanStack AI 與 Berth 前端棧一致是吸引力，但沒有 Python 端的端到端證據。這是時間點問題，一兩個月後再看會比較穩。
8. **Discord 的真正工作是身分、卡片與 gateway 長連線**，不是 LLM。這部分不管 A/B/C 內建與否都由 Berth 的 channel adapter 承擔；若走 B，等於把這件事外包給使用者選的 claw。

### 7.6 動工前建議的最小驗證（沿用 [P1][P2][P3] 並增補）

1. pydantic-ai：deferred tools → 寫入 `proposals` 列 → 從另一個請求帶 `DeferredToolResults` 恢復，確認 `message_history` 序列化可存 SQLite。（新）
2. pydantic-ai 的 `VercelAIAdapter(sdk_version=7)` + `@ai-sdk/react` 4.x 端到端跑一次核准卡。（新）
3. pydantic-ai 的重試 / 錯誤分類是否符合 brief「provider 失敗交給人」。（新，[P3] 反對 SDK 的理由之一）
4. Anthropic prompt cache 在 pydantic-ai 下的命中率（沿用 [P1] 待驗證 (a)）。
5. FastMCP 從登錄表動態註冊工具、自訂 token verifier 對到 Berth 個人 token。（新）
6. Discord 確認卡：`DynamicItem` 的 `custom_id` 帶 proposal id、重啟後仍可點、3 秒內 ack。（新）

---

## 8. 沿用與新查 / 修正對照

| 主題 | 沿用 | 新查或修正 |
| --- | --- | --- |
| nanoclaw / openclaw 原始碼層行為 | [P1] 全部沿用（斜線指令清單、壓縮、迴圈偵測、注入防護、`ChannelAdapter` / `ChannelPlugin`）| 重驗規模與 release；補 nanoclaw Chat SDK 能力表 [3]、openclaw approver 授權與兩個 issue [8][9][10] |
| 其他 claw | — | 新增 pi（含 pi-chat、compaction 細節）、Hermes Agent、nanobot；zeroclaw / picoclaw / ironclaw 只記規模 |
| Claude Agent SDK | [P1][P2]：子行程、權限回呼、授權、單一 provider | **修正**：[P2]「未明說是否需要 Node」→ 官方 hosting 頁明說隨附原生執行檔、不需另裝 Node；新增資源建議（1 GiB/agent）、`tools: []`、`SessionStore`、wheel 大小逐平台數字 |
| Anthropic SDK | [P2][P3] 全部 | 補 `compact-2026-09-04` 與 tool runner 的 `compact_before_next_turn()`、2.0 移除 client-side compaction_control [25] |
| pydantic-ai | [P1] deferred tools、`ProcessHistory`、`UsageLimits`；[P2] 版本 | **修正** [P2] 的「未驗證 human-in-the-loop」；新增 Vercel/AG-UI adapter（含 sdk 5/6/7）、`AnthropicCompaction`、harness（Compaction、Approval Reviewer、Skills、Spend Limits…）、`TestModel`、MCPToolset、`ag-ui` extra 版本落差 |
| 測試策略 | [P3]：respx 攔不到 httpx2 | 補：pydantic-ai 路線不需攔 HTTP（`TestModel` / `FunctionModel`），削弱該論點的一部分 |
| OpenAI Agents SDK | — | 新增 |
| LiteLLM | [P2]：依賴重 | 新增兩次供應鏈事件、`openai<3` 衝突 |
| MCP | [P2]：client、風險清單 | 新增規格 2026-07-28、FastMCP 4.1.4、掛進 FastAPI、認證、註解對應、Tavily MCP 認證方式 |
| 串流 UI | — | 全新（AI SDK 7、assistant-ui、TanStack AI 1.0、AG-UI 1.0、CopilotKit）|
| Discord | [P2]：長度、intent、discord.py 2.7.1 | **修正**：互動「逾時 15 分鐘」→ 3 秒 ack + 15 分鐘 token；按鈕不過期；補 persistent view / `DynamicItem`、discord.py 近況（最近 commit 2026-09-01）、替代函式庫 |

---

## 來源

查證日期皆為 2026-10-27，除非另註。

**本 repo**
- [55] `/Users/roxy/orca/projects/Berth/docs/design-brief.md` §14、§16.2、§20.23；`docs/plan.md` §11.6–11.8；`web/package.json`；`pyproject.toml`；`berth/services/commands.py`（2026-10-27 讀）
- [P1] `git show bk:docs/research/claw-references.md`（2026-10-26）
- [P2] `git show bk:docs/research/ai-provider-and-tools.md`（2026-10-26）
- [P3] `git show backup/m5-attempt-1-20261024:docs/research/ai-providers.md` 與 `ai-providers/anthropic.md`、`ai-providers/openai-compatible.md`（2026-10-24）

**claw 類專案**
- [1] https://github.com/nanocoai/nanoclaw （GitHub API：star、license、pushed_at、release `v2026.10.0`）
- [2] https://github.com/nanocoai/nanoclaw/blob/main/README.md
- [3] https://github.com/nanocoai/nanoclaw/blob/main/docs/architecture.md
- [4] https://github.com/nanocoai/nanoclaw/blob/main/docs/SECURITY.md
- [5] https://github.com/openclaw/openclaw （README；GitHub API：393,155 star、`v2026.10.7`）
- [6] https://docs.openclaw.ai/concepts/architecture
- [7] https://docs.openclaw.ai/tools/slash-commands
- [8] https://docs.openclaw.ai/tools/exec-approvals-advanced
- [9] https://github.com/openclaw/openclaw/issues/134982
- [10] https://github.com/openclaw/openclaw/issues/28753
- [11] https://github.com/earendil-works/pi （README；GitHub API）
- [12] https://github.com/earendil-works/pi/blob/main/packages/agent/README.md
- [13] https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/compaction.md
- [14] https://github.com/earendil-works/pi-chat
- [15] https://github.com/NousResearch/hermes-agent （README；GitHub API）
- [16] https://github.com/NousResearch/hermes-agent/blob/main/website/docs/developer-guide/architecture.md
- [17] https://github.com/HKUDS/nanobot （README；GitHub API）
- [18] https://github.com/HKUDS/nanobot/blob/main/docs/architecture.md

**套件與 SDK**
- [19] PyPI JSON API：`https://pypi.org/pypi/<package>/json`，套件 claude-agent-sdk、pydantic-ai-slim、pydantic-ai-harness、openai-agents、mcp、fastmcp、discord.py、py-cord、litellm、ag-ui-protocol、copilotkit、anthropic、sse-starlette、hikari、disnake、langgraph、nanobot-ai、hermes-agent
- [20] https://github.com/anthropics/claude-agent-sdk-python （README，含 License and terms）
- [21] https://code.claude.com/docs/en/agent-sdk/hosting
- [22] https://code.claude.com/docs/en/agent-sdk/custom-tools
- [23] https://code.claude.com/docs/en/agent-sdk/overview
- [24] https://code.claude.com/docs/en/agent-sdk/permissions ；https://code.claude.com/docs/en/agent-sdk/sessions
- [25] https://github.com/anthropics/anthropic-sdk-python/blob/main/tools.md ；https://github.com/anthropics/anthropic-sdk-python/blob/main/MIGRATION.md ；https://github.com/anthropics/claude-code/issues/19686 ；https://github.com/anthropics/claude-agent-sdk-python/issues/581
- [26] https://pydantic.dev/docs/ai/tools-toolsets/deferred-tools ；https://pydantic.dev/docs/ai/capabilities/handle-deferred-tool-calls
- [27] https://pydantic.dev/docs/ai/integrations/ui/vercel-ai/
- [28] https://github.com/pydantic/pydantic-ai/blob/main/pydantic_ai_slim/pydantic_ai/ui/vercel_ai/_adapter.py （`sdk_version: Literal[5, 6, 7]`，第 198–202 行）
- [29] https://pydantic.dev/docs/ai/integrations/ui/overview/ ；https://pydantic.dev/docs/ai/integrations/ui/ag-ui/
- [30] https://pydantic.dev/docs/ai/core-concepts/message-history/
- [31] https://pydantic.dev/docs/ai/models/anthropic/ ；https://pydantic.dev/docs/ai/models/openai/
- [32] https://pydantic.dev/docs/ai/harness ；https://github.com/pydantic/pydantic-ai-harness
- [33] https://pydantic.dev/docs/ai/harness/approval-reviewer ；https://pydantic.dev/docs/ai/harness/guardrails
- [34] https://pydantic.dev/docs/ai/guides/testing/
- [35] https://pydantic.dev/docs/ai/mcp/client/
- [36] https://openai.github.io/openai-agents-python/human_in_the_loop ；https://openai.github.io/openai-agents-python/results
- [37] （二手）https://github.com/woaitqs/repo-research/blob/main/research/openai-agents-python.md
- [38] https://docs.litellm.ai/blog/security-update-march-2026 ；https://success.trendmicro.com/en-US/solution/KA-0022880
- [39] https://securitylabs.datadoghq.com/articles/litellm-compromised-pypi-docker ；https://www.securityweek.com/litellm-compromised-in-fresh-supply-chain-attack

**MCP**
- [40] https://modelcontextprotocol.io/specification/latest/server/tools
- [41] https://blog.modelcontextprotocol.io/posts/2026-07-28 ；https://modelcontextprotocol.io/specification/2026-07-28/changelog
- [42] https://github.com/prefecthq/fastmcp/blob/v4.1.3/docs/integrations/fastapi.mdx ；https://github.com/prefecthq/fastmcp/blob/v4.1.3/docs/deployment/http.mdx （經 context7 `/prefecthq/fastmcp/v4.1.3`）
- [43] https://github.com/prefecthq/fastmcp/blob/v4.1.3/docs/servers/auth/oauth-proxy.mdx ；https://github.com/prefecthq/fastmcp/blob/v4.1.3/docs/servers/dependency-injection.mdx
- [44] https://docs.tavily.com/documentation/mcp ；https://github.com/tavily-ai/tavily-mcp

**串流 UI**
- [45] https://vercel.com/changelog/ai-sdk-7
- [46] https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol ；https://github.com/vercel/ai/issues/10196
- [47] GitHub API `gh api repos/<owner>/<repo>`（star、pushed_at、license）與 `gh search repos`；npm 與 PyPI 版本見 [19][48]
- [48] npm registry `https://registry.npmjs.org/<package>`，套件 ai、@ai-sdk/react、@assistant-ui/react、@assistant-ui/react-ai-sdk、@copilotkit/react-core、@ag-ui/client、@ag-ui/core、@tanstack/ai、@tanstack/ai-react、chat、@chat-adapter/discord；https://tanstack.com/ai/latest/docs/getting-started/overview ；https://tanstack.com/ai/latest/docs/transports/overview ；https://daily.dev/posts/tanstack-ai-1-0-still-your-ai-still-your-way-1fy62oqsr
- [49] https://www.sitepoint.com/ag-ui-1-0-stable-spec-agent-user-interaction （二手）；https://www.copilotkit.ai/blog/series-a
- [50] https://www.assistant-ui.com/docs/runtimes/custom/overview ；https://www.assistant-ui.com/docs/runtimes/pick-a-runtime
- [57] https://www.developersdigest.tech/blog/streaming-and-generative-ui-for-agents （二手；`x-vercel-ai-ui-message-stream: v1` header 與 `[DONE]`）

**Discord**
- [52] https://docs.discord.com/developers/interactions/receiving-and-responding
- [53] https://github.com/Rapptz/discord.py/blob/master/examples/views/persistent.py ；https://github.com/Rapptz/discord.py/blob/master/examples/views/dynamic_counter.py
- [54] https://github.com/Rapptz/discord.py/commits/master （GitHub API commits，2026-09-01 最近）

**其他**
- [56] https://www.firecrawl.dev/blog/agent-skills ；https://venturebeat.com/technology/anthropic-launches-enterprise-agent-skills-and-opens-the-standard （二手；agentskills.io 規格本身未直接讀）
