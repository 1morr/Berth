# 01 — 基準：S1–S8 真模型跑一次

**Status:** ready-for-agent

**Blocked by:** None (can start immediately)

**讀:** spec〈範圍〉〈共同規則〉；研究文檔 §1、§5；`scripts/experiments/m5_acceptance_scenarios.py` 開頭的說明；`docs/archive/m5.md` 裡 M5 驗收的逐項檢查（S1–S6、S2 變體）

## 為什麼

M5.6 的每一項改動都要和改動前比。數字要在任何會影響模型行為的票之前量，否則最後比不出工具改動和提示改動合起來的效果。

## 做什麼

1. 在 `m5_acceptance_scenarios.py` 加情境 S7，照 conversation `b0e4f028` 改寫成固定句子（腳本不會臨場回話）：先要下載《想吃掉我的非人少女》，再指定喵萌奶茶屋繁中單集、直接出卡。沿用同一支腳本，不另開一支。
   再加 S8，照原對話的模糊開頭：第一句「幫我找想吃掉你的那個什麼動漫」，第二句更正成《想吃掉我的非人少女》，兩句都不說要下載。S8 量的是還沒說要下載就搜種子（票 07 的 B4），S7 量不到這一點。
2. summary 多三個數字：種子搜尋次數（`search_search_torrents` 的呼叫數；S8 兩句都沒說要下載，搜了幾次都算）、卡片上要人選 Route 的列數、skill 載入次數。舊有的工具呼叫數、input token、費用照舊。
3. 兩種接口各跑 S1–S8 與 S2 的三個變體。缺 key 時問使用者。
4. 摘要寫進研究文檔新的一節〈基準〉：每個情境的數字表，加上照 M5 驗收逐項檢查的品質結論（S2 變體的範圍標記要記清楚，之後要比）。

## 驗收

- [ ] S7、S8 在腳本裡，`--only S7,S8` 跑得起來
- [ ] summary 有種子搜尋次數、要選 Route 的列數、skill 載入次數
- [ ] 兩種接口的 S1–S8 與 S2 變體都跑過，研究文檔〈基準〉有數字表與品質結論
- [ ] `scripts/experiments/README.md` 的說明跟上
- [ ] 全部檢查、pytest 綠；progress.md 已更新

## Comments
