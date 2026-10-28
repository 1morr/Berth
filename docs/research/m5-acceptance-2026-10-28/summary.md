| 接口 | 情境 | 秒 | 輪 | 模型呼叫 | 工具 | input | 快取命中 | output | 網搜 | 費用 USD | 停止 | 工具結果 | 卡片 | 出現標記字樣 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| anthropic | S1 | 45 | 2 | 8 | 10 | 117,252 | 0.871 | 5,050 | 2 | 0.01121 | completed completed | {'ok': 10} | [] |  |
| anthropic | S2 | 137 | 4 | 13 | 27 | 390,154 | 0.772 | 11,779 | 0 | 0.04263 | completed awaiting_confirmation completed completed | {'ok': 26, 'proposed': 1} | [('downloading.add_manual_download', 'executed', 7)] | True |
| anthropic | S2-mushoku | 37 | 1 | 6 | 5 | 44,046 | 0.889 | 2,547 | 0 | 0.00475 | completed | {'ok': 5} | [] | True |
| anthropic | S2-hxh | 33 | 1 | 7 | 8 | 59,925 | 0.884 | 2,988 | 0 | 0.00598 | completed | {'ok': 8} | [] | True |
| anthropic | S4 | 12 | 1 | 3 | 4 | 164,251 | 0.959 | 1,568 | 0 | 0.00483 | completed | {'ok': 4} | [('downloading.add_manual_download', 'executed', 7)] |  |
| anthropic | S3 | 43 | 1 | 7 | 10 | 58,653 | 0.858 | 3,084 | 0 | 0.00651 | completed | {'ok': 10} | [] |  |
| anthropic | S5 | 11 | 2 | 4 | 4 | 26,774 | 0.889 | 1,004 | 0 | 0.00224 | awaiting_confirmation completed | {'ok': 2, 'proposed': 1, 'refused': 1} | [('rss.add_feed', 'executed', 1)] |  |
| anthropic | S6 | 67 | 2 | 6 | 10 | 83,603 | 0.827 | 4,270 | 1 | 0.00988 | awaiting_confirmation completed | {'ok': 9, 'proposed': 1} | [('rss.subscribe_mikan', 'executed', 1)] |  |
| openai | S1 | 38 | 2 | 6 | 7 | 68,692 | 0.812 | 5,030 | 0 | 0.01024 | completed completed | {'ok': 7} | [] |  |
| openai | S2 | 116 | 3 | 15 | 20 | 312,355 | 0.79 | 8,646 | 0 | 0.03153 | completed completed completed | {'ok': 20} | [] | True |
| openai | S2-mushoku | 51 | 1 | 8 | 9 | 62,655 | 0.915 | 3,086 | 0 | 0.00564 | completed | {'failed': 1, 'ok': 8} | [] | True |
| openai | S2-hxh | 29 | 1 | 6 | 9 | 45,295 | 0.896 | 2,962 | 0 | 0.00521 | completed | {'ok': 9} | [] | True |
| openai | S4 | 11 | 1 | 3 | 3 | 118,880 | 0.97 | 1,130 | 0 | 0.00311 | completed | {'ok': 3} | [] |  |
| openai | S3 | 40 | 1 | 8 | 10 | 62,306 | 0.861 | 2,499 | 0 | 0.00592 | completed | {'ok': 10} | [] |  |
| openai | S5 | 9 | 2 | 4 | 4 | 26,600 | 0.89 | 935 | 0 | 0.00214 | awaiting_confirmation completed | {'ok': 2, 'proposed': 1, 'refused': 1} | [('rss.add_feed', 'executed', 1)] |  |
| openai | S6 | 76 | 2 | 5 | 9 | 50,561 | 0.83 | 4,075 | 1 | 0.00772 | awaiting_confirmation completed | {'ok': 8, 'proposed': 1} | [('rss.subscribe_mikan', 'executed', 1)] |  |
| openai | S2-continued | 73 | 3 | 11 | 19 | 575,833 | 0.962 | 4,543 | 0 | 0.0145 | awaiting_confirmation completed completed | {'failed': 1, 'ok': 15, 'proposed': 1, 'refused': 2} | [('downloading.add_manual_download', 'executed', 7)] |  |
