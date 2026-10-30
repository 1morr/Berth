# 05a — plan 去歷史：§0–§2（慣例、架構、資料模型）

**Status:** ready-for-agent

**Blocked by:** 02, 04a

**讀:** `.scratch/docs-diet/spec.md`（〈共同規則〉〈改寫規則〉）；plan §0–§2（約 165 行 41 KB，§2 資料模型 34 KB）；`docs/adr/` 的索引（brief §19）；改寫時遇到引用 brief 的地方才讀那一節

## 為什麼

plan 每行平均 330 bytes，117 處日期、1,007 處「票 NN」、12 處「推翻」混在規格裡，讀的人要自己拼出現況。plan 太大，按章節拆成 05a–05e，可以並行，後做的先 rebase。

## 做什麼

照 spec〈改寫規則〉改寫 plan §0–§2。章節與小節號不變（`berth/` 引用 §2.2–§2.4 各 30–50 次）。§2 的欄位清單對照 `berth/models/` 確認現況，plan 與程式不符時照程式寫，並列在 Comments。

## 驗收

- [ ] 前後大小與歷史標記數貼 Comments；剩下的標記逐條有理由
- [ ] 對照表貼 Comments，§0–§2 每個決定、規則、欄位、端點、數值都對到新版位置或 ADR
- [ ] 收尾 code-review 的 Spec 軸照對照表逐節比對舊版，結果貼 Comments
- [ ] 發現 plan 與 brief 的矛盾列在 Comments 問使用者，沒有自己挑
- [ ] 全部檢查與 test 綠；progress.md 記一列 session；commit；不 push

## Comments
