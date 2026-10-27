# Shape：設定頁的「AI」分頁（M5 票 09）

模式 **Operate**；全在既有的「泊位調度板」世界裡（DESIGN.md），不新增元件種類。使用者 2026-10-27 選定結構、主要動作與模型欄（三題都是建議的那一個）。

## 誰、何時、要做到什麼

- 精靈跑完之後的管理員，在桌機上做一次：手上有一把 Anthropic、OpenAI 或相容服務（DeepSeek、OpenRouter、自架閘道、本機模型）的 key，貼進來、填模型、按測試、看到「連上了」、打開 AI、儲存。之後只有換 key、換模型或測試失敗時回來。
- 成功的樣子：「測試連線」說出哪個模型回了話；失敗時說是 key 被拒、模型或網址找不到、服務出錯、連不上還是網址指錯地方，並附上服務回的原文。**沒有 AI 時 Berth 完整可用**：關著的開關是常態，不塗漆。

## 結構（由上而下，`SettingsFrame` 單欄、一張表單）

分頁列在「通知」之後加「AI」，同樣不是泊位。

1. **開關**：`Checkbox`「開啟 AI」＋一句說明（關著就沒有 AI，其餘功能照常）。
2. **接口**：兩顆 `aria-pressed` 切換鍵（`role="group"`，`NAV_BOX` / `NAV_BOX_ACTIVE`，同篩選列）：「Anthropic Messages」「OpenAI 相容」。切換時底下三欄換成那一種**存著的值**；兩種各自保存，切過去不會丟掉另一邊。
3. **連線**（選中那一種的三欄）：
   - Base URL：`Field`（`.value`，`inputMode="url"`），placeholder 是官方端點；hint 依接口：Anthropic「不含 /v1，SDK 會自己接；貼了也會拿掉」、OpenAI 相容「照那家服務文件寫的網址（OpenAI 官方含 /v1）」。
   - API key：`PasswordField`。存過時 placeholder「已設定，貼上新的就換掉」，key 原文永遠不回到瀏覽器；旁邊不放清除鍵——清除走「移除 key」Ghost（就地確認），只在有 key 時出現。
   - 模型：`Field`＋`datalist`（價目表上認得的模型，可以不選、照打）。底下一行**價目**（已存的模型）：「輸入 $2 · 輸出 $10 · 快取讀 $0.10 / 百萬 token（2026-10-27 查證）」；認不得是「價目未知：用量頁的費用會寫「未知」，不當 0」。表單改了模型還沒存時這一行說「存了之後顯示價目」。
4. **測試連線**：Ghost「測試連線」，測的是**表單上還沒存的值**（Sonarr 的 Test），key 欄空著就用存著的那一把。結果就地在鍵下（`aria-live`，那一格一直掛著）：成功是 `secured` 色塊「連上了」＋「回話的模型：`.value`」；失敗是 `blocked` 色塊＋一句人話＋補法＋`TechnicalDetails`（HTTP 狀態碼與原文）。測試不是開啟的前提。
5. **網路搜尋（選填）**：`SectionHeading`＋Tavily key 的 `PasswordField`（同樣只寫不讀）＋一句「設了之後兩種接口都多一個網路搜尋工具；Anthropic 另有自己的伺服器端搜尋」。有 key 時同樣有「移除」。
6. **儲存**：`PrimaryButton`，全頁唯一的調度黃。存選中那一種的三欄、開關、Tavily，並把選中那一種設成現在用的。拒絕（`base_url_invalid` 在 Base URL 欄下、`key_missing` 在 key 欄下、`model_missing` 在模型欄下）就地說；成功後鍵下 `role="status"` 一行「已儲存」。

## 失敗的說法（`AiProbeFailure`）

- `key_rejected`：服務不接受這把 key → 換一把，或確認它對這個網址有效。
- `not_found`：模型名或網址找不到 → 檢查模型名稱與 Base URL（Anthropic 不含 /v1）。
- `service_error`：服務回了錯誤（限流、額度、過載）→ 看原文；等一下再試。
- `unreachable`：連不上 → 檢查網址與 Berth 這台機器連不連得出去。
- `bad_response`：回的不是 API → Base URL 可能指到一個網頁。

## 狀態

讀取中、讀取失敗（`RequestFailed`）；開關開 / 關；接口兩種；key 有 / 沒有；價目認得 / 未知 / 改了沒存；測試：測試中、成功、五種失敗、被拒（缺 key、缺模型、網址不合格）；儲存：儲存中、已儲存、三種拒絕。390 寬：切換鍵兩顆並排（字短）、鍵整寬。

## 不做、留給之後

- 不在這頁教人申請 key；不列各家服務的預設網址清單（datalist 只給模型）。
- 側面板（票 12）、用量頁的費用（票 21）、Tavily 的測試（票 17）。
- 不做「測試成功才能開」的閘門（使用者選定）。
