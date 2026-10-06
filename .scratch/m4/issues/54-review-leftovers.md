# 54 — code-review 遺留與過期 i18n

**Status:** ready-for-agent

**Blocked by:** 37、39（設定頁索引站與頁 4 的改動先落地）

**讀:** `docs/research/wizard-audit-2026-10-06.md`（§A3「code-review 留下沒處理的」與「過期的 i18n」）；票 15、19、26、27、31 的 `## Comments`；`PRODUCT.md`、`DESIGN.md`

## 為什麼

審計的 §A3 列了一批各票 code-review 或 audit 留下、沒有票的項目，不在改進清單裡。使用者 2026-10-06 決定另開這一張收掉。

## 做什麼

逐條處理，先確認前面的票是不是已經順手修掉；能寫出失效條件的才修（全域規則：沒有 repro 就不修）。

1. 票 19：探針 torrent 在 `finally` 刪除失敗時會留在使用者的 qBittorrent。
2. 票 26：帳號被拒，或兩次 `setPreferences` 之間斷線時，qBittorrent 會留下「原帳號＋新密碼」。
3. 票 27：設定頁索引站的 `IndexerActions` 沒跟著改（每次重讀 key、已有站算數）。
4. 票 15：audit P2——`radiogroup` 沒有名字、五處 `truncate`。
5. 票 31：媒體庫深連結對 `host.docker.internal` 的問題。
6. `jellyfin.step.*` 等沒有引用處的 i18n 鍵：刪掉，並讓 `resources.test.ts`（或同類的閘門）擋未引用的鍵；做不到就在 Comments 說明。

## 驗收

- [ ] 每一條在 Comments 有結論（已修＋測試／已由 NN 處理／不修＋理由）
- [ ] 修掉的每一條都有先紅後綠的測試
- [ ] 若加了未引用 i18n 鍵的閘門，在測試檔內做雙向變異驗證
- [ ] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈
