# 10 — qbit_poller、SSE 與 Job 詳情時間線

**Status:** ready-for-agent

**Blocked by:** 09

**讀:** plan §3.1、§3.2（qbit_poller）、§6（events 群組）、§8.1、§11.2（T1.4）；
brief §5.1、§5.2、§20.2

## 做什麼

送單之後不用重整就看得到狀態與進度一路走到 `completed`；Job 詳情頁有時間線（brief §5.2 的事件）；
重啟 Berth 不丟狀態。

`qbit_poller` 用 `sync/maindata` 帶 rid 做增量，只看本系統 category 的 torrent，驅動 plan §3.1 中
由客戶端狀態觸發的每一個轉換。轉換一律 compare-and-set，每個 job 另有程序內的 `asyncio.Lock`。

順便解掉 plan T1.9 的第四條：**qBittorrent 的 403 要分得出「帳密不對」與「IP 被封」**——4.4.x
連續登入失敗會封 IP 且同樣回 403，現在被顯示成「帳密不對」（plan §8.1）。

`issues` 表在 M2 才建，所以本票的「無主 torrent」先寫 event；這是相對 plan §3.2 字面的偏差，
要記在 `docs/progress.md`。

## 驗收

- [ ] `qbit_poller` 由 lifespan 啟動、關閉時 cancel 並 await，不留 pending task
- [ ] 間隔：有活躍 job 5s、否則 30s、連續失敗退避到 5 分鐘
- [ ] plan §3.1 中由客戶端狀態觸發的轉換全部實作：`metadata_ready`、`downloading`、`stalled`、
      `missing_files`、`client_error`、`client_removed`、`completed`
- [ ] 轉換一律 compare-and-set（影響 0 列即放棄），有並發測試
- [ ] `metadata_ready` 時建立 `job_files`（`torrents/files[].name` 相對 `save_path`，先正規化尾斜線）
- [ ] 完成判定依 brief §20.2，4.4 與 5.x 兩個版本各有契約測試
- [ ] 進度事件每跨 25% 一筆，不刷屏
- [ ] `GET /api/events/stream`（SSE）推送 job 狀態與進度；前端據此讓相關 query 失效
- [ ] 送單到完成的狀態在 UI 即時更新、不用重整（playwright 實跑並附結果）
- [ ] 重啟 Berth 之後狀態不丟：由 DB 與下一輪 maindata 補上（實跑驗證）
- [ ] 無主 torrent 記一筆 event 並在 Job 列表或健康頁看得見（`issues` 表留 M2，偏差記進 progress.md）
- [ ] qBittorrent 的 403 分得出「帳密不對」與「IP 被封」，兩種都有測試與可行動的訊息
- [ ] Job 詳情頁的時間線顯示 brief §5.2 的事件，走 `/impeccable shape`
- [ ] 對比 ≥ 4.5:1；390px 窄版可用；zh-Hant 與 en 並列
- [ ] lint / type / test 全綠並貼指令輸出
