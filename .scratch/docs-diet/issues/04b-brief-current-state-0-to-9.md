# 04b — brief 去歷史（上）：§0–§9

**Status:** ready-for-agent

**Blocked by:** 04a

**讀:** `.scratch/docs-diet/spec.md`（〈共同規則〉〈改寫規則〉）；brief §0–§9（約 455 行 48 KB）；`docs/adr/` 的索引（brief §19）

## 為什麼

brief 現在混著現況與演變史，讀的人要自己拼出哪句還有效。這張改寫 §0–§9：定位、路徑模型、管線、解析、命名、資料模型、刪除與修復。

## 做什麼

照 spec〈改寫規則〉改寫 §0–§9。章節與小節號不變（§9.1、§6.5、§6.4 等被 `berth/` 引用數十次）。

## 驗收

- [ ] 前後大小與歷史標記數貼 Comments；剩下的標記逐條有理由
- [ ] 對照表貼 Comments，§0–§9 每個【決定】、規則、數值都對到新版位置或 ADR
- [ ] 收尾 code-review 的 Spec 軸照對照表逐節比對舊版，結果貼 Comments
- [ ] 發現的矛盾列在 Comments 問使用者，沒有自己挑
- [ ] 全部檢查與 test 綠；progress.md 記一列 session；commit；不 push

## Comments
