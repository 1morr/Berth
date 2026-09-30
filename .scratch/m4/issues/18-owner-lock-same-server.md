# 18 — 擁有者鎖定做實：只能換到同一台 Jellyfin、不能重建擁有者、版本在測連線時就擋

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** `docs/research/wizard-review-2026-09-30.md`（測試環境、錯誤設定對照表）；brief §19（精靈手動選擇）、§16.4、
§20.14；plan §9.3〈服務頁的共同形狀〉、§9.5；票 15 的 `## Comments`（`OWNER_LOCKED` / `JELLYFIN_OWNED` 那幾條）

## 為什麼（2026-09-30 精靈審查，兩個測試員各自重現）

- **擁有者成立後，Jellyfin 還能換成另一台，而且會存下來。** 既有 Jellyfin 頁按「改位址或憑證」→ 填另一台
  （`host.docker.internal:58097` → `:48096`，或反過來）→ 測試連線：200、`state: ok`，`/api/setup/status` 的
  `base_url` 變成新那台；擁有者仍顯示原本的帳號，而那個帳號、Berth 的 API key、媒體庫快照都在舊那台。
  畫面同一時間寫著「來源在擁有者成立之後就鎖住了」「換一台等於換擁有者，所以精靈裡鎖住了」。
  成因：改位址不重做這一頁（`berth/services/setup.py:277`），測試只打匿名的 `/System/Info/Public`
  （`setup.py:394-401`），一定綠。
- **`POST /setup/owner` 不擋「擁有者已存在」**（`setup.py:181-204`）：成立之後任何一位管理員直接打這支就能換掉
  擁有者。UI 沒有入口，但這是權限的洞。
- **Jellyfin 版本在測連線時就讀到了，卻要到登入才擋**：10.10.7 測連線是綠燈「連上了，已經有管理員 · 版本
  10.10.7」，按登入才 502，下面是英文 `Jellyfin 10.10.7 is older than 12.0`，前一句還說「它回的原文在下面」
  （其實是 Berth 自己的字串）。
- **按鈕與文案**：三個服務共用「改位址或憑證」（`web/src/setup/ServiceChoice.tsx:588-591`、`resources.ts:208`），
  Jellyfin 沒有憑證欄，提示卻寫「管理員帳密在下一格」（`resources.ts:258`），擁有者成立後沒有下一格；
  「這裡能做：重新測試這一台」但畫面上沒有重新測試鈕；狀態列「Jellyfin 連上了：連上了，已經有管理員」重複。
- **替還沒初始化的既有 Jellyfin 跑初始精靈時**，語言與地區寫死 zh-TW / TW、開啟遠端存取（`berth/services/jellyfin.py:71-73`、
  `:680-684`），沒問使用者。

## 做什麼

1. **「同一台」的判準**：先查證 Jellyfin `/System/Info/Public` 的 `Id`（ServerId）是不是跨重啟、跨換網址都穩定
   （`mattpocock-skills:research` 或對 berth-existing 的兩台實測；結論補進 brief §20）。
2. **擁有者成立後改 Jellyfin 位址**：新位址的 ServerId 與擁有者成立時記下的不同 → 拒絕、不存，理由是新的
   `ConnectionReason`（或沿用既有的拒絕列舉）；相同 → 存下並重新驗證 Berth 的 API key（打一支要驗證的端點），
   key 失效就要求擁有者重新登入。設定頁的「Jellyfin」換位址走同一條規則。
3. **`POST /setup/owner` 在擁有者已存在時回 409**；設定頁要換 API key 的「重新登入」是另一支，不受影響。
4. **版本在測連線時就擋**：`/System/Info/Public` 讀到版本低於 12.0 → `VERSION_UNSUPPORTED`，說「至少 12.0，你的是 X」
   （與票 17 Prowlarr 的句型一致）；登入那一段保留同一判斷作為後備。
5. **文案**：Jellyfin 那一格的按鈕叫「改位址」、拿掉「管理員帳密在下一格」；「這裡能做」只列畫面上真的有的動作
   （要嘛加一顆重新測試，要嘛拿掉那句）；狀態列去重複。
6. **替既有 Jellyfin 初始化時的語言與遠端存取**：**開工前問使用者**（2026-09-30 審查留下的決定）。協調者建議：
   語言與地區跟精靈當下的 UI 語言走；遠端存取不動（Berth 從同一台主機的容器連進來，不需要）。

## 驗收

- [ ] ServerId 判準的查證結論寫進 brief §20，附來源或實測紀錄
- [ ] 整合測試：擁有者成立後把位址換到 ServerId 不同的 Fake → 拒絕、`base_url` 不變；換到同一台的新網址 → 存下並
      重驗 key（雙向：同一台過、不同台擋）
- [ ] 整合測試：擁有者已存在時 `POST /setup/owner` 回 409，擁有者不變
- [ ] 整合測試：`/System/Info/Public` 回 11.x 時測連線就是 `version_unsupported`，訊息帶目前版本與下限；剛好 12.0 通過
- [ ] vitest：Jellyfin 那一格的按鈕文字、沒有「管理員帳密在下一格」；zh-Hant 與 en 並列
- [ ] 初始化語言與遠端存取依使用者的決定實作，決定記進 progress.md「偏差與決定」
- [ ] playwright 對 `berth-existing` 實跑（另起一份受測 Berth，見研究檔）：10.10.7 在測連線就紅；擁有者成立後改到另一台
      被擋、畫面說明為什麼；改回同一台通過。附截圖或文字結果
- [ ] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈
