# 03b — brief §20 壓縮（下）：§20.8–§20.24

**Status:** ready-for-agent

**Blocked by:** 03a

**讀:** `.scratch/docs-diet/spec.md`；票 03a 的做法與 Comments；brief §20.8–§20.24（約 450 行 100 KB，交給子代理逐節處理）；各節提到的 `docs/research/` 檔

## 為什麼

同 03a。這一半有 9 節沒有研究檔：§20.10、§20.11、§20.15–§20.21。

## 做什麼

照 03a 的第 1–5 步做，差別：

- 沒有研究檔的 9 節裡，主題相近的可以併成一個研究檔（例：§20.16、§20.19、§20.20、§20.21 都是搜尋），併法寫在 Comments。brief 的小節號照舊各自保留。
- §20.9 排在 §20.10 後面，順序可以理正，號碼不改。

## 驗收

- [ ] `scripts/docs_moved_lines.py` 對 `docs/design-brief.md` → `docs/research/*.md` 跑出「遺失 0」，輸出貼 Comments
- [ ] §20.8–§20.24 每節前後行數表、§20 全章前後行數貼 Comments
- [ ] 引用點清單與檢查結果貼 Comments（`grep -n '§20\.\(8\|9\|1[0-9]\|2[0-4]\)\b'`）
- [ ] brief 到 research 的連結都指得到檔與錨點（跑一次檢查，貼輸出）
- [ ] 全部檢查與 test 綠；progress.md 記一列 session；commit；不 push

## Comments
