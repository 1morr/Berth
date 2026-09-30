# 20 — 既有 Prowlarr 不再是死路：0 站不算完成、舊版說出版本、加站與介面登入分開

**Status:** ready-for-agent

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
   開得了的位址）後按「重新讀取」，或明確選「之後再說」（沿用現有的 skip）。**開工前問使用者**要不要另外讓 Berth
   替既有 Prowlarr 加推薦的公開站（這是寫入使用者的服務，與「既有不改」的原則要權衡；協調者建議：可以，但要使用者在
   畫面上按一次、清楚寫會加哪幾站，移除仍交給 Prowlarr 自己的介面）。
2. **舊版說出版本**：`/ping` 不是 JSON 時改讀 `/api/v1/system/status`（帶 key）取版本；低於 1.3.2 → `version_unsupported`，
   「至少 1.3.2，你的是 X」。1.0–1.3 的 `system/status` 在哪種驗證下拿得到要先查證（研究檔或對 `bad-prowlarr-old` 實測），
   補進 `docs/research/prowlarr-version-floor.md`。
3. **key 錯**：401 → `auth_required`，說「API key 不對：在 Prowlarr 的 設定 → 一般 複製」；不再是「連不上」。
4. **套件內的兩顆按鈕**：「加入 N 個站」貼著站清單、不需要介面登入；介面登入是自己的區塊與按鈕，說明寫清楚是否必填
   （照 Prowlarr 現行版本的行為查證後寫）。
5. **文案與計數**：「回頭看」依套件內／既有分開；連線卡的站數與清單一致；重新整理後泊位卡讀得到已加入的站。

## 驗收

- [ ] 整合測試：既有 Prowlarr 0 站 → 這一頁不算完成（`_current_step` 停在 4）；按 skip 才往下；有站 → 完成（雙向）
- [ ] 整合測試：`/ping` 回 HTML 而 `system/status` 回 1.0.1 → `version_unsupported` 帶版本；1.3.2 → 通過
- [ ] 整合測試：key 錯 → `auth_required`，不是 `unreachable`
- [ ] vitest：加站按鈕在沒填介面登入時可按；介面登入是獨立按鈕；「回頭看」依來源不同
- [ ] 使用者對「替既有 Prowlarr 加站」的決定實作並記進 progress.md「偏差與決定」
- [ ] playwright 對 `berth-existing` 實跑：`bad-prowlarr-old`（`:59696`）說出版本；`ok-prowlarr`（`:48696`）0 站時停在待處理、
      加站或 skip 之後往下；附截圖或文字結果
- [ ] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈
