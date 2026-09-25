# 06g — 精靈偵測：服務還在啟動時的暫時錯誤當成「探測中」，不是 500、不是既有

**Status:** done

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

- [x] 紅燈先行：Fake Jellyfin 丟 `ServiceBusyError` 時 `detect_services` 回 `pending` / `starting` 而不是冒例外（整合測試，修正前紅）
- [x] `protocol_mismatch` 在視窗內是 `pending`、過了視窗是 `existing`（單元測試用注入的 `now`，雙向）；三個服務各一條
- [x] `ServiceBusyError` 在視窗結束時轉 `timeout`（單元測試）
- [x] 前端：探測回 500 時照樣排下一次輪詢（前端測試，修正前紅）
- [x] 實跑：重置試跑環境、同時起四個容器，從精靈第 1 步照常操作，第 2 步不必按「重新探測」就全部判定完成；附時間線
- [x] 新 `DetectionReason` 的 zh-Hant 與 en；plan §9.3 第 2 步補上「啟動中」這一種
- [x] lint、type、test 綠燈

## Comments

**做法**：`_classified` 多接 `ServiceBusyError` → `pending` / `starting`（新的 `DetectionReason`，進 OpenAPI、zh-Hant / en、`signals.ts`）；`ProtocolMismatchError` 改回 `pending` / `protocol_mismatch`，由 `_settled` 過了視窗判既有（其餘 `pending` 照舊判逾時）。三個 `_verdict_*` 都走 `_classified`，所以同一條規則。使用者自己填的位址（`_probe_connection`）照舊把 `pending` 當場轉既有；`starting` 進 `UNRESOLVED_REASONS`，否則「既有 · 還在啟動」會被當成接好了。前端 `SetupPage.tsx`：探測失敗時從第一次失敗起算（`failingSince`）、在 `window_seconds` 內每 3 秒再探，視窗內的失敗顯示成「探測中…」、不掛「探測沒跑完」；過了才停下來等人按。使用者自己按與單一服務重探成功都重算這個視窗。

**紅燈與變異**：後端整合 8 條（503 → `starting`、`starting` 逾時、`protocol_mismatch` 視窗內 / 外各三個服務、自填位址的兩種不給視窗），前端 3 條（500 之後照排、一直失敗到上限停、放棄後單一重探恢復輪詢）。變異：拿掉 `UNRESOLVED_REASONS` 的 `STARTING`、`_settled` 的協定不符改回逾時，各自轉紅後還原。**驗收寫「單元測試」，實際放在 `tests/integration/test_setup_service.py`**：與同檔的 `pending` / 逾時測試同一層，走 `detect_services` 加注入的 `now`，不直接測 `_settled`。

**實跑（隔離副本，使用者拍板不重置 `berth-trial`）**：repo 的 `deploy/docker-compose.yml` + 這一票工作樹 build 的 `berth:06g`，project `berth-06g`、port 28xxx，`config/` 與 `data/` 全新，四個容器一次 `up -d`；playwright 在 Berth 回 health 的那一刻照常填第 1 步、按「開始探測」，之後什麼都不按。時間從 `up` 起算：

| 時間 | 事件 / Jellyfin | Prowlarr | qBittorrent |
| --- | --- | --- | --- |
| 8.8 s | Berth `/api/health` 200 | | |
| 9.0 s | 第 1 步送出 | | |
| 9.8 s | 按「開始探測」 | | |
| 10.4 s | `pending` / **`protocol_mismatch`** | `pending` / `unreachable` | `bundled` |
| 13.4 s | `pending` / **`starting`** | `pending` / `unreachable` | `bundled` |
| 16.5 s | `bundled` / `setup_pending` | `pending` / `unreachable` | `bundled` |
| 19.5–22.5 s | `bundled` | `pending` / `unreachable` | `bundled` |
| 25.7 s | `bundled` | `bundled` / `no_indexers` | `bundled` |
| 26.0 s | 「前往泊位 1」出現；單一服務重探 0 次 | | |

六次 `POST /setup/detect` 全是 200，Berth log 沒有 traceback；兩種新的「還在啟動」都真的出現。截圖 `.local/screens/m3-06g/step2-done.png`（不進版控）。跑完 `down`、刪目錄與 image；`berth-trial` 一直沒動。

**code-review 未處理的發現**：
- 後端視窗沒重算時指名重探一台剛起來的服務（另一台停在 `timeout`，`probe_started_at` 不會清），`protocol_mismatch` 會立刻判既有、`starting` 立刻判逾時，不再等一個視窗。`unreachable` 本來就是這樣；按「重新探測」整輪重試（`restart`）會重算。
- 視窗內那一列寫「探測中 · 連得上，但回的東西不是這個服務」加倒數：理由照實說看到的東西，等待提示寫「容器還在啟動」。票面說「先當還在啟動」，沒有改理由，因為過了視窗要靠它判既有。
- `windowMs` 在 status 還沒載入時是 0，第一次失敗就算放棄；走得到第 2 步時 status 一定已經載入。
- `failingSince` 在兩處歸零（探到了、使用者按了新的一輪）：兩個不同的理由，沒有合併。
