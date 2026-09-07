# 04 — 實驗：Jellyfin 命名實測、qBittorrent 版本相容、Prowlarr host API

**Status:** ready-for-agent

**Blocked by:** 03

**讀:** brief §20.6、§20.7、§7、§6.8；plan §5、§8.1、§9.2、§9.3、§11.1（T0.3）

## 做什麼

用 03 的 compose 環境跑完 brief §20.6 剩下的實驗，結論寫回 brief §20.6 / §20.7（附來源），並凍結 plan §5 的命名模板。腳本一律留在 `scripts/experiments/`，可重跑。

**與 brief 的偏差**：brief §17 把實驗排在 M0 最前面，本票改排在 compose 之後，理由是實驗需要真的 Jellyfin 與兩個版本的 qBittorrent，compose 已經提供。命名模組要到 M1 的解析器票才寫，模板在那之前凍結即可。開工時確認這條已在 `docs/progress.md` 的「偏差與決定」。

三組實驗：Jellyfin 命名（10.10 與 10.11 各一次，dummy 檔 + API 查驗）、qBittorrent 4.4 與 5.x 的參數矩陣、Prowlarr `config/host` 的欄位名與 Linux 宿主硬鏈接腳本。

## 驗收

- [ ] `<Title> (<Year>) - S01E01 - <Episode Title> [BD][1080p][CHT+JP][Group].mkv` 被辨識為 S01E01，方括號與 `+` 不滲入劇名或集名
- [ ] 同一集兩個版本放同一季資料夾：未裝插件的表現、裝 MergeVersions 後排程任務的名稱與 Id、合併結果、版本選單標籤都已記錄
- [ ] 電影 ` - [BD][2160p][CHT+JP][Group]` 標籤被接受，版本排序已記錄
- [ ] `Season 00` 與 `extras/`（劇集層與季層）的行為與 brief §20.1 相符，或差異已記錄
- [ ] `….CHT.zh.ass` / `….CHS.zh.ass` 在字幕選單的顯示文字已記錄
- [ ] `#!/details?id=` 深連結在該版本可用與否已記錄
- [ ] qBittorrent 4.4 / 5.x：`paused` vs `stopped`、`contentLayout`、`torrents/files` 的 name 相對基準、`torrents/categories` 的 `savePath` / `save_path` 鍵名差異都有實測結果
- [ ] `WebUI\ServerDomains=qbittorrent` 是否足以通過 Host 檢查已有結論；不足時記下改用 `HostHeaderValidation=false` 的決定並回寫 plan §9.2
- [ ] Prowlarr `config/host` 設定 Forms 帳密的欄位名已確認
- [ ] Linux 宿主 bind mount 的硬鏈接腳本可跑並通過
- [ ] 結論寫回 brief §20.6 / §20.7，plan §5 的命名模板凍結，§8.1 / §9.2 依實測修正
- [ ] 推翻 plan 或 brief 決定的部分在同一 commit 改文件，並在 progress.md 記一行

## Comments
