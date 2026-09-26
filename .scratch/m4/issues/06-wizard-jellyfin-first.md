# 06 — 精靈改為 Jellyfin 優先：第 1 步就是 Berth 的擁有者

**Status:** ready-for-agent

**Blocked by:** 05

**讀:** brief §11（Berth 沒有自己的帳號）、§16.3、§19 2026-09-26「精靈改為 Jellyfin 優先」那一列；plan §9.3 第 1–3 步與〈前端的導覽〉、§9.4；`.scratch/m0/wizard-shape.md`、`.scratch/m3/issues/06c-setup-admin-cutaway.md`（現在的兩組帳密是怎麼來的）；開工先 `/impeccable onboard` 重新 shape 前置段

## 為什麼

Berth 登入一律交給 Jellyfin（`berth/services/auth.py:1-8`，Seerr 的慣例），可是精靈第 1 步叫「建立 Berth 管理員」，
同一組帳密身兼三職：精靈期間的門鎖、套件內 Jellyfin 管理員、（勾選時）qBittorrent 與 Prowlarr 的介面登入。
2026-09-26 使用者試跑時看不懂「密碼同上」、不懂 Jellyfin 為何單獨列出；接既有服務時這組帳密在精靈結束後
**登不進 Berth**（實測），唯一的用途是門鎖——而 05 修的那條 bug 就是它被寫進了使用者的舊 Prowlarr。

使用者拍板（brief §19）：照 Seerr 的做法，**先連 Jellyfin，Jellyfin 的管理員就是 Berth 的擁有者**。

## 做什麼

1. 前置段改成：**偵測 Jellyfin**（只讀，不需要門鎖）→ **擁有者**：
   - 套件內（`StartupWizardCompleted=false`）：「建立 Jellyfin 管理員」，文案說明 Berth 沒有自己的帳號，
     之後登入 Berth 就用這一組，角色由 Jellyfin 決定。
   - 既有：「用你的 Jellyfin 管理員登入」（不是管理員就拒絕並說明）。
   - 成功的那一刻發 Berth session、精靈 API 從此要登入——取代現在的「Berth 管理員」門鎖。安全面與現在相同
     （誰先到誰建立；Jellyfin 自己的啟動精靈與 Seerr 也是如此），寫進 plan §9.3。
2. 其他服務的偵測挪到擁有者之後（每個泊位自己偵測或在泊位板前一次偵測，shape 時定）。
3. `SetupAdmin` 的「帳號本身 / 介面那一組」兩層拆掉：擁有者的帳密只用來建或登入 Jellyfin、換 API key，**不存下來**
   （既有 Jellyfin 現在就是「只用來換 API key，不會存下來」，套件內跟著一樣）。qBittorrent / Prowlarr 的介面帳密
   移到它們自己的泊位（07）。資料格式的破壞性變更寫 migration，舊列的處理寫進 plan。
4. 精靈完成頁與登入頁的文案跟著改：「用你的 Jellyfin 帳號登入」。

## 驗收

- [ ] 套件內：建立 Jellyfin 管理員 → 同一組帳密登得進 Berth、是 admin（整合測試 + playwright，`berth-lab/reset.sh bundled`）
- [ ] 既有：以非管理員登入被拒、以管理員登入成功並成為擁有者（整合測試 + playwright，`reset.sh existing`）
- [ ] 擁有者成立前，精靈的寫入端點（建立、套用、加站）一律拒絕；成立後需 session（整合測試，雙向）
- [ ] 資料庫裡不再有擁有者的明文密碼（測試讀 `settings.setup` 斷言）；migration 對舊列有測試
- [ ] 真服務 e2e 的 conftest 改走新流程且全綠；前端 e2e 的精靈三條（wizard / existing / cold-start）改寫且全綠
- [ ] brief §16.3 表格、plan §9.3 第 1–3 步、README 精靈段同步；`/impeccable critique`、`audit` 過一輪
- [ ] lint、type、test 綠燈

## Comments
