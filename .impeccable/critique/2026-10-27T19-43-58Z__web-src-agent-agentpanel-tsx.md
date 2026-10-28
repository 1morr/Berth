---
target_identity: "file:/Users/roxy/orca/workspaces/Berth/t22/web/src/agent/AgentPanel.tsx"
target_fingerprint: "sha256:928e932d7f81a12f0418b012cb13c764c55cacf15ce7a6fa506757107dd529d2"
target_path: /Users/roxy/orca/workspaces/Berth/t22/web/src/agent/AgentPanel.tsx
timestamp: 2026-10-27T19-43-58Z
slug: web-src-agent-agentpanel-tsx
---
Method: dual-agent (A: design review + audit, opus · B: detector + overlay, sonnet)

# M5 UI 收尾（票 22）：側面板、確認卡、AI 設定、用量頁、步驟頁、作品頁「為什麼」

| 面 | Nielsen | Audit |
| --- | --- | --- |
| 側面板 | 29/40 | 15/20 |
| 確認卡 | 27/40 | 15/20 |
| AI 設定 | 30/40 | 17/20 |
| 用量頁 | 31/40 | 18/20 |
| 步驟頁 | 26/36 | 16/20 |
| 作品頁「為什麼」 | 25/36 | 15/20 |

Detector：CLI 9 檔 0 條；overlay 1280 全部乾淨，390 只有三處中英混排的行尾孤字（AI 設定 1、用量頁 2）。

P1（這張票修）：
1. 助理散文裡的連結用 TEXT_LINK（.label inline-flex 11px），換行與散文重疊；自動連結把「，但」吃進網址（agent/Markdown.tsx）。
2. 被按的鍵消失後焦點掉回 body：送出→停止、繼續、確認卡確認/拒絕。
3. 「出自外部來源」用 text-blocked-ink 紅字（The One Meaning Rule）。
4. 送單卡沒重述會寫死的資料夾名（plan §5，票 13 留項）。
5. 390 寬季表被「為什麼」鍵撐寬（394/340），標題被裁。

P2/P3 見票 22 Comments。
