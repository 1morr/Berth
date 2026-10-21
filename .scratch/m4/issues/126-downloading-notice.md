# 126 — 「正在下載」：RSS 每輪每部作品一則

**Status:** ready-for-agent

**Blocked by:** 125

**讀:** plan §11.5〈通知〉；brief §15；`berth/services/rss.py` 的 `poll_feed`、`_submit`、`_submit_waiting`（一輪在哪裡開始與結束）；送單的命令（`services/jobs.py` 的 `add_download` 一帶）；M4 票 03（大批送單）

## 為什麼

試跑時一次 Mikan 綁定 11 分鐘送出 144 個 torrent（plan §11.5）。每個 torrent 一則的話，手機會被洗版。人在場自己按下載時，也不需要再被告知一次。

## 做什麼

1. RSS 一輪（一個 Feed 的一次輪詢、補漏或綁定後的補送）送出的 Job，依收件人與作品合成一則：「芙莉蓮 S02E03–E05 正在下載（Route 名）」；這一輪結束時寫入，與送單的交易同進退的原則照 plan §3.3。
2. 人手按的下載（搜尋結果、作品頁）也送給其他訂閱者，但不送給按的人。
3. 收件人規則同票 125（訂閱、Discord ID、`UserViews`）。

## 驗收

- [ ] 一輪送出同作品 3 集與另一部 2 集 → 每位收件人 2 則，季集範圍正確（pytest）
- [ ] 一次綁定送出上百個 torrent（Fake）→ 每位收件人每部作品一則（pytest）
- [ ] 手動下載：按的人不收、其他訂閱者收（pytest）
- [ ] 沒送成功的（`submit_failed`）不算進「正在下載」（pytest）
- [ ] 全部檢查、pytest 綠；CHANGELOG、progress.md 已更新
