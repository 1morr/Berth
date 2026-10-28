# 21c — 修復：DeepSeek 尖峰時段讓 21b 的計價測試變紅

**Status:** ready-for-agent

**Blocked by:** 21b

**讀:** 票 21b 與它的 Comments；`berth/adapters/ai/prices.py`、記帳寫 `ai_calls.cost_usd` 的地方（`services/agent.py` 或 `adapters/ai/usage.py` 的 `call_row`）；`tests/integration/test_agent_web_search.py::TestTheBooks`；brief §20.24 的 DeepSeek 尖峰 / 離峰那一條

## 為什麼

`main` 的 CI（run 40620886441，2026-10-28 02:42 UTC）紅在：

```
FAILED tests/integration/test_agent_web_search.py::TestTheBooks::test_a_call_is_priced_by_the_endpoint_it_went_to
assert 1.74e-05 == 8.7e-06 ± 8.7e-12
```

剛好兩倍。02:42 UTC 是 DeepSeek 的尖峰（平日 UTC 01:00–04:00、06:00–10:00，價錢是離峰的兩倍）；票 21b 跑測試時是離峰，所以當時是綠的。每個平日的尖峰時段都會紅，是穩定的紅燈。

**要先分清是產品的問題還是測試的問題**：這條測試給假模型的回應已經設了 `timestamp=OFF_PEAK`，算出來卻是尖峰價。21b 說「每次呼叫照回應當下的時段算」——如果記帳用的是牆上時鐘（`now()`）或請求開始時間而不是回應的 `timestamp`，那是產品的 bug（用量頁的費用在尖峰邊界會算錯）；如果是假模型把 `timestamp` 蓋掉了，才是測試的問題。

## 做什麼

1. **repro**：寫一條會紅的測試，把時鐘釘在尖峰（例如 time-machine 釘 02:42 UTC 的平日），回應的 `timestamp` 給離峰，斷言照回應時間計價。在修之前跑一次貼紅燈。
2. 照 repro 找出根因並修：計價用的時間要跟 21b 寫在文件裡的規則一致（回應的時間；沒有時間才退到記帳那一刻），文件與程式說的要是同一件事。
3. **補對稱的測試**：尖峰時段的呼叫照尖峰價、離峰照離峰價，兩條都釘時鐘，不依賴跑測試的時間。
4. **掃一遍**：其他斷言費用的測試（`grep` `cost_usd`、`approx(`、`0.15`、`0.6`、`deepseek`）有沒有同樣依賴當下時段的，一併釘住；在 Comments 列出掃過的檔。
5. 不准只拉長容忍或改預期值：說不出原因的不收。

## 驗收

- [ ] repro 修之前紅、修之後綠（貼兩次輸出），根因寫在 Comments（產品還是測試）
- [ ] 尖峰與離峰各一條釘時鐘的測試；其他費用測試掃過、該釘的都釘了
- [ ] 在尖峰時段跑一次完整的 `pytest -m 'not e2e'` 綠（現在跑或用時鐘釘的方式證明），全部檢查綠
- [ ] 回頭補勾：`main` 的 CI 轉綠（協調者 push 後確認）
- [ ] progress.md 已更新

## Comments
