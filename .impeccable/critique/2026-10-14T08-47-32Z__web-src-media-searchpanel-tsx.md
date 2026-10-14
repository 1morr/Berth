---
target: 作品頁搜尋區塊（票 84b 後）
total_score: 30
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 0
target_identity: "file:C:\\Users\\Roxy\\orca\\projects\\MediaServer\\web\\src\\media\\SearchPanel.tsx"
target_fingerprint: "sha256:ebcc118f51cac10e053c8c60240b806ad62b9d7c4f7879c3fb3d9c93b0556d1a"
target_path: "C:\\Users\\Roxy\\orca\\projects\\MediaServer\\web\\src\\media\\SearchPanel.tsx"
timestamp: 2026-10-14T08-47-32Z
slug: web-src-media-searchpanel-tsx
---
# 搜尋區塊（送出前）critique：票 84b 前後

Method: dual-agent（A 設計審查、B 偵測器與瀏覽器 overlay）

前版（HEAD）28/40；後版（工作樹）30/40。差在 #4 Consistency 2→3（兩條標籤軸收成一條、預覽有欄位標籤）、#8 Aesthetic 2→3（名字不再印兩次、四行同權重散文收成標籤＋清單＋一句）。

偵測器：CLI 對 SearchPanel.tsx、QueryChoices.tsx 0 條；overlay（tv 1280/390、movie 1280）No anti-patterns found；390 無橫向捲動。

後版優先問題：
1. [P2] 停用原因離搜尋鍵太遠（兩版都有；動關鍵字列需另外拍板）
2. [P2] 打了關鍵字時 chip 看起來仍有效（票 84b 刪了「只會問這一個」）
3. [P2] 被拒時標籤仍寫「會問 · 12 個查詢」（措辭是設計決定）
4. [P2] 缺集模式搜尋中預覽與纜繩可能是舊的（兩版都有，要先 repro）
5. [P3] 缺集範圍句與標籤都說「會問」；代價句在 max-w-prose 處把「追蹤站」拆行
