# 04 — 模型不給 `route_id`，Route 由伺服器在提出時定

**Status:** done

**Blocked by:** 01、03

**讀:** spec〈範圍〉A4、〈共同規則〉；研究文檔 §4 A4；brief §14〈對話裡的確認卡〉；plan §6〈proposals〉、§7〈確認卡〉；`services/proposals.py` 模組 docstring（第 2、3 點）

## 為什麼

M5 票 23b 之後，模型給的 `route_id` 本來就不算數：可選的不只一條時由人在卡片上選。模型還是得先查 `media.route_choices` 再填一個，四個 skill 也各寫了一段 Route 的說明。這些對模型來說都是不必要的負擔。

## 做什麼

1. **設計先行**（`mattpocock-skills:codebase-design`）：`route_id` 從「模型看到的輸入」拿掉要切在哪一層（登錄表推出的輸入模型、`agent_tools` 的工具 schema，還是 `proposals.propose`），三支 `sends_into_a_route` 的命令要一起適用。另外要決定 Route 還沒定時 Proposal 存下的參數與 `arguments_hash` 怎麼算、提出時的乾跑用哪一條 Route。結論寫進 Comments 與 `proposals` 模組 docstring。
2. 提出時：可選的只有一條就用它；不只一條就出 `RouteAsk`（預選照舊，模型給的不算）；零條就拒絕（沿用現有的拒絕理由，查定後寫進 Comments），理由交給模型。
3. 人在 UI 上手動送單（作品頁）照舊自己帶 `route_id`，不受影響。
4. 給模型的工具清單拿掉 `media.route_choices`（命令留著，`route_offer` 與 UI 在用）；`media.read_media` 給模型的那一份拿掉 `routes`、`default_route_id`，工具說明跟著縮短。
5. 確認卡上只有一條可選的列，要能從預覽（不是模型給的參數）顯示那一條 Route 的名字。
6. 四個 skill 裡的 Route 段落刪掉（`test_skills.py` 的工具宣告跟著改）。
7. 文件：brief §14、plan §6〈proposals〉、§7〈確認卡〉「一條的照模型給的」那句與「Route 由人在卡片上選」。

## 驗收

- [x] 三支會送進 Route 的命令，給模型的工具 schema 都沒有 `route_id`（`test_agent_tools.py`）
- [x] 作品可選一條：提出成功、卡片不用選、執行用那一條；兩條：`RouteAsk` 預選上次用的；零條：提出被拒、理由交給模型（整合測試）
- [x] 升級前存下、參數帶 `route_id` 的 Proposal 照樣核准與執行（整合測試）
- [x] 模型的工具清單沒有 `media.route_choices`；`read_media` 給模型的輸出沒有 Route 欄位
- [x] skill 沒有 Route 段落；brief §14、plan §6、§7 已改
- [x] 全部檢查、pytest、vitest 綠；progress.md 已更新（推翻 plan §7 的那句記一條偏差）

## Comments

- **切在哪一層（設計先行）**：切在「給模型的卡片列 schema」（`services/agent.py` 的 `SubmitRow`、
  `SearchSubscriptionRow`，與 `card_input` 替其餘命令推出的 `_card_row`），不是登錄表推出的命令輸入
  模型。命令照舊收 `route_id`：作品頁與 API 的手動送單在用（票面第 3 點），`sends_into_a_route` 也靠
  它認這三支。`proposals.propose` 收下已驗證的列之後，自己補 `route_id`。
- **存下的參數與 `arguments_hash`**：提出時就把伺服器定的 Route 寫進參數，存下的是完整的一份，
  雜湊照它算（重算比對的規則不變）。不只一條時乾跑用「上次用的先試、其餘照 id」第一條過得去的；
  那一條只是佔位，`decide` 時人選的那一條照舊蓋過它（`routes_json`）。升級前存的卡（參數本來就有
  `route_id`）原樣通過，不回填。
- **乾跑用哪一條**：見上；都過不去就拒絕，理由取最後試的那一條（不會挑一條紅的當唯一答案）。
- **零條的理由**：沿用命令自己宣告的 `route_missing`（`JobRefusal` 與 `RssRefusal` 同一個值），
  `detail` 是作品的 `media_id`；`media_id` 認不得、或 Media 不在時是 `media_missing`（同一個 enum，
  同一個 detail）。這三支原本沒有「一條都沒有」的情況——模型總會給一個 id，再由乾跑擋它。
  `route_missing` 的定義補上「這部作品一條放得進的 Route 都沒有」（`domain/enums.py`）。
- **預覽多一格 `single_routes`**：只有一條時是 `{id, name}`，卡片照它印名字（不從存下的參數讀）。
  舊的卡沒有這一格，`_view` 當空的。
- **測試**：`test_agent_tools` 三支命令的 schema 與 `read_media` 的模型視圖；`test_proposal_routes`
  的一條／兩條／零條／升級前存的卡；`test_agent_injection`、`test_agent_write_tools` 的假模型不再查
  `media.route_choices`；`scripts/fake_setup_server.py` 同步。驗證：pre-commit 全過、pytest 5752
  passed / 1 skipped、vitest 2440 passed、agent e2e（桌機與 390）34 passed。
- **code-review 之後補的**：三支寫入工具的 `about` 拿掉「Route 要對得上作品種類」（模型不再決定，
  這句話只讓人誤會）；`media.route_choices` 本來沒有呼叫端，`route_offer` 改成叫它（票面說它在用，
  現在真的在），命令留著給 M7 的命令清單；`agent_origins.ID_FIELDS` 拿掉 `route_id`，與 plan §7
  〈守法〉一致；測試的送單列照模型實際給的形狀（沒有 `route_id`），「一條就用它」才是真的證明。
  未處理的取捨：`_prepare` 仍回四個等長的逐列序列（與 `ProposalPreview` 的逐列 tuple 同一個形狀，
  不另外造型別）、Route 政策與乾跑編排留在同一支（約 60 行，一起改的理由只有一個）；CHANGELOG 已補。
