# 06g — 精靈偵測：服務還在啟動時的暫時錯誤當成「探測中」，不是 500、不是既有

**Status:** ready-for-agent

**Blocked by:** None — can start immediately（只動 `services/setup.py` 的判定、前端的輪詢條件與它們的測試）

**讀:** plan §9.3 第 2 步（「探不到要分兩種」、`resolved`、2 分鐘上限）；brief §16.3；`berth/services/setup.py`（`_classified`、`_verdict_*`）、`berth/adapters/http.py`（`ServiceBusyError`）、`berth/adapters/jellyfin/client.py`（`public_info`）；`web/src/pages/SetupPage.tsx`（`waiting` 與輪詢的 effect）

## 做什麼

使用者 2026-09-25 重跑精靈時遇到偵測失敗，按「重新探測」之後又好了。重置試跑環境（`C:\Users\Roxy\berth-trial\`，四個容器同時啟動）後以腳本在 Berth 起來的那一刻建管理員、每 0.5 秒 `POST /setup/detect` 一次，量到的時間線：

| 啟動後 | Jellyfin | Prowlarr | qBittorrent |
| --- | --- | --- | --- |
| 4.8 s、7.9 s | **整支回 500** | | |
| 11.0 s | **`existing` / `protocol_mismatch` / `resolved=false`** | `pending` / `unreachable` | `bundled` |
| 12.6 s | `pending` / `unreachable` | `pending` | `bundled` |
| 13.4–15.6 s | **整支回 500（5 次）** | | |
| 16.1 s | `bundled` / `setup_pending` | `pending` | `bundled` |
| 24.6 s | `bundled` | `bundled` / `no_indexers` | `bundled` |

兩個缺陷：

1. **Jellyfin 啟動中回 503「still loading」，`_classified` 沒接 `ServiceBusyError`**，例外一路冒成 500（traceback：`setup._verdict_jellyfin` → `jellyfin.client.public_info` → `adapters/http.py` 的 `ServiceBusyError: GET /System/Info/Public: 503 still loading`）。`_classified` 的 docstring 寫「把 adapter 的四種錯誤翻成判定」，`ServiceBusyError` 是第五種。
2. **啟動中的 Jellyfin 被判成 `existing` / `protocol_mismatch`**：`public_info` 拿到的不是 Jellyfin 的 public info payload（啟動途中的回應），就丟 `ProtocolMismatchError`，而那是終局判定。

前端只在「有服務是 `pending`」時自動輪詢（`SetupPage.tsx` 的 `waiting`）。所以：第一次探測就 500 時還沒有任何判定、不輪詢，畫面停在「偵測失敗」；Jellyfin 被誤判成既有的那一刻若另外兩個已經有結論，也不再輪詢，畫面展開既有服務的表單。兩種都只能靠手按「重新探測」——使用者碰到的就是這個。

- **`ServiceBusyError` → `pending`**（新的 `DetectionReason`，例如 `starting`，封閉集合進 OpenAPI 與 i18n：「還在啟動」）。跟 `unreachable` 一樣受 2 分鐘上限管，逾時轉 `timeout`。
- **`protocol_mismatch` 在輪詢視窗內當 `pending`**：從第一次探測起算、還在 `window_seconds` 內的 `protocol_mismatch` 先當「還在啟動」繼續等；過了視窗仍是它才判 `existing`。代價：主機名上真的是別的東西時，要等到視窗結束才展開表單——與 `unreachable` 同一個代價，可以接受。三個服務的 `_verdict_*` 都照這個規則，不只 Jellyfin。
- **前端：探測本身失敗（非 2xx）時照樣排下一次輪詢**，直到拿到判定或視窗結束；不是停在「偵測失敗」等人按。
- 修好之後，「重新探測」剩下的用途是使用者自己改了東西（例如把服務加回 `COMPOSE_PROFILES` 再起）——06d 把它移到出問題的那一格旁邊。

## 驗收

- [ ] 紅燈先行：Fake Jellyfin 丟 `ServiceBusyError` 時 `detect_services` 回 `pending` / `starting` 而不是冒例外（整合測試，修正前紅）
- [ ] `protocol_mismatch` 在視窗內是 `pending`、過了視窗是 `existing`（單元測試用注入的 `now`，雙向）；三個服務各一條
- [ ] `ServiceBusyError` 在視窗結束時轉 `timeout`（單元測試）
- [ ] 前端：探測回 500 時照樣排下一次輪詢（前端測試，修正前紅）
- [ ] 實跑：重置試跑環境、同時起四個容器，從精靈第 1 步照常操作，第 2 步不必按「重新探測」就全部判定完成；附時間線
- [ ] 新 `DetectionReason` 的 zh-Hant 與 en；plan §9.3 第 2 步補上「啟動中」這一種
- [ ] lint、type、test 綠燈
