# 15 — 前端 e2e 閘門

**Status:** ready-for-agent

**Blocked by:** 13、14（前端改動收完才不會一直重寫腳本）

**讀:** plan §10（測試策略）、§9.3（精靈流程）、§11.3 的票 14 那一列；README（演練情境那一節）

## 做什麼

plan §10 現在寫的是實話：**「沒有腳本化的 playwright e2e」**（2026-09-22 改的，它從 M0 起就與
repo 不符）。這一票把它變成不實話——把 playwright 對演練情境跑精靈與送單腳本化進 CI。

範圍以**現有的演練情境**為底（README 已記：`inventory`、`long-lists` 等，`scripts/fake_setup_server.py`
起得來）：精靈走完 → 送單 → 等入庫。M2 新增的審核與修正流程至少各有一條（`/review` 確認一筆
audit、`/issues` 修一條 `library_link_missing`）——它們是 M2 最該有閘門的一批。

**排在 13 / 14 之後**：那兩票會動到媒體庫、詳情頁與清單元件，先寫腳本就是先寫一份要重寫的腳本。

**與後端 e2e 的關係**：`tests/e2e/` 那一套（compose + 真服務）是後端的，nightly 跑。這一票是
瀏覽器那一層，兩者不合併——共用 compose 環境但斷言的東西不同。

不做的話就維持 §10 現在的實話，那句話不准改。

## 驗收

- [ ] playwright 腳本在 CI 上跑得起來（貼 workflow run 連結與輸出）
- [ ] 至少四條：精靈走完、送單到入庫、`/review` 確認一筆 audit、`/issues` 修一條
      `library_link_missing`
- [ ] 腳本用的是演練情境（`scripts/fake_setup_server.py`），不打真的索引站與 TMDB
- [ ] 失敗時留得下證據（截圖或 trace），CI 上撿得到
- [ ] plan §10 那句話改成腳本化之後的實話，README 的演練情境那一節跟著更新
- [ ] 跑一次故意的失敗（改壞一個選擇器）確認它真的會紅
- [ ] lint、type、test 綠燈

## Comments
