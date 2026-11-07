# 07 — 共同規則進系統指示，skills 5 → 3

**Status:** done

**Blocked by:** 04、05、06

**讀:** spec〈範圍〉B1–B4、〈共同規則〉；研究文檔 §2、§3、§4 B（草稿都在那裡）；brief §14（skills）；plan §6〈agent〉

## 為什麼

5 個 skill 加起來 351 行，同一段話重複出現 3–4 次（搜尋語言、Route、卡片的說法、重建帳本、`in_jellyfin` 的意思），而且點名了特定作品。照分層原則重新分配：共同規則寫一次在系統指示，skill 只寫決策順序。

## 做什麼

1. **B1、B4**：研究文檔 §4 B1 的草稿加進 `services/agent.py` 的 `INSTRUCTIONS`（英文），其中包含「只在使用者要下載或問有什麼時才搜種子」這一條。
2. **B2**：`download`（取代 `missing-episodes`、`series-mapping` 與 `new-season-picks` 第 8 步，≤ 30 行）、`recommend`（取代 `new-season-picks`，≤ 20 行）。`subscribe` 先只刪掉已經進系統指示的段落與 Route 段落，改寫留給票 09。照研究文檔的草稿寫，依 04–06 的結果調整（`contains`、`episodes`、沒有 Route）。
3. `why-not-imported` 不再是 skill：結論的意思，以及「唯讀、先說結論、最後給下一步」，寫進 `why_not.explain` 的工具說明。
4. **重建帳本的指引只留一處**：`media.read_media` 給模型的輸出在 `in_jellyfin` 佔一整季以上時帶一個 `hint`（格式在這張票定，寫進 Comments 與 plan §6）。skill 與系統指示都不再寫。
5. **B3**：skill 不點名作品，只寫通則。
6. **閘門**：`test_skills.py` 加上 skill 總行數上限（≤ 80，加上票 09 要寫的 `subscribe`），並做雙向變異驗證（超過上限會紅、改格式不會紅）。
7. `m5_acceptance_scenarios.py` 的 `MISMATCH` 依賴舊 skill 的字樣（「未經核對」），改成新 skill 會讓模型說出的字樣，或改用不依賴措辭的判斷。
8. 文件：brief §14 的 skills 清單、plan §6〈agent〉。

## 驗收

- [x] `berth/skills/` 只剩 `download`、`subscribe`、`recommend`；`download` ≤ 30 行、`recommend` ≤ 20 行
- [x] 系統指示包含 B1 的四條；skill 裡沒有那四條的重述，也沒有點名作品
- [x] `why_not.explain` 的說明寫出各結論的意思；`read_media` 在 `in_jellyfin` 佔滿一季時帶 `hint`（測試）
- [x] `test_skills.py` 的總行數閘門通過雙向變異驗證
- [x] 驗收腳本不再依賴舊 skill 的字樣
- [x] brief §14、plan §6 已改；全部檢查、pytest 綠；progress.md 已更新

## Comments

- 2026-11-07 協調者（使用者決定）：`contains` 是字串比對，`繁日` 也會命中「简繁日内封」的發佈。使用者接受這種「簡繁日」版本（含繁中，屬可接受的超集），因此 skill 照寫 `繁日`、不必強迫用 `繁日双语`；票 11 比對「13 集、同一字幕組」即可，不必逐列比語言欄位。
- 2026-11-07 實作：`hint` 的格式（也寫進 plan §6〈agent〉）——`media.read_media` 給模型的那一份多一格 `hint`（字串），只在有季的已播集全是 `in_jellyfin`（整季以上）時出現，句子列出那幾季（`S01, S02`）並帶按鈕名的兩種語言（"Rebuild the ledger from the library"（從媒體庫重建帳本））。
- 2026-11-07 實作：行數閘門算整份檔案的行數（與票、spec 的字面一致）；download 29、recommend 17、subscribe 34，合計 80 ≤ 80，票 09 改寫 subscribe 後有餘裕。`download` 與 `recommend` 的逐檔上限（30／20）另有斷言；變異實測：subscribe 多加一行 → 總量閘門紅，還原後綠。
- 2026-11-07 實作：`subscribe` 刪掉搜尋語言段、名字清單段、注入提醒段與卡片段（Route 段票 04 已無），並把表格說明改寫成散文，34 行；流程本身的改寫（`rss.subscribe`）留給票 09。刪掉的卡片句含「助理建議只當預選」的細節，屬 brief §14 的卡片政策、模型不必知道。`recommend` 宣告 `rss.list_subscriptions`，所以和 `subscribe` 一樣只給管理員。
- 2026-11-07 實作：`MISMATCH` 改成 `unchecked`——新 `download` skill 要模型在無法核對的季標這個字樣（英文固定 token），不再依賴舊 skill 的「未經核對」。
- 2026-11-07 實作：B3 由 `TestNoWorkIsNamed` 守，掃內文與描述；作品名單（`NAMED_WORKS`）是手寫的驗收情境那幾部，新增情境點名新作品時要跟著加。雙向變異：內文寫進 `Re:Zero` 會紅，只改 frontmatter 格式不紅。
- 2026-11-07 實作：`download` 第 3 步照舊 skill 保留無例外的標記規則（第 0 集、.5、總集篇、被移到特典、編號接續或跨季），免讓 S2-mushoku／S2-hxh 的範圍標記變差；第 1 步補上 `inventory_find_in_library` 的 `episodes`（票 06）。
- 2026-11-07 補：系統指示第 2 條加一句「先認出作品（discover／TMDB），使用者選定前不搜發行」——通用規則，避免只說「找」就被讀成要來源（S8）；brief §14 同步。
