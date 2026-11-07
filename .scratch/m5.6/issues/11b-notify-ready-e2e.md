# 11b — 修「可以看了」真服務 e2e 的穩定紅

**Status:** ready-for-agent

**Blocked by:** —

**讀:** 票 11 的 Comments（三次斷言、main nightly 的兩次紅、resolver 線索）；`tests/e2e/`（含 `stack.py`）、`pipeline/`、`services/notify.py`、`docs/development/e2e.md`

## 為什麼

票 11 跑真服務 e2e（`pytest -m e2e`）三次，都是 27 passed／1 failed，紅的一直是
`test_an_rss_hit_tells_the_crew_it_is_downloading_then_ready_to_watch`（「可以看了」600 秒內沒到）。
main 的 nightly e2e 在 2026-11-05、11-06 也紅在同一條，兩次都早於 M5.6 的任何 commit（M5.6 從 11-07 08:43 UTC 起），
`pipeline/` 與 `services/notify.py` 自 v0.5.0 起沒改過——所以不是這批造成的，但它是穩定紅，會擋住票 11 的
「`pytest -m e2e` 綠」。

## 做什麼

1. **先分清是產品的問題還是測試的問題**：重現那一條（`pytest -m e2e -k an_rss_hit` 這類最小指令），
   把失敗現場留住——要留容器與 volume 就在本分支暫改 `tests/e2e/stack.py` 的收尾（暫改不進 commit）或手動
   compose；讀服務 log、通知排程與 resolver 的流程，寫出「哪一步沒有發生、為什麼」。
2. **先有會紅的 repro 才修**：repro 寫進本票 Comments（指令、失敗的斷言、失敗現場在哪）。只把 600 秒拉長而
   說不出原因的不收。
3. 修法依根因落在產品或測試：產品就同輪補測試與文件（`docs/development/e2e.md`；行為對使用者可見才動
   CHANGELOG），測試就修測試並說明為什麼不是產品的問題。
4. 修完那一條**連跑三次都綠**，再跑一次整套 `pytest -m e2e`。
5. 一併把票 11 需要的重跑做掉：修完回報協調者，票 11 的 session 會 merge main、重跑 `pytest -m e2e` 與最後一輪
   全部檢查，然後才補勾「`pytest -m e2e` 綠」並封存（那一勾不在這張票）。

## 驗收

- [ ] 會紅的 repro 寫在票的 Comments（指令、失敗斷言、失敗現場位置）
- [ ] 根因寫清楚，且分清是產品還是測試
- [ ] 修法有測試或實跑證據；沒有只放寬逾時
- [ ] 紅過的那一條連跑三次都綠，整套 `pytest -m e2e` 也綠
- [ ] 全部檢查、pytest 綠；`docs/progress.md` 已更新

## Comments

- 2026-11-07 協調者：票 11 的真服務 e2e 三次都紅在同一條；依協調者規則（穩定紅一律插修復票）插這張，
  排在票 11 封存之前。票 11 已把三次斷言、nightly 的兩次紅與 resolver 線索寫在它的 Comments。
