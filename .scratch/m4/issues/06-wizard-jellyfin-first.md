# 06 — 精靈改為 Jellyfin 優先：第 1 步就是 Berth 的擁有者

**Status:** done

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

- [x] 套件內：建立 Jellyfin 管理員 → 同一組帳密登得進 Berth、是 admin（整合測試 + playwright，`berth-lab/reset.sh bundled`）
- [x] 既有：以非管理員登入被拒、以管理員登入成功並成為擁有者（整合測試 + playwright，`reset.sh existing`）
- [x] 擁有者成立前，精靈的寫入端點（建立、套用、加站）一律拒絕；成立後需 session（整合測試，雙向）
- [x] 資料庫裡不再有擁有者的明文密碼（測試讀 `settings.setup` 斷言）；migration 對舊列有測試
- [x] 真服務 e2e 的 conftest 改走新流程且全綠；前端 e2e 的精靈三條（wizard / existing / cold-start）改寫且全綠
- [x] brief §16.3 表格、plan §9.3 第 1–3 步、README 精靈段同步；`/impeccable critique`、`audit` 過一輪
- [x] lint、type、test 綠燈

## Comments

**2026-09-28 實作紀錄**

- shape（`/impeccable onboard`，`.scratch/m4/wizard-owner-shape.md`）問了使用者三題、都照建議：qBittorrent / Prowlarr 的偵測留在第 2 步；套件內兩者的介面帳密在 07 之前不設（寫密碼的程式碼改讀泊位自己的 `web_ui_*`，07 補上填它們的地方）；密碼打兩次只在建立時。
- Jellyfin 的七步分兩半：第 1 步跑版本、語言、建管理員、遠端存取、完成初始精靈、登入換 key（`OWNER_STEPS`），泊位 1 跑版本與建媒體庫（`BERTH_STEPS`，用 key；沒有 key 就拒絕）。登入換 key 放在初始精靈跑完之後是原本就實測過的順序；berth-lab 的真 Jellyfin 12.1 上七步全 ok。`JellyfinStep` 照執行順序重排（媒體庫最後）。
- 門禁：`SETUP_OPENING_PATHS`（status、detect、`services/jellyfin`、owner）在擁有者之前匿名，其餘 403；之後整組要管理員 session。`GET /health` 多 `owner_established`，前端守衛靠它把沒有 session 的人送去 `/login?redirect=/setup`。
- 驗證：
  - 真服務 e2e 22 passed（18 分 54 秒，冷啟動那幾秒有碰到：Jellyfin starting → protocol_mismatch → starting → bundled，之後等 Prowlarr）。e2e 要自己看 qBittorrent 的時候改用容器 log 的臨時密碼（`harness.qbittorrent_session`），07 做完再換回泊位上設的那一組。
  - 前端 e2e 33 passed（精靈三條另在 critique 修正後重跑 6 passed）。
  - berth-lab `bundled`（playwright）：建立 `labowner` 之後 `/auth/me` 是 admin；清 cookie 後 `/setup` 導到 `/login?redirect=%2Fsetup`，同一組登回來是 admin；匿名打 bootstrap 與第二次 owner 都 401；`berth.db` 裡找不到那組密碼。
  - berth-lab `existing`：Jellyfin 不在 compose 裡，填 `host.docker.internal:38096` 之後是登入表單；非管理員 `homeguest`（實驗用，以 homeadmin 在舊 Jellyfin 上建的）被拒、`/auth/me` 401；`homeadmin` 成為擁有者、是 admin，清 cookie 後同一組登回精靈。
  - 截圖在 `.playwright-mcp/`（不進 repo）。
- critique（`.impeccable/critique/2026-09-28T13-52-10Z__web-src-setup-ownerstep-tsx.md`，31/40，A、B 各一個子代理）修了三條：找到的既有 Jellyfin 下面收起位址表單（「換一台 Jellyfin」再打開）、`probeEndpoint` 寫使用者填的位址、成立之後停在結果上；拒絕訊息移到送出鈕上方。
- audit（程式碼層，偵測器 CLI 0、overlay 1）：

  | # | 面向 | 分 | 重點 |
  | --- | --- | --- | --- |
  | 1 | 無障礙 | 3 | 欄位與錯誤以 `aria-describedby` 關聯、拒絕是 `role="alert"`、探測區 `aria-live`；載入後焦點在 h2，Tab 跳過頁首語言鍵（StepFrame 既有） |
  | 2 | 效能 | 4 | 第 1 步只自動探一次，之後照第 2 步的輪詢規則 |
  | 3 | 響應式 | 3 | 390 無水平溢出；sticky 主按鈕遮住下方欄位（精靈共用） |
  | 4 | 主題 | 4 | 只用 token，沒有硬寫的顏色 |
  | 5 | 實作一致 | 3 | 偵測器乾淨；overlay 的 `flat-type-hierarchy`（整頁 h1 / h2 皆 18px）是精靈共用樣式 |
  | | 合計 | 17/20 | Good |

**code-review 與 critique 沒處理的發現**

- 390 寬 sticky 主按鈕遮住它下方的欄位（critique P1）：`STICKY_ACTION` 是每一步共用的樣式，改它是另一張票的事。
- `flat-type-hierarchy`（整頁 h1 18px、h2 18px）：精靈共用的字級，同上。
- 前端的 `DETECTED_IN_STEP_TWO` 手抄後端 `_detectable` 的那一半，沒有閘門；後端改可探清單時前置列的計數會說錯。
- `_Runner.auth` / `.refusal` 是 `_authenticate` 就地寫、`claim_jellyfin` 事後讀的 out-param。
- `claim_owner`、`open_session` 是寫入命令，落在 `BEFORE_M3` 豁免的 `setup`、`auth` 模組，`test_command_marks.py` 守不到（M5 補標記時一起）。
- `SetupIndexer` 同時有 `web_ui_password`（要設的）與 `login_password`（上次寫進去的），差別只在註解；07 動這兩格時考慮改名。
- 非管理員在精靈跑到一半時自己去 `/login` 登入，`/setup` 會讓他留在精靈頁、每一支回 403（守衛只看有沒有 session）。罕見，沒有擋。
