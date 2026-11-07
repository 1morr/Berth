---
target: web/src/agent/AgentPanel.tsx (M5.6 票 10b 側面板與拖寬把手)
total_score: 28
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 2
p2_count: 2
p3_count: 1
target_identity: "file:/Users/roxy/orca/workspaces/Berth/t10b/web/src/agent/AgentPanel.tsx"
target_fingerprint: "sha256:35b7cf07ed7871e7c60a8998b66db7842cb11d80a31ca8ea19733ab810325f57"
target_path: /Users/roxy/orca/workspaces/Berth/t10b/web/src/agent/AgentPanel.tsx
timestamp: 2026-11-07T10-46-31Z
slug: web-src-agent-agentpanel-tsx
---
# 助理側面板與拖寬把手 critique（M5.6 票 10b）

Method: dual-agent (A: 設計審查 · B: 偵測器＋瀏覽器證據)

## Design Health Score

| # | 原則 | 分 | 關鍵問題 |
|---|------|----|----------|
| 1 | 系統狀態可見 | 3 | 拖動中沒有寬度讀數，只有版面跟著跑 |
| 2 | 貼近真實世界 | 3 | 拖邊緣是通用心智模型，但沒有握把讓人「看見」它 |
| 3 | 使用者控制與自由 | 3 | 可拖回、會夾限；雙擊不回預設、沒有重設 |
| 4 | 一致性與標準 | 2 | 站上其他互動都用字自報家門，只有這顆把手靜止時不說話 |
| 5 | 錯誤預防 | 3 | 壞值回預設、拖動不選字；1024 寬仍可讓面板吃掉 40rem |
| 6 | 辨識而非回想 | 2 | 靜止時與面板的 2px 分隔線完全融為一體，要 hover 才知道 |
| 7 | 彈性與效率 | 3 | 1:1 跟手、`Shift` 4rem、記住寬度；沒有回到預設的快捷 |
| 8 | 美學與極簡 | 4 | 純 2px、`ink`、無陰影無圓角 |
| 9 | 錯誤辨識與復原 | 3 | 到上下限毫無回饋，分不出「到底了」還是「壞了」 |
| 10 | 說明與文件 | 2 | 只有 `aria-label`，`aria-valuenow` 是裸數字（26，沒有單位） |
| **Total** | | **28/40** | **需改善帶（24–29）** |

## Design Specificity Verdict

LLM：不夠專屬。面板殼與把手換到任何有側邊聊天欄的產品都不會顯得不對；Berth 的語彙在這裡只剩一條線，
且違反〈The Summary Is One Button Rule〉。機制層面則是少見地正確。

Deterministic scan：CLI `detect` 0 findings（exit 0）；瀏覽器 overlay 注入成功，桌面 1280 與 390 各一次，
`[impeccable] No anti-patterns found.`，DOM 沒有任何 anti-pattern 標記。沒有 false positive。

## Overall Impression

機制比多數產品的分隔把手正確，但可發現性是核心，而它最弱：靜止時畫面上不存在這個控制。

## What's Working

1. 機制正確：pointer capture、`event.buttons === 0` 補救、四捨五入、try/catch；1:1 跟手、不選字。
2. hover 兼任拖動回饋：拖動全程保持高亮。
3. 無障礙底子：`aria-valuenow/min/max`、24px 命中區、鍵盤到得了、390 時不渲染。

## Priority Issues

- [P1] 靜止時零可發現性：rest 是透明的，只剩與所有分隔線同款的線。Fix：中段加握把刻記或 `.label` 文字。
- [P1] 拖動無讀數、無重設、到界無回饋：拖動／聚焦時顯示 `.value` 寬度、雙擊回 26rem。
- [P2] 上限 40rem 不看視窗：1024 寬拖到 40rem，頁面剩 384px、頁首長到 246px。
- [P2] 命中區越界 12px：`elementFromPoint(886)` 是把手不是頁面；目前頁面的 `px-6` 邊距擋著。
- [P3] 語意缺口：`aria-valuenow` 沒有單位與步進說明；focus 只靠描邊。

## Persona Red Flags

- Jordan（第一次用）：永遠不會發現能拉寬，會去拉瀏覽器視窗。
- Alex（重度使用者）：直覺雙擊邊緣求重設（目前無效）、拖到 40rem 得到沉默。
- 鍵盤／讀屏：到得了、方向鍵有效，但聽到「調整側面板寬度 26」，沒有單位與上下限。

## Minor Observations

- 40rem 時抬頭列變 640px 的空曠橫條。
- 390 與 768 都走全螢幕，平板直向沒有拉寬能力（`lg` 門檻）。
- 確認卡貼底決策列在 24／40rem 都會壓到列上——票 10 的範圍。
- 舊 conversation id 404 讓面板進失敗狀態（資料復原問題，非設計）。

## Questions to Consider

1. 如果這個把手永遠沒人找到，它算功德還是算雜訊？
2. 寬度是「這次任務的需要」還是「跨 session 的偏好」？
3. 站上每顆互動都用字說出自己，為什麼這一顆例外？
