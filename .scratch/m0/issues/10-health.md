# 10 — 健康檢查迴圈、健康頁與服務設定頁

**Status:** done

**Blocked by:** 07、09

**讀:** plan §3.2（health_checker）、§6（health、settings、routes 群組）、§9.5、§11.1（T0.8）；brief §16.2

## 做什麼

背景迴圈定期跑四項健康檢查（Jellyfin、qBittorrent、索引站、Route 硬鏈接與跨服務可見性），健康頁顯示每個服務與每個 Route 的狀態、最後成功時間、失敗原因與修正建議；服務設定頁可重測連線、重新套用建議設定。

迴圈以 asyncio task 在 lifespan 啟動，各服務獨立 try/except，一個服務掛掉不拖垮其他檢查。
（原文還寫了「與退避」，實作沒有做——理由見 `docs/progress.md` 的偏差與決定。）

## 驗收

- [x] `health_checker` 在 lifespan 啟動與關閉，關閉時不留 pending task
- [x] `GET /api/health` 匿名回 ok / degraded；`GET /api/health/detail` 需登入，回逐服務與逐 Route 的明細與最後成功時間
- [x] 健康頁四項綠燈
- [x] 停掉任一服務後 5 分鐘內該項變紅，顯示原因與修正建議；其餘三項不受影響
- [x] 服務重新啟動後自動恢復綠燈，不需重啟 Berth
- [x] 設定頁可對每個服務「測試連線」，結果即時顯示
- [x] qBittorrent 關鍵設定漂移時顯示差異與「還原建議設定」按鈕
- [x] Route 的健康結果寫回 `routes.health_status` 與 `health_detail_json`
- [x] 健康頁走 impeccable `shape`
- [x] playwright 跑通全綠與其中一項紅燈兩種狀態並附結果

## Comments

### 完成時的狀態（2026-09-08）

- 416 個後端測試 + 103 個前端測試綠燈；ruff / ruff-format / mypy --strict / import-linter /
  eslint / prettier / tsc 全過。
- 四項檢查的實跑證據（`scripts/fake_setup_server.py` 的三個新情境，真的 API、真的資料庫、
  真的檔案系統，只有三個外部服務是 Fake）：
  - `--scenario healthy`：四格泊位板全綠，值都是那一輪量到的——`10.11.11 · 3 libraries`、
    `v5.2.3 · Web API 2.15.1`、`索引站 1`、`3 條 Route`；展開的 Route 顯示
    `dev=11550084160259632778 · inode=50946970784904639 · free=617.1 GB`（Windows NTFS 上真的
    建了硬鏈接再比 inode）。
  - `--scenario degraded`：按「立即重測」後 BTH 3 變紅、另外三格不動，卡片就地展開
    `GET /ping: connection refused`、`連續失敗 1 次`、`最後成功 38 秒前` 與三條可複製的
    docker 指令。
  - `--scenario drifted`：qBittorrent 那一格是 `設定被改過`（黃，不是紅），設定頁列出逐鍵
    差異表與「還原建議設定」；按下去之後差異表變成「五個建議鍵都還是建議值。」。
- **迴圈在真的程序裡自己跑過**：`healthy` 那台 08:51 啟動、沒有人按過任何按鈕，
  `GET /api/health/detail` 的 `checked_at` 在 09:06 已經是新的一輪。
- 深淺兩主題 × zh-Hant / en 都跑過，最低文字對比 **5.71:1**（亮色）與 **6.53:1**（深色），
  兩者都過 WCAG 2.2 AA；390px 窄版沒有頁面層級的橫向捲動。
- `/impeccable shape`：brief 在 `.scratch/m0/health-shape.md`，direction contract 在
  `.impeccable/surfaces/web-src-pages-healthpage-tsx.md`；detector 對七個新檔案回 `[]`。

### code-review 的發現與處置

兩軸都跑過（Standards / Spec）。已修：逐 Route 缺最後成功時間（票面明寫的驗收）、迴圈第一輪
之前把已接好的服務說成「尚未接上」、漂移連結對非 admin 是死路、差異表的「被改過」只靠顏色、
`ROUTE_SIGNAL` / `ROUTES_SIGNAL` 與四個泊位定義各兩份、恆等映射 `COMPOSE_SERVICE`、
動態組 i18n key、前端型別 `RouteHealthStatus` 名不副實、`Timestamp` 的空值與狀態共用同一句話、
CHANGELOG 未更新。逐條記在 `docs/progress.md` 的「偏差與決定」。

**沒有處理、留給後續的**：

- **brief §16.4 的「媒體庫掛 TVDB 插件（警告）」沒有納入健康檢查。** 那個警告目前只出現在
  精靈第 3 步與第 7 步的媒體庫清單裡——使用者能在那裡改 metadata fetcher，健康頁沒有對應的
  動作。要納入的話應該與 Reconciler 的 Issue 清單一起做（M2），而不是在服務那一列多一個
  沒有按鈕的黃燈。
- **磁碟空間沒有門檻判定。** 目前只在 Route 的 `hardlink` 纜繩上以 `free=` 顯示實測值。
  plan §3.2 原本把「磁碟空間」列在 `health_checker` 的工作裡；門檻與 Issue 留到 M2 的
  Reconciler（那裡才有 Issue 這個載體）。
- **同一份形狀寫了四層**（`ServiceHealth` → `ServiceHealthView` → `ServiceHealthOut` →
  TS 的 `ServiceHealth`）。前兩層是架構要求的（`api` 不 import `models`），第四層本來就該由
  plan §6 的 `openapi-typescript` 產。這是整個前端的共同債，不是這一票引入的；M1 的 API 面
  長出來之後一起接上型別產生器與 CI 的過期檢查。
- **`GET /api/settings/services` 回的是整份 `HealthDetail`（含 `routes`）**，設定頁用不到那一段。
  好處是兩頁同一個形狀、同一份快取；代價是多讀一次 routes 表。M1 若出現第三個消費者再拆。
