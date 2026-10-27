# 05 — 核准被擋的計劃時重新比對帳本

**Status:** ready-for-agent

**Blocked by:** 01

**讀:** plan §11.6〈分段〉第 1 段、§11.4 的 M3 票 14 / 14b 段落；`docs/research/m5-ai-direction-2026-10-27.md` A3 的 R10；`.scratch/m3/issues/14-*.md`、`14b-*.md` 的 Comments；`berth/services/plan_review.py`（`held_proposal` 與核准路徑）

## 為什麼

被播出日比對擋下的計劃列，與 `held_proposal` 的改正，在核准時不再比對帳本，所以重複版本與 `span_clash` 會漏檢。M6 起 AI 的結果走同一條核准路徑，這個洞要先補。

## 做什麼

1. 先寫會紅的測試：被擋下的列，在核准前帳本裡已經有同一集，核准之後產生重複；或者兩列撞在同一個範圍（`span_clash`）。
2. 核准路徑在套用之前，用與規劃時同一份帳本比對。規則只有一份實作，不在核准路徑另寫一套。
3. 比對出問題時，照規劃時的行為處理（重複版本的決定、撞範圍的理由），不默默放行。

## 驗收

- [ ] 重複版本與 `span_clash` 各有一條先紅後綠的測試
- [ ] 規劃與核准共用同一個比對函式
- [ ] 全部檢查與 pytest 綠；progress.md 已更新

## Comments
