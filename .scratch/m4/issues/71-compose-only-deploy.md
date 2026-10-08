# 71 — 只用 compose 檔加 `.env` 就能部署，發 0.2.1

**Status:** ready-for-agent

**Blocked by:** 70（內嵌 preseed 的寫法與結論）；排在 42 之後做（同一批 guide 與 brief §20.14，避免兩個 session 同時改）

**讀:** 票 70 的結論與 brief 裡它新增的那一節；brief §19 E4、§20.17；票 56、57、58 的 Comments；README、README.zh-Hant、`docs/guide/` 的安裝、Unraid、升級三段；`docs/development.md` 的發版段

## 為什麼

- 使用者拍板（2026-10-09）：**部署只要 compose 檔加 `.env`**，貼進 Unraid Compose Manager 或任何資料夾就能 `up`。不下載 zip、不 clone、不放額外檔案。
- 這推翻 E4（票 56 的 release 附件 zip）。
- Release 頁**保留，只放那一版的說明**（CHANGELOG 段落），**不附任何檔案**。版本化的 image 照舊在推 `v*` tag 時發到 GHCR。

## 做什麼

1. **部署檔**：
   - compose 照票 70 定案的寫法內嵌 qBittorrent preseed；
   - 刪掉 preseed 目錄與它的掛載；
   - `.env.example` 的註解寫明：`DATA_ROOT`、`CONFIG_ROOT` 在 Unraid / Compose Manager 一定要用絕對路徑，否則會寫到隨身碟。
2. **拿掉 zip**（照全域規則直接刪舊路徑，不留相容層）：
   - 打包腳本、它的測試、pytest 為它加的 import 路徑；
   - release workflow 建 zip 與上傳附件的步驟；Release 頁照常建、內容是說明；
   - 實驗腳本裡引用 preseed 路徑的地方。
3. **閘門**：
   - 新測試：部署用 compose 的每個 host 掛載來源都是 `${變數}` 開頭或絕對路徑，不准相對路徑；
   - 雙向變異：加一條 `./x:/y` 會紅，改無關的註解或服務名不紅；
   - 現有的 preseed 腳本測試改成從 compose 檔抽出內嵌的腳本（還原 `$$`）再跑，原本守的行為一條不少。
4. **介面文案**：zh-Hant 與 en 提到 preseed 目錄或 zip 的補救說明改寫，例如套件內 qBittorrent 進不去時，請使用者確認 compose 是完整複製的。
5. **文件**（README 與 README.zh-Hant 同輪改，`test_readme_docs` 守兩份一致）：
   - 安裝改成：取得 compose 與 `.env.example` → 改幾個值 → `up -d`。
     - 連結指向**這次發版的 tag** 底下的原始檔（例如 `raw.githubusercontent.com/1morr/Berth/v0.2.1/deploy/...`），不指 `main`，免得 compose 比 image 新。
     - 下一次發版要更新這個連結：寫進 `docs/development.md` 的發版步驟。
   - Compose 最低版本寫 2.23.1。
   - `docs/guide/requirements.md`〈Unraid〉改寫成 Compose Manager 的做法：Add New Stack → 貼 compose → 貼 `.env` 改值 → Compose Up。不再提 Indirect Path 與 berth-deploy 目錄。
   - `upgrading.md`：從 0.2.0 升上來，之前下載過 zip 的人怎麼換（換 compose 檔即可，preseed 目錄可刪）。
6. **紀錄**：
   - brief §19 E4 那列記「2026-10-09 使用者推翻：只用 compose＋.env」；
   - §20.17 標成被取代，指到 70 的那一節；
   - plan §9.1、CHANGELOG `[Unreleased]` → `[0.2.1]`，從 0.2.0 升級要注意的寫清楚；
   - progress.md 偏差與決定。
7. **實跑**：在 repo 外的乾淨目錄，只放 compose 與 `.env` 兩個檔，照新 README 走到頁 2 套件內 qBittorrent 綠。
   - 本機一次；42 那台 VM（rootless）一次。
   - 本機用 `berth-t71` 專案名與另一組 port。
8. **發 0.2.1**（使用者已授權推 tag、建 Release、push main）：
   - pyproject 版號；
   - 推 `v0.2.1`，Release run 綠；
   - Release 頁沒有附件、有說明；
   - 匿名查 GHCR：`latest` 與 `0.2.1` 是同一個 digest。
   - 發版後照 README 上的連結，在乾淨環境從頭走到入庫一部公有領域電影：TMDB key 照審計做法，不出現在任何輸出。
9. **不碰 Unraid**：使用者要自己在 Unraid 上照新 README 部署。

## 驗收

- [ ] 部署檔裡沒有相對路徑掛載、沒有 preseed 目錄；新閘門雙向驗證寫在測試檔內
- [ ] preseed 行為測試改成讀 compose 內嵌的腳本，原有斷言都在且綠
- [ ] zip 打包、它的測試與 release workflow 的附件步驟都刪掉；Release 頁照常建、無附件
- [ ] README、README.zh-Hant、guide、development.md（發版步驟含更新 compose 連結）、`.env.example` 已改；全 repo 掃斷鏈 0
- [ ] 乾淨目錄只放 compose＋`.env`：本機與 VM 各一次到頁 2 綠，附指令輸出
- [ ] `v0.2.1` 已發：Release run 綠、無附件、GHCR `latest` = `0.2.1` digest；照 README 從乾淨環境入庫一部，附截圖
- [ ] brief E4 推翻紀錄、§20.17 標取代、plan §9.1、CHANGELOG `[0.2.1]`、progress.md 已更新
- [ ] 全部檢查、pytest、vitest、前端 e2e 綠燈
