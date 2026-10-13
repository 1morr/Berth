# 93 — 簡化：清掉沒人用的東西，knip 加進 pre-commit

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** `docs/research/simplification-audit-2026-10-13.md` 的 S20–S24、〈閘門建議〉的 knip 一節、附錄 A；`docs/development.md`〈全部檢查〉；全域規則「規則要有閘門」（新閘門要在測試檔內做雙向變異驗證）

## 為什麼

票 86 審計找到一批確定沒人用的東西。knip 在前端的誤報率是 13%，而且兩行設定就能全部排除，值得當成閘門，以後就不用再靠人審。前提是先把它現在抓到的清掉，否則閘門一開就是紅的。vulture 誤報 75%～91%，不加。使用者（2026-10-13）照協調者建議要做。

## 做什麼

1. **S20**：刪前端沒讀的 `SetupStatusOut.completed`、`RouteSetupOut.completed` 與 services 端的來源。資料庫的 `SetupSettings.completed` 不動。
2. **S21**：刪 knip 抓到的 12 項；另外 23 項同檔有用的拿掉 `export`。不設 `ignoreExportsUsedInFile`，讓 export 面保持最小。
3. **S22**：刪 `Config.data_root` 與 Dockerfile 的那行 ENV。compose 的 `${DATA_ROOT}` 掛載與 `.env.example` 照留；`development.md`、`plan.md` 改成明講 `DATA_ROOT` 只給 compose 掛載用。
4. **S23**：刪 `IndexerResult.leechers`、`FakeIndexerSearch.closed`。
5. **S24**：刪 `Waiter`；pipeline 四份 `Sleeper` / `Clock` 別名收到 `pipeline/ticks.py`。
6. **knip 閘門**：
   - `web/package.json` 加 knip devDependency，鎖當前 stable。
   - `web/knip.json` 加 `ignoreBinaries: ["uv"]`，以及 `schema.d.ts` 的 `exports`、`types` 排除。
   - pre-commit 加一條 `pnpm -C web exec knip`，`files: ^web/`。
   - `docs/development.md`〈全部檢查〉寫進去。

## 驗收

- [ ] `pnpm -C web exec knip` 在現在的樹上 0 條
- [ ] 閘門的雙向驗證寫成測試（例如在暫存目錄造一個沒人用的 export，斷言 knip 報它；改一次無關的命名，斷言它不報），不只是手動驗證
- [ ] S20、S22 的變動 CHANGELOG 有記（S22 是設定項的變動，行為不變）；`gen:api` 重跑
- [ ] 全部檢查（含新的 knip）、pytest、vitest 綠；progress.md 已更新
