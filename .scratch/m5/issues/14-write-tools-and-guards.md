# 14 — 寫入工具與守法

**Status:** ready-for-agent

**Blocked by:** 13

**讀:** plan §11.6〈已定〉、〈分段〉第 5 段；brief §14、§20.24；`docs/research/m5-ai-direction-2026-10-27.md` A3 的 R5、C4 第 3–5 點、C6 情境 4；`docs/research/m5-prototype-2026-10-27.md`〈實跑才抓到的問題〉第 6 點、S5 / S6 逐字稿；`scripts/experiments/m5_agent_chat.py` 的 `harvest`、`_unseen`、`add_rss_feed`

## 為什麼

情境 1、2、4 需要訂閱、加 Feed、缺集搜尋。M5 的注入防線主要靠能力邊界：id 只能出自工具結果，網址只能出自使用者的話，送出 torrent 有數量閘。

## 做什麼

1. **工具**：
   - 讀取：索引站搜尋（帶季號時記得 `missing`）、缺集搜尋、Mikan 番組搜尋與字幕組清單。
   - 寫入：Mikan 訂閱、關鍵字訂閱、加 Feed、Route 清單。
   - 全部經登錄表與執行器。
2. **守法**（通用，不寫在個別工具裡）：
   - **id 必須出自這段對話已存的工具結果**：media、source、route、bangumi、subgroup。不是的回理由給模型，不出卡。
   - **網址必須逐字出自使用者的話**：`CONNECTS_OUT` 的參數。
   - 「讀過外部內容」的警示**只標在自由文字參數出自外部內容的卡**（實測：全部都標，警示就沒有意義）。
3. **送單的數量與磁碟閘**（R5）：一張卡最多 N 個 torrent，扣在途量，超過的拆成下一張。N 寫成設定預設值，理由記在 plan。
4. **一般使用者**只能送自己的單、只能讀；訂閱與加 Feed 是 admin。

## 驗收

- [ ] 每個守法各有被擋與放行的測試（假模型）
- [ ] 實測抓到的兩個預覽理由（`route_required`、`route_kind_mismatch`）在卡片出現之前就被擋下（測試）
- [ ] 數量閘拆卡（測試）
- [ ] `agent` 情境走一次「加這個 RSS：<網址>」與「上網找網址直接加」，前者出卡、後者被擋（playwright 實跑）
- [ ] 全部檢查、pytest、vitest 綠；progress.md 已更新

## Comments
