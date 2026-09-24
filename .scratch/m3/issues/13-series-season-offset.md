# 13 — 季號與 offset：第一批審核、套用到整個 RSS Series、確認後不再 audit

**Status:** ready-for-agent

**Blocked by:** 05（批次確認的分組形狀）、08（RSS Series 與規劃讀季號 offset）

**讀:** plan §2.3（`plans`、`plan_items`）、§3.1（`review` 的核准 / 拒絕）、§4.4、§11.4；brief §6.4、§6.5、§15（「季號與 offset」）、§19（「沒有 AI 時把人工降到最少」）

## 做什麼

brief §15，使用者 2026-09-24 拍板。

- **每份計劃記下它用到的季號與 offset**：RSS Series 的值在規劃時讀，所以同一個 Series 前後兩份計劃可能用了不同的值，要看得出來。
- **新 RSS Series 的第一批進審核**：已經入庫、只是等人看一眼，走 audit 的形狀（`confirmed = false` 期間 high 也標 audit）。審核頁以 RSS Series 分組，一組一顆「全部確認」（沿用票 05 的形狀）；確認之後 `confirmed = true`。
- **改正並套用到這個 RSS Series**：在審核裡改一集的季集時，可以選「套用到這個 RSS Series」。套用後寫回 Series 的季號與 offset，**重算它底下還沒確認的集數**（補舊集一次十幾集，第一集錯就全錯，改一次要全修好）。重算走既有的重新規劃與 rematch 路徑，不另寫一條入庫路。
- **確認過之後，medium 入庫不再進 audit 清單**：之後改由播出日比對（票 14）、片長驗證（票 15）、Jellyfin 回驗（票 17）與 M4 的每日檢查守著。

新命令（套用到 Series、確認 Series）照票 05 標副作用等級與反向命令。

## 驗收

- [ ] Plan 上看得到它用的季號與 offset（API 與 `/jobs/:hash`）
- [ ] 新 Series 的第一批出現在 `/review`，以 Series 分組；按一次全部確認之後 `confirmed = true`（整合測試）
- [ ] split-cour：第二 cour 從 01 重數、TMDB 併成一季，第一批換算錯 → 在審核裡改一集並套用到 Series → 其餘未確認的集數跟著對，已入庫的鏈接搬到正確路徑（整合測試，對應 M3 驗收第五條）
- [ ] 已確認的 Series，新進的 medium 集數不出現在 audit 清單；未確認的照舊出現（雙向，對應 M3 驗收最後一條）
- [ ] 新命令都有副作用標記
- [ ] playwright 對演練情境實跑改正並套用，附結果
- [ ] lint、type、test 綠燈
