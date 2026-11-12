# 09 — AI 任務：待綁定 RSS Series，加送下載的閘

**Status:** ready-for-agent

**Blocked by:** 06

**讀:** spec〈AI 任務與 `ai_worker`〉送下載的閘、〈第一批任務型別〉、〈AI 評估〉、〈共同規則〉；brief §15〈綁定〉〈補舊集與第一輪〉、§14；plan §8.5〈自動綁定〉〈RSS Series 的鍵〉；C1 表「待綁定 RSS Series」那一列、C3 表「送單的數量與磁碟閘」；`AiSettings.card_downloads`；第 05、06 張的 Comments

## 為什麼

待綁定的 RSS Series 等人猜是哪部作品。綁定會補舊集送單，送出的 torrent 收不回，所以這張同時做背景任務的送下載閘，評估件數也照高風險的 60 件。

## 做什麼

1. 決定的形狀：猜作品（候選由程式先用 TMDB、Bangumi、Mikan 查好）、選 Route 後綁定，或交給人。Route 沒有預設、不只一條可選時做成 Proposal。驗證：名字、開播日、唯一性。
2. **送下載的閘**（放在地基的套用路徑上，所有帶 `Flag.DOWNLOADS` 的命令都適用，不只這一型）：這一次會送出的 torrent 超過 `AiSettings.card_downloads`（13），或送完剩餘磁碟會低於最低剩餘磁碟設定，就不送，改成 Proposal，附原因。
3. 案例集：從真實的待綁定清單取樣，至少 60 件，連同標準答案凍進 repo（取樣方法與去識別化寫進 Comments）。
4. 跑評估（兩種接口），達標才在設定頁放開關。
5. 文件：brief §14、plan §3.2 或 §4.5（閘寫在哪照第 05 張的結構）、`CONTEXT.md`。

## 驗收

- [ ] 背景 AI 綁錯一個 Series 時送出的 torrent 不超過 13 個，多的停在 Proposal（整合測試）
- [ ] 磁碟不夠時不送、改 Proposal（整合測試）
- [ ] Route 不只一條時停在 Proposal（整合測試）
- [ ] 真模型評估 ≥ 60 件：套用的錯 0 件、交回人的比例 ≤ 5%，數字在 Comments 與研究紀錄
- [ ] AI 關著或開關在人時行為不變（整合測試）；設定頁有開關
- [ ] 全部檢查、pytest、vitest 綠

## Comments
