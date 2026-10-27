# 23 — M5 驗收

**Status:** ready-for-human

**Blocked by:** 15, 22

**讀:** plan §11.6〈驗收〉；brief §17 的 M5 列；`docs/research/m5-prototype-2026-10-27.md`（驗收用同一套情境）；`scripts/experiments/m5_agent_scenarios.py`；`docs/development.md`〈e2e〉〈前端 e2e〉

## 為什麼

M5 的驗收有兩半：
- **決定性的**：假模型＋整合測試＋前端 e2e。
- **真模型的**：用使用者的 key 實際跑情境，要使用者提供 key 與時間，所以這張是 `ready-for-human`。

## 做什麼

1. **決定性的**：plan §11.6〈驗收〉逐條對到一條測試或一次 playwright 實跑。缺的補上。
   - 不可逆、`connects_out`、`downloads` 只能經確認卡（含注入）。
   - 重啟之後舊卡片還按得下去；壓縮之後卡片還在。
   - 每一輪的數字，含被中止的那一輪。
   - 防護各觸發一次。
   - 一般使用者的門禁。
   - 沒設 provider 時與 M4 相同：全套 test 綠，前端 e2e 照舊。
2. **真模型的**：
   - 把 `m5_agent_scenarios.py` 改成打產品的 `/agent/chat` 與 Proposal API，或另寫一支。
   - 用使用者的 key，對 Fake 後端 `search` 情境（真 TMDB、真索引站、替身 qBittorrent）跑情境 1–6。兩種接口要各自一台全新的 Berth（prototype 的教訓）。
   - 數字與逐字稿記在 `docs/research/`，對照 prototype 的那一份。
3. **真服務 e2e**：`TMDB_API_KEY` 已有，跑一次 `pytest -m e2e`，確認 M4 的 e2e 沒被弄壞。
4. 收尾：plan、brief、CHANGELOG、progress.md；要不要發版、push，先問使用者。

## 驗收

- [ ] plan §11.6〈驗收〉每一條都有對應的測試或實跑紀錄（列在 Comments）
- [ ] 真模型情境 1–3 走完，Re:Zero 全系列分批送出正確（數字與逐字稿在 `docs/research/`）
- [ ] `pytest -m e2e` 綠（貼輸出）
- [ ] 全部檢查、pytest、vitest、前端 e2e 綠；CHANGELOG、progress.md 已更新

## Comments
