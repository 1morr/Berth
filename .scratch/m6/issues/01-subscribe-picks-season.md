# 01 — 以作品訂閱挑對那一季，發 0.5.2

**Status:** ready-for-agent

**Blocked by:** None (can start immediately)

**讀:** spec〈範圍〉M5.6 遺留第 1 點、〈共同規則〉；brief §20.29、§15〈從 Media 頁訂閱〉；`docs/research/agent-slimming-2026-11-06.md` §8〈已知缺陷〉；M5.6 票 08 的 Comments（`match_bangumi` 的設計）；plan §6〈agent〉

## 為什麼

0.5.1 已經發出去的缺陷：`rss.subscribe` 只收 `media_id` 與字幕組，`services.bangumi.match_bangumi` 拿作品的 `first_air_date` 比對 Mikan 番組頁的開播日。TMDB 一個條目、Mikan 每季一頁時挑到第一季，按下確認後 backfill 把舊集送進下載（實測《黑色五葉草》100 筆、《葬送的芙莉蓮》39 筆）。送出的 torrent 收不回，所以先修、先發版。

## 做什麼

1. **先量**（`mattpocock-skills:prototype`，腳本留在 `scripts/experiments/`）：對 Mikan 實頁重量一次 brief §20.29 的兩部作品，另找一部 split-cour 被拆成兩頁、一部 Mikan 的頁比 TMDB 的季粗的作品。記下每一頁的開播日與 TMDB 各季的 `air_date` 怎麼對得上，結果補進 brief §20.29（附來源）。
2. **定修法**：訂閱帶上「第幾季」，或比對被推薦那一季的 `air_date`（brief §20.29 的兩個方向），照第 1 步的資料選，理由寫進 Comments。對不上任何一頁、或一季對到不只一頁時怎麼辦也要定（傾向：問人，不猜）。
3. 實作（`mattpocock-skills:tdd`）：卡片說出挑到的是哪一頁、哪一季；給模型的工具 schema 跟著改時，`test_agent_tools.py` 一起改。
4. 用真模型重跑 S1 與 S6（`scripts/experiments/m5_acceptance_scenarios.py`，兩種接口），確認沒有送出舊集，數字補進研究文檔 §8。
5. **發 0.5.2**：CHANGELOG 收成 0.5.2、`pyproject.toml` 與 `uv.lock` 同步，tag 與 push 先問使用者（照 0.5.1 那一列的做法）。

## 驗收

- [ ] brief §20.29 的兩個情境挑到使用者要的那一季（整合測試，用替身 Mikan 頁）
- [ ] Mikan 實頁量過一次，結果與來源在 brief §20.29；split-cour 與「頁比季粗」各有一條測試
- [ ] 對不上或對到多頁時不自己挑（整合測試）
- [ ] 真模型重跑 S1、S6 沒有送出舊集，數字在研究文檔
- [ ] 全部檢查、pytest、vitest 綠；CHANGELOG 已收成 0.5.2；tag 與 push 已問過使用者

## Comments
