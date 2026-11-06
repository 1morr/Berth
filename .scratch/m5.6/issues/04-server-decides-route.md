# 04 — 模型不給 `route_id`，Route 由伺服器在提出時定

**Status:** ready-for-agent

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

- [ ] 三支會送進 Route 的命令，給模型的工具 schema 都沒有 `route_id`（`test_agent_tools.py`）
- [ ] 作品可選一條：提出成功、卡片不用選、執行用那一條；兩條：`RouteAsk` 預選上次用的；零條：提出被拒、理由交給模型（整合測試）
- [ ] 升級前存下、參數帶 `route_id` 的 Proposal 照樣核准與執行（整合測試）
- [ ] 模型的工具清單沒有 `media.route_choices`；`read_media` 給模型的輸出沒有 Route 欄位
- [ ] skill 沒有 Route 段落；brief §14、plan §6、§7 已改
- [ ] 全部檢查、pytest、vitest 綠；progress.md 已更新（推翻 plan §7 的那句記一條偏差）

## Comments
