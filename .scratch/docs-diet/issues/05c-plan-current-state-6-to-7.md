# 05c — plan 去歷史：§6–§7（API 面、前端）

**Status:** ready-for-agent

**Blocked by:** 02, 04a

**讀:** `.scratch/docs-diet/spec.md`（〈共同規則〉〈改寫規則〉）；plan §6–§7（只有 63 行卻有 83 KB，§6 平均一行 1.6 KB）；`docs/adr/` 的索引（brief §19）；改寫時遇到引用 brief 的地方才讀那一節

## 為什麼

plan 每行平均 330 bytes，117 處日期、1,007 處「票 NN」、12 處「推翻」混在規格裡，讀的人要自己拼出現況。plan 太大，按章節拆成 05a–05e，可以並行，後做的先 rebase。§6 是最難讀的一節：44 行 70 KB。

## 做什麼

照 spec〈改寫規則〉改寫 plan §6–§7。章節與小節號不變（§6 被 `berth/` 引用 119 次）。§6 的表格一列一個端點群，長說明拆到表下的清單；端點與欄位對照 `web/src/api/schema.d.ts` 確認現況。

## 驗收

- [ ] 前後大小與歷史標記數貼 Comments；剩下的標記逐條有理由
- [ ] 對照表貼 Comments，§6–§7 每個決定、規則、欄位、端點、數值都對到新版位置或 ADR
- [ ] 收尾 code-review 的 Spec 軸照對照表逐節比對舊版，結果貼 Comments
- [ ] 發現 plan 與 brief 的矛盾列在 Comments 問使用者，沒有自己挑
- [ ] 全部檢查與 test 綠；progress.md 記一列 session；commit；不 push

## Comments
