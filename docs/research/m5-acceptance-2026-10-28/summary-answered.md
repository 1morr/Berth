| 接口 | 情境 | 秒 | 輪 | 模型呼叫 | 工具 | input | 快取命中 | output | 網搜 | 費用 USD | 停止 | 工具結果 | 卡片 | 出現標記字樣 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| anthropic | S1 | 165 | 4 | 12 | 15 | 233,312 | 0.932 | 11,066 | 2 | 0.00969 | completed completed awaiting_confirmation completed | {'ok': 14, 'proposed': 1} | [('rss.subscribe_mikan', 'executed', 1)] |  |
| anthropic | S3 | 117 | 3 | 10 | 14 | 123,453 | 0.904 | 6,507 | 0 | 0.00601 | awaiting_confirmation completed completed | {'failed': 1, 'ok': 11, 'proposed': 1, 'refused': 1} | [('downloading.add_manual_download', 'executed', 1)] |  |
| openai | S1 | 90 | 4 | 11 | 12 | 192,491 | 0.917 | 8,984 | 1 | 0.00832 | completed completed awaiting_confirmation completed | {'ok': 11, 'proposed': 1} | [('rss.subscribe_mikan', 'executed', 1)] |  |
| openai | S3 | 59 | 3 | 10 | 13 | 129,485 | 0.894 | 5,757 | 0 | 0.00587 | completed awaiting_confirmation completed | {'ok': 12, 'proposed': 1} | [('downloading.add_manual_download', 'executed', 1)] |  |
