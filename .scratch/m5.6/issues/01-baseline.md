# 01 — 基準：S1–S8 真模型跑一次

**Status:** done

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

- [x] S7、S8 在腳本裡，`--only S7,S8` 跑得起來
- [x] summary 有種子搜尋次數、要選 Route 的列數、skill 載入次數
- [x] 兩種接口的 S1–S8 與 S2 變體都跑過，研究文檔〈基準〉有數字表與品質結論
- [x] `scripts/experiments/README.md` 的說明跟上
- [x] 全部檢查、pytest 綠；progress.md 已更新

## Comments

- 舊的 Route 情境（M5 票 23b）本來就叫 `S7`，和這張票要的新 S7 撞名。改名 `S7-route`（沿用 `S2-mushoku` 的變體慣例），新的 S7／S8 照 spec 用掉這兩個編號；M5 封存文件裡提到的 S7 是舊情境。
- 驅動原本不送字幕組選擇；M5 票 26 之後訂閱卡會要人選，S1 的卡因此 422 `subgroup_required` 停在 pending。這張票補上：照模型預選的那一個送，也寫進逐字稿。
- S2 anthropic 第一次跑撞到模型端 `max_tokens` 4096 的暫時錯誤，換新 server 重跑成功；`S7-route` 第一次跑被前一個 S3 的下載污染（S3 已送整季《宝石の国》），另外開一台重跑。研究文檔的表格只用有效的列，丟掉的輪次約 $0.09。
- 新 S7 的基準：種子搜尋 11（anthropic）／10（openai），13 列卡 Route 13 次；S8：anthropic 0 次、openai 6 次。原對話的 18 次含 S7 沒有的模糊開頭，之後和 S7 的 10–11 次比，不和 18 比。
- 分兩段跑：S1–S6、S2 變體、`S7-route` 一段，`--only S7,S8` 一段；S8 排在 S7 前面（S7 下載同一部作品）。
