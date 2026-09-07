# 04 — 實驗：Jellyfin 命名實測、qBittorrent 版本相容、Prowlarr host API

**Status:** done

**Blocked by:** 03

**讀:** brief §20.6、§20.7、§7、§6.8；plan §5、§8.1、§9.2、§9.3、§11.1（T0.3）

## 做什麼

用 03 的 compose 環境跑完 brief §20.6 剩下的實驗，結論寫回 brief §20.6 / §20.7（附來源），並凍結 plan §5 的命名模板。腳本一律留在 `scripts/experiments/`，可重跑。

**與 brief 的偏差**：brief §17 把實驗排在 M0 最前面，本票改排在 compose 之後，理由是實驗需要真的 Jellyfin 與兩個版本的 qBittorrent，compose 已經提供。命名模組要到 M1 的解析器票才寫，模板在那之前凍結即可。開工時確認這條已在 `docs/progress.md` 的「偏差與決定」。

三組實驗：Jellyfin 命名（10.10 與 10.11 各一次，dummy 檔 + API 查驗）、qBittorrent 4.4 與 5.x 的參數矩陣、Prowlarr `config/host` 的欄位名與 Linux 宿主硬鏈接腳本。

## 驗收

- [x] `<Title> (<Year>) - S01E01 - <Episode Title> [BD][1080p][CHT+JP][Group].mkv` 被辨識為 S01E01，方括號與 `+` 不滲入劇名或集名
- [x] 同一集兩個版本放同一季資料夾：未裝插件的表現、裝 MergeVersions 後排程任務的名稱與 Id、合併結果、版本選單標籤都已記錄
- [x] 電影 ` - [BD][2160p][CHT+JP][Group]` 標籤被接受，版本排序已記錄
- [x] `Season 00` 與 `extras/`（劇集層與季層）的行為與 brief §20.1 相符，或差異已記錄
- [x] `….CHT.zh.ass` / `….CHS.zh.ass` 在字幕選單的顯示文字已記錄
- [x] `#!/details?id=` 深連結在該版本可用與否已記錄
- [x] qBittorrent 4.4 / 5.x：`paused` vs `stopped`、`contentLayout`、`torrents/files` 的 name 相對基準、`torrents/categories` 的 `savePath` / `save_path` 鍵名差異都有實測結果
- [x] `WebUI\ServerDomains=qbittorrent` 是否足以通過 Host 檢查已有結論；不足時記下改用 `HostHeaderValidation=false` 的決定並回寫 plan §9.2
- [x] Prowlarr `config/host` 設定 Forms 帳密的欄位名已確認
- [x] Linux 宿主 bind mount 的硬鏈接腳本可跑並通過
- [x] 結論寫回 brief §20.6 / §20.7，plan §5 的命名模板凍結，§8.1 / §9.2 依實測修正
- [x] 推翻 plan 或 brief 決定的部分在同一 commit 改文件，並在 progress.md 記一行

## Comments

完整結果：`docs/research/m0-experiments.md`。腳本：`scripts/experiments/`（含自己的 README，
說明如何重跑；`jellyfin_naming.py` 要從乾淨的 `/config` 跑，Jellyfin 的 DB 會留住舊掃描結果）。

**與票的偏差**

- 票寫「用 03 的 compose 環境」，實際另起了 `scripts/experiments/compose.yml`。理由是
  `deploy/` 只有單一版本的 Jellyfin 與 qBittorrent，而本票的核心就是「兩個版本各跑一次」；
  另外實驗會把 qBittorrent 的偏好改壞、把 Jellyfin 的 `/config` 砍掉重來，不該碰使用者
  照著 README 起的那一套。port 與子網都與 `deploy/` 錯開，兩套可以同時跑。

**驗收的兩點說明**

- 「Linux 宿主 bind mount」用的是 Docker Desktop 自己的 Linux VM（`docker-desktop` 發行版）上的
  ext4 路徑 —— daemon 端的檔案系統，`link()` 與原生 Linux 宿主同一條路徑，但**不是另一台實體
  Linux**。原生 Linux 宿主與 NAS 都仍未測，brief §20.6 兩條都保留；`hardlink.sh` 沒有相依，
  ssh 進去就能跑。
- `WebUI\ServerDomains=qbittorrent` **足以**通過 Host 檢查，所以沒有走「改用
  `HostHeaderValidation=false`」那條分支。真正的發現是 Host 檢查**還會比對 port**，
  已回寫 plan §9.2 與 README 的部署疑難排解。

**票沒要求但量到、且已回寫文件的**

- `POST /Startup/User` 前必須先 `GET /Startup/User`，否則 500（plan §9.4）。
- `POST /Library/VirtualFolders` 的 body 要包成 `{"LibraryOptions": {...}}`，否則整份選項被靜默
  丟掉（plan §9.4）。
- 10.11 第一次掃描後 `parentId=<seriesId>` 與 `/Shows/{id}/Episodes` 都回 0，`find_episodes`
  改用媒體庫 recursive + `Path` 前綴（plan §8.2、brief §20.1）。
- 劇集經 MergeVersions 合併後的版本標籤是**整個檔名主幹**而非 tags（brief §7.7）。
- 電影檔名少了 `[tmdbid-<id>]` 會變成兩部獨立的片，brief §7.2 的舊範例是錯的（已更正）。
- `zh-Hant` / `zh-Hans` 只有 10.11 認得（brief §20.1）。

**沒測到、已標回文件的**

- **版本標籤含中文**：實驗用的 tag 全是 ASCII，但 brief §6.8 的 group token 保留字幕組原文，
  中文組名沒被覆蓋到。brief §20.1「多版本」那一條保留「未證實」。
- 「預置 `WebUI\ServerDomains` ini 鍵再啟動」沒另外測；實驗改的是對應的 runtime 偏好
  `web_ui_domain_list`。結論是不預置，所以不需要。

**留給後續里程碑**

- benchmark v0 的 20 筆 torrent fixture → M1 解析器票。
- Mikan / Nyaa 的 RSS fixture → M3 RSS 票。
- 絕對編號換算失敗率 → M1 解析器票。
