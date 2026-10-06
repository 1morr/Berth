# 33 — 接管＝只管 Berth 擁有的物件：名詞表、brief 與寫入白名單閘門

**Status:** done

**Blocked by:** 32（套件內 qBittorrent 不寫全域鍵之後，這條定義才對兩種來源都成立）

**讀:** `docs/research/wizard-audit-2026-10-06.md`（§B 全部、「文件與實作不符」的 `CONTEXT.md:110-112`、brief:519、brief:123、README:28 四列、改進清單 P1-1）；brief §19「精靈審計後的八項」D1、§16.3、§16.4；`CONTEXT.md` 的 Existing / Bundled service

## 為什麼（2026-10-06 審計）

- `CONTEXT.md` 的定義已經過時。它寫既有服務「只做檢查，不寫它的帳密、不改它的全域偏好、不替它加索引站，改動一律要按鈕確認」。
  實際上 Berth 會建 API key「Berth」、建 `berth-*` 分類、加 Berth 路徑；票 20 起也能加站；票 08 之後沒有獨立的確認鍵。
- **D1 拍板**：接管＝只建立與管理 Berth 擁有的物件，套件內與既有共用同一條。兩者只差在套件內由 Berth 讓服務有人登得進去：Jellyfin 管理員、介面登入、白名單、掛載的 key。
- 這條規則現在沒有閘門。票 05 的事故（覆寫使用者 Prowlarr 的登入）就是同一類錯。

## 做什麼

1. 改寫 `CONTEXT.md` 的 Existing service 與 Bundled service，用報告 §B2 結尾的說法。
2. 改寫 brief §16.3 開頭的條列與 §16.4，把報告 §B3 的「物件 × 套件內 / 既有 × 能不能撤回」表收進 §16.4。
   一併修掉 brief:519（「偵測套件內…」）與 brief:123（「路徑字串可以是 `/data` 以外」）。頂端「待改寫」那句裡 D1 的部分拿掉。
3. README 各服務概述（BTH 1–3）照實作改寫：既有 Jellyfin 的 Berth 路徑併進「建立並檢查」、頁 1 會建 API key。
   BTH 4 的敘述留給 37 與 44。
4. **閘門**：整合測試跑完整個精靈（套件內與既有各一輪）。Fake 後端收到的每個寫入請求，都要落在一張白名單裡：
   Berth 擁有的物件，加上只限套件內的 bootstrap（Jellyfin 初始設定、介面登入）。既有那一輪的 bootstrap 只允許「那台 Jellyfin 還沒初始化」這一個例外。
   已有的前端 `existing.spec` 寫入清單若能涵蓋，沿用並擴充，不另起一份。

## 驗收

- [x] `CONTEXT.md` 與 brief §16.3、§16.4 用同一套說法描述「Berth 只管自己擁有的物件」，兩者不互相矛盾
- [x] 寫入白名單閘門測試在測試檔內做雙向變異驗證：既有那一輪多送一個全域偏好要變紅，改無關命名不變紅
- [x] 報告「文件與實作不符」表中這張負責的四列（CONTEXT:110-112、brief:519、brief:123、README:28）都已改
- [x] progress.md「偏差與決定」記一行
- [x] 全部檢查（`pre-commit run --all-files`）、test 綠燈

## Comments

2026-10-06 code-review（Standards 與 Spec 兩軸）沒有處理的發現：

- README〈選「既有」的條件〉仍寫「同一個容器路徑（例如三個都是 `/data`）」，比 brief §4.4 的「固定 `/data`」寬。那一段的改寫屬於審計 P1-6，留給那張票。
- README 服務表下新加的總述說既有 Prowlarr 也能加「你勾選加入的站」（票 20 起的實際行為），表裡 BTH 4 既有那一欄仍是「用你已經有的站」。BTH 4 的敘述照票面留給 37、44。
- `ok`、`under`、`methods` 這幾個測試 helper 名字偏短（Mysterious Name，判斷題）：只在這個檔案裡用、用法一眼看得出，不改。
- 測試從 `test_setup_api.py` 匯入 `_choose`、`_seen`、`_set_paths` 這幾個私有 helper：鄰近的測試檔已有同樣做法，不算違規。
