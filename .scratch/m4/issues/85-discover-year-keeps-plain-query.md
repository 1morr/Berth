# 85 — 探索搜尋：片名結尾是數字的作品（Space 1999）照樣找得到

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** M4 票 69 的 Comments〈已知限制〉最後兩條、〈決定〉的「探索的年份」；`berth/services/discover.py`（年份拆分、`search_year`）；`tests/integration/test_discover.py` 的 `TestSearchWithAYear`；brief §20.19

## 為什麼

票 69 讓「Nosferatu 1922」找得到東西：結尾是年份時，拆成片名加年份去問 TMDB，那一年**完全沒有結果**才退回原字串。

但片名本身以數字結尾的作品會被拆錯：
- 「Space 1999」被拆成片名 `Space`、1999 年。那一年有別的片，就不會退回，真正的《Space: 1999》找不到。
- 「the 1975」也一樣。

## 做什麼

- 結尾是年份時，拆開問（片名加年份）的同時，也照原字串問 `search/multi`，兩份合併去重。
- 排序：拆開問的結果排前面，原字串的結果接在後面。這是為了讓「Nosferatu 1922」照舊第一筆就是 1922 那部。
- 沒有年份的搜尋不變。

## 驗收

- [ ] 「Space 1999」的結果裡有《Space: 1999》（假 TMDB 回應）；「Nosferatu 1922」第一筆照舊是 1922 那部；pytest 守，做變異驗證
- [ ] 實跑：真的 TMDB 搜「Space 1999」與「Nosferatu 1922」，附結果（不得在任何輸出印出 TMDB key）；用隔離環境，**不准碰使用者的 `berth-local`**
- [ ] 全部檢查、pytest、vitest 綠；CHANGELOG、progress.md 已更新

## Comments
