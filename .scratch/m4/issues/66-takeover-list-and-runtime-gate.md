# 66 — 接管清單補齊、閘門延伸到執行期、「移除 Berth」清單

**Status:** ready-for-agent

**Blocked by:** 62（Jellyfin 掃描的範圍先定，清單才寫得準）

**讀:** `docs/research/usability-audit-2026-10-07.md` §5.3、附錄 C、§8 P1-10、P1-11；`notes/r1-code-evidence.md` §1.8、§1.9（白名單閘門的範圍與漏洞 G1–G8）；brief §16.4 物件表與閘門段；CONTEXT.md 的 Bundled / Existing service；`tests/integration/test_setup_owned_writes.py`

## 為什麼

- D1 說 Berth 只建立與管理自己擁有的物件，但下面這些不在物件表、也不在閘門裡（R1 讀碼，S3 實跑確認裝置）：
  - qBittorrent 每個 torrent 都帶 tag `berth`；
  - 每次送單都 `ensure_category`，使用者刪掉的 `berth-*` 分類會被悄悄重建；
  - 每次 Berth 使用者登入，Jellyfin 會多一筆裝置；
  - 套件內 Prowlarr 的「移除」看的是「公開 torrent 站或推薦站」，不看是不是 Berth 加的，使用者自己加的也刪得掉。
- 白名單閘門只守精靈流程；送單、入庫、反查、Issue 修復這些執行期的寫入沒有閘門。另外 `delete_indexer` 的白名單條件比程式嚴，會給人「已經守住」的錯覺。
- Berth 沒有「不用 Berth 了」的清理入口，也沒有文件列出要手動清的東西（S4 整理了一份）。

## 做什麼

1. brief §16.4 物件表與 CONTEXT.md 補上 tag、分類重建、裝置紀錄（全庫掃描照 62 的結論）；各寫明「為什麼」與「怎麼撤」。
2. **行為變更**：套件內 Prowlarr 的「移除」只給 Berth 加的站（`added_sites`；票 47 之前加的沒有紀錄，照實說、不給移除）。CHANGELOG 記這個行為變更。
3. 閘門加一輪執行期：替身上走「送單 → 下載完成 → 入庫 → 反查 → Issue 修復」，每個寫入都要對上白名單（tag 只能是 `berth`、分類只能是 `berth-*`、刪 torrent 只能刪 Berth 的且不刪檔…）。
   - 照全域規則在測試檔內做雙向變異；閘門的宣稱段落（brief §16.4）改成與實際範圍一致。
4. 新增一份使用者 guide「Uninstalling Berth」（英文，57 的 guide 格式）：三個服務各要手動清什麼、硬鏈接怎麼釋放空間。內容取自審計附錄 C.2。

## 驗收

- [ ] 白名單閘門的執行期那一輪，與它的雙向變異
- [ ] 整合測試：Prowlarr 移除只給 Berth 加的站（雙向）
- [ ] brief §16.4、CONTEXT.md、uninstall guide、CHANGELOG 同步
- [ ] 全部檢查、test 綠燈；progress.md 記一行
