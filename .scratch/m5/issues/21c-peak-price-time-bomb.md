# 21c — 修復：DeepSeek 尖峰時段讓 21b 的計價測試變紅

**Status:** done

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

- [x] repro 修之前紅、修之後綠（貼兩次輸出），根因寫在 Comments（產品還是測試）
- [x] 尖峰與離峰各一條釘時鐘的測試；其他費用測試掃過、該釘的都釘了
- [x] 在尖峰時段跑一次完整的 `pytest -m 'not e2e'` 綠（現在跑或用時鐘釘的方式證明），全部檢查綠
- [x] 回頭補勾：`main` 的 CI 轉綠（協調者 push 後確認：run 40626515132 success，sha bf17f0b8）
- [x] progress.md 已更新

## Comments

- 2026-10-28 實作（session 紀錄在 progress.md）。
- **根因：測試，不是產品。** 記帳（`services/agent_books.call_row`）本來就照 `response.timestamp` 查價。pydantic-ai 2.62 的真實串流路徑（`AnthropicModel`、`OpenAIChatModel`）在第一個片段到了之後才建 `StreamedResponse`，`timestamp` 一律是那一刻的本機時鐘（`_utils.now_utc()`），服務端的 `created` 只進 `provider_details`；所以「照回應時間計價」就等於「照收到第一個片段那一刻」，用量頁沒有算錯。測試用的 `FunctionModel` 串流同樣用本機時鐘，`FakeAi` 只轉送 parts，腳本給的 `timestamp=OFF_PEAK` 留不下來，測試以為控制得了時段、其實是看跑測試的時間。這條事實補進 brief §20.24（附原始碼位置）。與票 22 的診斷一致（協調者轉述，22 的 commit `3dfb7b36`）。
- 修法照協調者定的：**釘時鐘**。中途一度改替身讓串流帶腳本的時間（repro 因此轉綠），但真服務沒有這個能力，等於讓測試控制一個不存在的東西，撤掉了；`FakeAi` 只在說明裡寫明「串流時間是開始串流那一刻，控制時段要釘時鐘」。
- repro（修之前，`test_a_call_is_priced_by_the_endpoint_it_went_to` 把時鐘釘在週三 02:42 UTC，腳本仍給 `timestamp=OFF_PEAK`），與 CI 一模一樣：
  ```
  FAILED tests/integration/test_agent_web_search.py::TestTheBooks::test_a_call_is_priced_by_the_endpoint_it_went_to
  E       assert 1.74e-05 == 8.7e-06 ± 8.7e-12
  ```
  修之後（那條改成釘在離峰、拿掉腳本的時間；新增 peak / off-peak 兩條）：
  ```
  test_server_side_searches_on_the_official_endpoint_are_counted_and_priced PASSED
  test_other_endpoints_count_searches_but_leave_their_price_out PASSED
  test_a_call_is_priced_by_the_endpoint_it_went_to PASSED
  test_a_call_is_priced_at_the_hour_it_was_answered[peak] PASSED
  test_a_call_is_priced_at_the_hour_it_was_answered[off-peak] PASSED
  test_an_empty_base_url_records_the_official_one PASSED
  test_a_reply_without_searches_records_zero PASSED
  7 passed
  ```
- 尖峰 / 離峰兩條：`test_a_call_is_priced_at_the_hour_it_was_answered[peak|off-peak]`，預期值是 brief §20.24 的官方價（$0.3 / $1.2、$0.15 / $0.6），不是用 `cost_of` 重算。變異：記帳改成永遠用離峰時間 → `[peak]` 紅。
- 掃過的檔（`cost_usd`、`cost_of`、`price_of`、`approx(`、`0.15`、`0.6`、`deepseek`）：
  - 釘了：`test_agent_web_search.py::test_other_endpoints_count_searches_but_leave_their_price_out`——它的 `priced()` 照 `row.created_at`（記帳那刻）重算，產品照回應那刻，跨過尖峰邊界兩邊不一樣。
  - 不用釘：`tests/unit/test_ai_prices.py`（每次都帶 `at`）、`tests/integration/test_usage.py`（傳 `now=`）、`test_agent_api.py`（用量頁比的是 `ai_calls` 的加總、Anthropic 官方價；L921 的 DeepSeek 只斷言非 NULL）、`test_ai_settings_api.py`（Anthropic 價不分時段、DeepSeek 只斷言 vendor）、`test_agent_write_tools.py`、`test_ai_adapter.py`（不斷言費用）、`tests/unit/test_spend_alerts.py`（0.15 是提醒門檻）、`web/src/usage/prices.ts` 與 `web/` 的頁面測試（fixture 資料，不讀時間）、同檔的官方端點那條（Anthropic 不分時段）。
- 完整 `pytest -m 'not e2e'` 在真實尖峰跑（週三 02:59–03:09 UTC，5150 passed；改成釘時鐘之後 03:12–03:22 UTC 再跑一次，5150 passed）；`pre-commit run --all-files` 全綠。
- code-review 已修：三條 DeepSeek 測試重複的 `turn_ai_on(...)` 抽成 `turn_deepseek_on`。其餘發現（`_Scripted` 的命名、`stamps` 的 push / pop、`Any` 沒註原因）都針對後來撤掉的替身改動，不適用。
- 未處理：無。
