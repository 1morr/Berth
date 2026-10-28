# 23c — 系列對照的整季標記做進程式（等 A/B 結果決定做或取消）

**Status:** blocked

**Blocked by:** 23b；`docs/research/agent-sources-ab-2026-10-28.md`（精簡組 vs 完整組的真模型比較，使用者 2026-10-28 要求）

**讀:** 票 23b 的〈做什麼〉第 1、2、5 點（從那裡拆出來）；`docs/research/fribb-vs-chaining-2026-10-28.md`；`docs/research/m5-acceptance-2026-10-28.md` 情境 2 的三個變體；`berth/skills/series-mapping/SKILL.md`

## 為什麼

票 23 的真模型只標出部分「兩種算法不一致」的季；使用者決定把比對做進程式（票 23b 第 1、2 點）。之後使用者要先用真模型比較「只有網路搜尋 + TMDB」與「再加 AniList / Fribb / Bangumi」——比較若顯示這三個來源可以拿掉，這張就**取消**（改成拿掉來源的票）；若要留，就照下面做。23b 先只做 Route 卡片，這部分拆到這裡。

## 做什麼（只在 A/B 結論是「留」時做）

1. 伺服器端的系列對照工具：輸入 AniList 條目與 TMDB 作品，算出每個 TV 條目的 A（Fribb）、B（照 AniList 集數串接），每一季給 `needs_review` 與原因（任一列不一致、B 超出那一季集數、那一季沿用連續編號）；與 `scripts/experiments/fribb_vs_chaining.py` 共用判定，不寫兩份。Fribb 不可用時只回 B、所有季標「未經對照表」。
2. `series-mapping` 第 3 步改成照抄這支工具的範圍與標記。
3. 測試：Re:Zero 第二季、無職轉生第二季前後半、HxH 2011 的 `needs_review` 與研究結論一致（研究的回應快取已不在，要用 `TMDB_API_KEY` 重錄 fixture）；改壞會紅。
4. 真模型兩種接口重跑情境 2 的三個變體：該標的季全部標出、沒有誤報；補進 `docs/research/m5-acceptance-2026-10-28.md`。

## 驗收

- [ ] A/B 結論已讀，決定做或取消寫在 Comments（取消就改 Status 為 cancelled 並開拿掉來源的票）
- [ ] （做的話）工具在伺服器端算出整季標記，與研究一致（測試，改壞會紅）；skill 照抄
- [ ] （做的話）真模型重跑三個變體：該標的全標、沒有誤報
- [ ] 全部檢查、pytest、vitest 綠；progress.md 已更新

## Comments
