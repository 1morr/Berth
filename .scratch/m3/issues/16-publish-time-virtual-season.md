# 16 — 解析器：以發佈時間推測虛擬季

**Status:** ready-for-agent

**Blocked by:** 14（發佈時間已帶到規劃）

**讀:** plan §4.4、§4.6（benchmark）、§11.4（「M1 帶過來的一條」）；brief §6.4；`docs/research/profile-effect.md` §4；`docs/research/anime-episode-source.md` §6.4

## 做什麼

M1 票 06 刻意沒做的那一條：brief §6.4「以**發佈時間**推測虛擬季」（AutoBangumi v3.2 的做法）。當時解析器拿不到發佈時間，而 RSS item 一定帶著。

`mattpocock-skills:tdd`，benchmark fixture 就是紅燈：

- **自己的語料**：從票 07 的 fixture 與 Mikan 單一 feed 裡挑 split-cour、第二 cour 從 01 重數、TMDB 併成一季的作品，帶著發佈時間進 benchmark 語料。
- **規則**：發佈時間落在哪一個虛擬季（§4.4 的 180 天切法，不要調小）的播出區間，就用那個虛擬季換算。Candidate 標一個新的 `strategy`，信心至多 medium。
- 與票 14 的分工：這一條是**推測**，票 14 是**驗證**。推測錯了由驗證擋下，所以兩者要能同時存在而不互相抵銷；寫一條測試證明推測出的集數仍會被播出日比對檢查。
- 它要能分開 `profile-effect.md` §4 說的兩種讀法（第一季第 N 集 vs 後面某季從 01 重數），分不開的仍送審核。

解析器改動必跑 `berth bench`，`auto_wrong` 不得上升（專案 CLAUDE.md）。

## 驗收

- [ ] 新語料進 benchmark，改動前是紅的（貼改動前的 bench 輸出）
- [ ] 改動後 `berth bench` 的 `auto_wrong` 不升，新語料的自動入庫率提升（貼前後數字）
- [ ] 推測結果仍經過播出日比對（整合測試）
- [ ] plan §4.4 把「沒有做」那一句改成實際的規則
- [ ] lint、type、test 綠燈
