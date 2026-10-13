# 66 — 接管清單補齊、閘門延伸到執行期、「移除 Berth」清單

**Status:** done

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

- [x] 白名單閘門的執行期那一輪，與它的雙向變異
- [x] 整合測試：Prowlarr 移除只給 Berth 加的站（雙向）
- [x] brief §16.4、CONTEXT.md、uninstall guide、CHANGELOG 同步
- [x] 全部檢查、test 綠燈；progress.md 記一行

## Comments

- 2026-10-14 實作：閘門的執行期那一輪經 services 走（不經 API）：`test_plan.ready` 起點、`walk_runtime` 走送單 → 缺檔按「重新校驗」→ 下載完成 → 規劃、入庫 → 反查（第一次全庫掃描、之後只刷新媒體庫）→ 六次用完按「重新掃描媒體庫」→ 刪 Job。白名單新列：`add_torrent`（看 adapter 真的送的表單 `add_form`：`berth-*`、tag 只有 `berth`、`autoTMM=true`、沒有 `savepath`，補 R1 G2）、`start`／`recheck`／`delete_torrent` 只對 Berth 這一輪送的或探測的 hash、`notify_paths` 在 library root 底下、`refresh_library` 只 Route 的媒體庫、`run_task` 只「掃描媒體庫」。變異：單筆寫入紅綠各一組，tag 與刪檔另各一條走完整流程。Prowlarr 的移除改看 `added_sites`，閘門的 `delete_indexer` 與程式不再一寬一嚴（G4）。Jellyfin 裝置的行為查 v12.1 原始碼補進 brief §20.22。
- 驗證：pre-commit 全綠；pytest 3970 passed；vitest 1808 passed；前端 e2e wizard / settings / existing 兩種寬度 6 passed。
- code-review 沒處理的：(1) 「是不是 Berth 加的站」在 `_sites` 與 `remove_indexer` 各判斷一次（後者還要先擋既有），沒收成一支；(2) 閘門檔從 `test_plan`、`test_downloads` import 起點與 `status`，沒搬進 `factories.py`；(3) 刪檔的那條變異 monkeypatch 私有的 `deletion._remove_torrent`，那裡重構時要跟著改；(4) 兩條走完整流程的變異只驗紅，綠的方向由主測試承擔；(5) `under()` 改成兩種分隔符都認（Windows 的 `tmp_path`），精靈那幾輪也跟著放寬一點（root 後面接反斜線也算在底下），容器路徑不會出現反斜線。
- 仍不在閘門範圍（brief §16.4 閘門段已寫明）：換台時移除空分類那一顆只用合成寫入驗（R1 G5）、`mark_played`（使用者自己的觀看紀錄）、Jellyfin 的裝置紀錄（登入被當讀，G3）、磁碟（G6）。
