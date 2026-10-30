# 04c — brief 去歷史（下）：§10–§18

**Status:** ready-for-agent

**Blocked by:** 04a

**讀:** `.scratch/docs-diet/spec.md`（〈共同規則〉〈改寫規則〉）；brief §10–§18（約 270 行 76 KB，最大是 §16.3、§16.4 共 32 KB）；`docs/adr/` 的索引（brief §19）

## 為什麼

同 04b。這張改寫 metadata、帳號、播放、頁面、AI 與通知、RSS、部署、里程碑、延後清單。

## 做什麼

照 spec〈改寫規則〉改寫 §10–§18。章節與小節號不變（§16.4、§15、§11 各被 `berth/` 引用 60–100 次）。

- §17 里程碑：已驗收的寫一句加 archive 連結，M6、M7 照現況。
- 和 04b 可以並行，但兩張都改 brief：後做的先 rebase。

## 驗收

- [ ] 前後大小與歷史標記數貼 Comments；剩下的標記逐條有理由
- [ ] 對照表貼 Comments，§10–§18 每個【決定】、規則、數值都對到新版位置或 ADR
- [ ] 收尾 code-review 的 Spec 軸照對照表逐節比對舊版，結果貼 Comments
- [ ] 發現的矛盾列在 Comments 問使用者，沒有自己挑
- [ ] 全部檢查與 test 綠；progress.md 記一列 session；commit；不 push

## Comments
