# 20 — 既有 Prowlarr 不再是死路：0 站不算完成、舊版說出版本、加站與介面登入分開

**Status:** done

**Blocked by:** None — can start immediately

**讀:** `docs/research/wizard-review-2026-09-30.md`；brief §20.14（Prowlarr 下限 1.3.2）、§19；plan §9.5〈Prowlarr 與索引站〉；
票 09、17 的 `## Comments`；`docs/research/prowlarr-version-floor.md`

## 為什麼（2026-09-30 精靈審查）

- **既有 Prowlarr 沒有站也標「已完成」。** 接 `ok-prowlarr`（`:48696`，0 站）→「已完成 · Prowlarr · 0」、「這一台上還沒有
  任何站」，泊位卡「已完成 · 尚未加入索引站」，可以直接往下走。零站的 Berth 什麼都搜不到；既有模式也不提供加站
  （`POST /setup/indexers/connect` 只連不加，`berth/services/indexer.py:326-379`）。
- **Prowlarr 1.0.1 說的是「連不上」。** `bad-prowlarr-old`（`:59696`）：狀態列「主機名解得到但連不上」，內文
  `http://host.docker.internal:59696/ping: response is not JSON`，手動步驟叫人查位址與 key。1.0.1 沒有 `/ping`（回 HTML），
  但它的 `/api/v1/system/status` 有正確回版本。票 17 的下限判斷在 `/ping` 之後，走不到。
- **key 錯時**：內文 `GET /api/v1/system/status: 401`，列表頭卻寫 `GET /api/v1/indexer`，狀態列還停在上一次的結果；
  票 17 Comments 已記「`probe_indexer` 失敗只分得出版本太舊與其餘（含帳密錯）」。
- **套件內加站被綁在介面登入上。** 勾了站按「加入 N 個站」→ Prowlarr 介面登入的密碼欄「這一格要填」；說明卻寫
  「不設的話，Prowlarr 第一次打開時會自己要你設一組」，看起來是選填。同一顆主按鈕沒勾站時叫「設定介面登入」、勾了叫
  「加入 N 個站」，而且在登入區塊下面，離站清單很遠。
- **既有模式的「回頭看」寫「測試並加更多公開站…移除不要的站」**，同一頁又寫「不加、不移除」；套件內剛選下去的前幾秒
  也閃過既有模式的文案。連線卡一直寫「索引站 0」，同頁卻是「已加入 2 站」；重新整理後泊位卡 BTH 4 顯示「尚未加入索引站」。

## 做什麼

1. **0 站不算完成**：既有 Prowlarr 連上但沒有站 → 這一頁停在「待處理」，說出下一步：到 Prowlarr 加站（連結用瀏覽器
   開得了的位址）後按「重新讀取」，或明確選「之後再說」（沿用現有的 skip）。**使用者 2026-09-30 拍板：可以，要按一次確認**——既有 Prowlarr 也走套件內那套「推薦站預設不勾、先測試、通過才勾、按一次
   加入」，畫面寫清楚會加進使用者的 Prowlarr、加哪幾站；移除仍交給 Prowlarr 自己的介面（不提供移除鈕）。介面登入只屬於
   套件內，既有模式不碰。
2. **舊版說出版本**：`/ping` 不是 JSON 時改讀 `/api/v1/system/status`（帶 key）取版本；低於 1.3.2 → `version_unsupported`，
   「至少 1.3.2，你的是 X」。1.0–1.3 的 `system/status` 在哪種驗證下拿得到要先查證（研究檔或對 `bad-prowlarr-old` 實測），
   補進 `docs/research/prowlarr-version-floor.md`。
3. **key 錯**：401 → `auth_required`，說「API key 不對：在 Prowlarr 的 設定 → 一般 複製」；不再是「連不上」。
4. **套件內的兩顆按鈕**：「加入 N 個站」貼著站清單、不需要介面登入；介面登入是自己的區塊與按鈕，說明寫清楚是否必填
   （照 Prowlarr 現行版本的行為查證後寫）。
5. **文案與計數**：「回頭看」依套件內／既有分開；連線卡的站數與清單一致；重新整理後泊位卡讀得到已加入的站。

## 驗收

- [x] 整合測試：既有 Prowlarr 0 站 → 這一頁不算完成（`_current_step` 停在 4）；按 skip 才往下；有站 → 完成（雙向）
- [x] 整合測試：`/ping` 回 HTML 而 `system/status` 回 1.0.1 → `version_unsupported` 帶版本；1.3.2 → 通過
- [x] 整合測試：key 錯 → `auth_required`，不是 `unreachable`
- [x] vitest：加站按鈕在沒填介面登入時可按；介面登入是獨立按鈕；「回頭看」依來源不同
- [x] 既有 Prowlarr 可以測站、勾選、按一次加入（整合測試：加的只有勾選的站、不改 `config/host`；雙向：沒按就不加），
      決定記進 progress.md「偏差與決定」
