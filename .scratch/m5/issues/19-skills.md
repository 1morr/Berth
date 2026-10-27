# 19 — skills

**Status:** ready-for-agent

**Blocked by:** 11

**讀:** plan §11.6〈分段〉第 7 段；`docs/research/m5-ai-direction-2026-10-27.md` C2〈claw 類專案能抄的〉的 skills 那一條；`scripts/experiments/m5_agent_chat.py` 的 `SKILLS` 與 `load_skill`；`docs/research/m5-prototype-2026-10-27.md` 的 S1 / S2 / S4 逐字稿（模型怎麼用 skill）

## 為什麼

情境的工作流程（系列整理、新番推薦、為什麼沒入庫、補缺集）寫在 system prompt 裡太長，而且每一輪都要付費。漸進揭露的做法是：system prompt 只放名稱與一句描述，需要時用唯讀工具載入全文。實測裡兩種接口都會主動載入。

## 做什麼

1. skills 是 repo 裡的 markdown 檔：開頭寫名稱與描述，內文是流程。只能是指令，不能變成執行入口。
2. 唯讀工具 `load_skill(name)`；instructions 列出名稱與描述。
3. 第一批：
   - `series-mapping`：含 Fribb offset 重疊的處理，見票 16 第 4 點。
   - `new-season-picks`：評分附人數，樣本少的要標。
   - `why-not-imported`：用票 10 的命令。
   - `missing-episodes`：情境 4。
4. 格式檢查：名稱唯一、描述不空，用測試守。

## 驗收

- [ ] skill 檔的格式有閘門（雙向變異驗證）
- [ ] `/skills` 列得出來；`load_skill` 回全文（測試）
- [ ] 全部檢查與 pytest 綠；progress.md 已更新

## Comments
