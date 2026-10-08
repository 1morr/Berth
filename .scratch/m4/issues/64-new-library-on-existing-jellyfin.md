# 64 — 替既有 Jellyfin 新建媒體庫（勾了才建），類型對得上的預設勾選

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** `docs/research/usability-audit-2026-10-07.md` §2 E1、§4.2 C2、§5.2、§8 P2-15；brief §16.4（接管＝只建立與管理 Berth 擁有的物件、既有 Jellyfin 不搬媒體庫）、§19「第四輪可用性審計的八項」E1；CONTEXT.md 的 Jellyfin Library、Berth path、Existing service；`tests/integration/test_setup_owned_writes.py` 的白名單（閘門）

## 為什麼

- 既有 Jellyfin 只有劇集媒體庫、使用者想下載電影時，現在 Berth 不建，卡片叫使用者先去 Jellyfin 建。
- 這是使用者理想流程（「能接入就自動完成需要的設定」）與 D1 唯一實際衝突的地方。
- 使用者拍板 E1：頁 3 多一列「新建一個媒體庫」，勾了才建。新建的媒體庫是獨立物件，納入「Berth 擁有的物件」，推翻 §16.4「既有不建媒體庫」。
- 審計 S2：頁 3 要逐個勾媒體庫；中文媒體庫名直接成為分類與資料夾名（`berth-節目`、`/data/library/節目`），特殊字元與撞名沒驗過。

## 做什麼

1. **先 `/impeccable shape`** 頁 3 既有那一側的新列：類型、名稱、資料夾。說清楚「這個媒體庫在你的 Jellyfin 上，所有使用者都看得到」。
2. 既有 Jellyfin 的頁 3 可以新增「新建媒體庫」列（類型＋名稱，路徑是 `/data/library/<slug>`），勾了才在「建立並檢查」時建。
   - 與套件內建媒體庫同一條路徑（同名的不重複建）。
3. 類型對得上 Route 用途的既有媒體庫（movies、tvshows）預設勾選；其他不勾。
4. **接管定義改寫**：brief §16.4 物件表、CONTEXT.md 的 Existing service，都加上「使用者勾選後新建的媒體庫」。
   - 寫入白名單閘門放行「既有 Jellyfin 上、勾選的、在 library root 底下的新媒體庫」，做雙向變異：沒勾也建、建在 library root 外都要紅。
5. 媒體庫名的 slug：中日文、空白、`/`、同名，各一個單元測試。照結果決定要不要改規則，改了就記進偏差。

## 驗收

- [ ] 整合測試：勾了才建、同名不重複、預設勾選的規則；白名單閘門雙向
- [ ] slug 的單元測試（中文、特殊字元、撞名）
- [ ] vitest 與實跑：只有劇集媒體庫的既有 Jellyfin，頁 3 新建電影媒體庫 → 6/6 → 入庫一部電影，附截圖
- [ ] 全部檢查、test、前端 e2e 綠燈；brief §16.4、CONTEXT.md、README guide、CHANGELOG 同步；progress.md 記一行
