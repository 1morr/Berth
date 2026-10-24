# 16 — M5 驗收

**Status:** ready-for-agent

**Blocked by:** 01–15

**讀:** plan §11.6 驗收；brief §17 M5 那一列；progress.md M5 的 session 紀錄與偏差

## 為什麼

逐條對 plan §11.6 的驗收，並用真的 Anthropic key 端到端跑一次。

## 做什麼

1. 逐條對驗收，每一條指到證明它的測試或實跑紀錄：
   - 側面板「訂閱這部的 Mikan RSS」「這部作品缺的集搜一下並下載」做得到，結果是卡片、撤銷得掉
   - 「加一個索引站」「把這部的 complete 刪掉」停在確認卡
   - `user` 碰不到管理員的命令
   - 照注入指令做的假模型被擋下
   - 用量頁看得到每次呼叫的 tokens 與快取命中率
   - 沒設 AI 憑證時行為與 M4 相同
2. 用真 key 實跑上面的對話（使用者提供 key），記下 tokens 與命中率，確認快取有吃到。
3. 里程碑收尾的 `mattpocock-skills:code-review`（從 M5 開工的 commit 起）；未處理的發現記到這張的 Comments。
4. PRODUCT.md 的路線圖把 M5 標成完成；CHANGELOG 整理；問使用者要不要發版。

## 驗收

- [ ] plan §11.6 每一條驗收都有對應證據
- [ ] 真 key 實跑紀錄附在票上（tokens、命中率）
- [ ] 里程碑 code-review 做完
- [ ] 全部檢查、pytest、vitest 綠；PRODUCT.md、CHANGELOG、progress.md 已更新
