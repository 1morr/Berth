# 37 — BTH 4 只支援 Prowlarr：拿掉通用 Torznab 端點

**Status:** ready-for-agent

**Blocked by:** 33（兩張都改寫 brief §16.4，33 先定好定義）

**讀:** `docs/research/wizard-audit-2026-10-06.md`（§D 全部，那張「會影響的地方」表就是清單；改進清單 P1-9）；brief §19「精靈審計後的八項」D3、§3、§16.3、§16.4、§20.7 與 §20 的 Jackett 結論；plan §4、§8.4、§9.3

## 為什麼

- **D3 拍板**：拿掉通用 Torznab 端點與 Jackett。這推翻 brief §3「只依賴 Torznab 協定、支援 Jackett」。
- Torznab 路徑本來就缺頁 4 最核心的能力：沒有站清單、不能加站、不能測站、沒有版本下限。整條 `kind` 分岔散在設定、API、services、health 與前端。
- 泊位名改成「Prowlarr」，與 Jellyfin、qBittorrent 兩格一致。

## 做什麼

1. 刪 Torznab 的 adapter（`TorznabSearch`、client、fake、caps）、`IndexerKind` 與 `kind` 欄位、services 與 health 裡的分岔、相關 fixture 與測試。
   Prowlarr 搜尋若共用 Torznab 的 session 或解析器，留它需要的那部分。
2. **資料格式是破壞性變更**（D3 已拍板）：寫一支資料 migration，把已存 `kind="torznab"` 的索引站設定清掉，讓頁 4 回到待處理。先例是 M4 的 `setup_choices` migration。
3. 前端：頁 4 與設定頁拿掉「接法」單選與 Torznab 說明；泊位名、`board.*`、`indexer.title`、完成頁等改成「Prowlarr」；約 8 對 zh-Hant / en 文案。
4. API：`IndexerConnectIn.kind` 拿掉，更新 OpenAPI 型別。CHANGELOG 記破壞性變更。
5. 文件同一個 commit 改：brief §3 表格與頂端那句、§16.4、§20 的 Jackett 結論（標「已不採用」並保留來源）；plan §4、§8.4、§9.3；README、`CONTEXT.md:122`、`PRODUCT.md`。

## 驗收

- [ ] 整合測試：存著 `torznab` 設定的資料庫跑 migration 之後，頁 4 是待處理，搜尋回「沒有設定」而不是 500
- [ ] `grep -ri torznab` 在 `berth/`、`web/src/`、`tests/` 只剩 Prowlarr 搜尋自己需要的部分，每一處在 Comments 說明為什麼留著
- [ ] 前端：精靈與設定頁沒有 Torznab 與 Jackett；泊位名是「Prowlarr」（zh-Hant 與 en）
- [ ] 文件已改；progress.md「偏差與決定」記一行
- [ ] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e、真服務 e2e 綠燈