- [x] playwright 對 `berth-existing` 實跑：`bad-prowlarr-old`（`:59696`）說出版本；`ok-prowlarr`（`:48696`）0 站時停在待處理、
      加站或 skip 之後往下；附截圖或文字結果
- [x] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈

## Comments

### 實跑（2026-09-30，playwright 對 berth-existing）

受測 Berth 是從工作樹 build 的 `berth:t20-verify`，容器 `berth-t20`（`127.0.0.1:28383`，預設 bridge、自己的 config 與 data 目錄）。
頁 1、2 走 API（既有 `ok-jellyfin` 成立擁有者、既有 `ok-qbittorrent` 確認）；頁 3 在受測 Berth 的資料庫放一條綠的 Route
（不碰 berth-trial 的 `/data`）。頁 4 以 `@playwright/test` 的腳本實跑，結果：

- `bad-prowlarr-old`（`:59696`）：纜繩「失敗 · Prowlarr 1.0.1.2220 · GET /api/v1/system/status」，補法「至少要 Prowlarr 1.3.2，這一台是 1.0.1.2220；等也不會好」。
- `ok-prowlarr` 配錯的 key：「GET /api/v1/system/status: 401」，補法「API key 不對：在 Prowlarr 的『設定 → 一般』複製 API key」。
- `ok-prowlarr`（`:48696`）0 站：纜繩「尚未執行 · Prowlarr 0」、提示「待處理」＋「重新讀取」＋「開啟 Prowlarr 的索引站頁」連結（`host.docker.internal` 換成瀏覽器的主機名，vitest 守著），沒有「前往下一個泊位」；泊位卡 BTH 4「待靠泊 · 既有 · Prowlarr · 尚未加入索引站」。
- 「測試全部」：3 站沒通過（Cloudflare 2、連不上 1）、6 站通過；勾 dmhy，按鈕上方「按下去會把這 1 站加進你的 Prowlarr（host.docker.internal:48696）：dmhy。」，按「加入 1 個站」後出現「前往下一個泊位」，連線卡「索引站 1」；重新整理後泊位卡 BTH 4「已完成 · 既有 · Prowlarr · 1 個索引站」。
- 從 ok-prowlarr 移除 dmhy 後回到頁 4 按「重新讀取」：回到待處理；按「之後再說」→「前往下一個泊位」→ TMDB。
- 收尾：ok-prowlarr 還原成實測前的 0 站（`GET /api/v1/indexer` → `[]`）、撤掉受測 Berth 在 ok-jellyfin 建的 API key（204）、`berth-t20` 容器、`berth:t20-verify` image 與目錄都刪了。截圖在該 session 的 scratchpad，沒有進 repo。

### 驗證

- `uv run pre-commit run --all-files`：全部 Passed。
- pytest：3402 passed（code-review 修正之後的全套）。
- vitest：70 檔 1110 passed（新增 `BerthNav.test.tsx`）。
- 前端 e2e：全套 33 passed；code-review 修正後重 build，`wizard` / `existing` / `settings` 兩種寬度再跑一次，6 passed（`existing` 第一次是瀏覽器啟動逾時——與整套 pytest 同時跑——單獨重跑通過）。

### code-review 沒有處理的發現

- **Standards（判斷題）**：站數以字串存在 `ServiceTest.detail`（`_recount` 寫回、`setup._existing_indexer_step` 以 `int()` 讀回），同一欄位在版本太舊時放版本字串——沿用票 17 以前的形狀，沒有另開欄位。
- **Standards**：`indexer._failed_probe` 的例外 → 理由對照與 `setup._classified` 重疊一部分（後者多了 IP 封鎖、啟動中與「等」）；兩者的呼叫端要的東西不同，這一輪沒有合併。
- **Standards**：「套件內 / 既有 Prowlarr / Torznab」的判斷在前端有四處（`modeOf`、`IndexerActions`、`AddSites` 的 `existing`、`RevisitNote` 的 `origin`）；`IndexerProbe.step` 與 `.sites` 帶同一份站數。開 Prowlarr 索引站頁的連結在 `NoSites` 與 `AddSites` 各一個。
- **Spec**：既有表單那一條纜繩的端點標 `GET /api/v1/system/status`；連上時細節是站數，實際來自 `GET /api/v1/indexer`。
- **Spec**：設定頁 → 索引站對 0 站的既有 Prowlarr 只畫空的「已加入」與「加站」，沒有精靈那一塊「待處理」提示（票面只談精靈）。
