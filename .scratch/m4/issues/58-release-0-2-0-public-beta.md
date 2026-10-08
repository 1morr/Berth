# 58 — 發 0.2.0：第一個公開 beta

**Status:** ready-for-agent

**Blocked by:** 55（Unraid 實跑的結論寫進 CHANGELOG 的「測過的平台」）、56（release 附件）、57（新 README）

**讀:** `docs/research/usability-audit-2026-10-07.md` §2 E5、§6.3；README（新的英文版）〈Versions & upgrading〉；票 41（上一次發版的流程與 Comments）

## 為什麼

- GHCR 的 `:latest` 還是 0.1.0，不含票 43–54；照 README 部署會看到舊精靈（審計 P1-1、E5）。
- 使用者要今天公開、寫進 CV：發版之後，「下載 zip → `up -d`」才是一般人實際拿得到的東西。

## 做什麼

1. CHANGELOG `[Unreleased]` 收成 `[0.2.0]`。
   - 開頭寫：「公開 beta」、測過的平台（Windows Docker Desktop、Unraid 7.1）、已知限制（連到 README）。
   - 從 0.1.0 升級要注意的破壞性變更，照票 41 的寫法。
2. **打 `v0.2.0` tag 並 push 之前，先問使用者**（對外動作）。
3. 發版之後驗證：
   - GHCR 的 `latest` 與 `0.2.0` 是同一個 digest；release 頁有 zip 附件。
   - 在一個乾淨目錄，用 README 上的「最新版」連結下載 zip，照英文 README 走到 S1 入庫一部公有領域電影。
4. 在 GitHub repo 設定 description、topics（self-hosted、jellyfin、qbittorrent、prowlarr、media-automation 之類）與網站連結。**改 repo 設定前先問使用者。**

## 驗收

- [ ] 使用者同意後 push `v0.2.0`；Release run 綠燈；匿名 `tags/list` 與 digest 比對結果貼在 Comments
- [ ] 乾淨環境照英文 README 從 zip 走到入庫一部，附截圖
- [ ] progress.md 的 M4 列與 session 紀錄記一行
