# 11 — 第一批審核：證據夠強時跳過；要看的整組說一句話

**Status:** ready-for-agent

**Blocked by:** 02（Jellyfin 回驗誤報修掉之前，審核頁的量不準）

**讀:** brief §15、§19 2026-09-26「第一批審核證據夠強時跳過」那一列；plan §4.4（播出日比對、以發佈時間推測虛擬季）、§11.4；`.scratch/m3/issues/13-series-season-offset.md`、`14-air-date-check.md`、`15-runtime-check.md`；`berth/services/review.py:~126, ~548`、`berth/services/plan.py:~922`

## 為什麼

自動綁定的 RSS Series 在 `confirmed = false` 期間入庫的每一集都掛 audit（`AuditReason.FIRST_BATCH`，高信心也是），
為的是抓規則層看不出的季號與 offset 錯（split-cour、字幕組每輪重數）——Jellyfin 回驗抓不到，它認集數靠 Berth 的檔名。
2026-09-26 試跑：BLACK TORCH 四集全部「只有集號、發佈標題與作品完全相同、播出日對得上」，使用者逐一展開、
看不出有什麼需要在意，收起時只看得到「S01E03」。

使用者拍板：**證據夠強時跳過第一批**。

## 做什麼

1. 定「證據夠強」並寫進 plan §11.4 / brief §15（下面是起點，用 benchmark 語料與 M3 e2e 的 split-cour 案例驗證後再定）：
   該列規則層信心 high；季集照字面對應（沒有 offset、沒有絕對集數換算、沒有以發佈時間推測的重數、Series 沒有設季號與 offset）；
   播出日比對拿得到那一集的播出日而且通過；片長驗證通過或量不出。
2. 第一批裡每一列都符合時：不掛 audit，系統把 Series 標成已確認（`bound_by` 之外記一筆事件，說出依據）；有一列不符合就照舊整批待確認。
3. 仍需要看的那一批，審核頁整組一句話說出在問什麼（「確認 BLACK TORCH × ANi 的季集對應：E01–E04 由集號直接對應」），
   配「確認整個 Series」；逐列展開留著。作品頁 RSS 訂閱那一段的「第一批待確認」標籤帶同一句說明。
4. M3 e2e 的 `test_one_correction_carries_the_rest_of_the_series`（split-cour 要停在審核）必須照樣停住——那就是這條規則不能放過的樣子。

## 驗收

- [ ] 規則寫成純函式，逐條件雙向測試（每拿掉一個條件，本來跳過的那一批就會掛 audit）
- [ ] split-cour 與虛擬季的案例仍停在審核（整合測試 + 真服務 e2e 綠燈）
- [ ] 跳過時 Series 自動確認、時間線有依據；不跳過時審核頁整組一句話（vitest + playwright 文字結果）
- [ ] brief §15、plan §11.4 同步；`berth bench` 的 `auto_wrong` 不升
- [ ] lint、type、test 綠燈

## Comments
