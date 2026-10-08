# 57 — README 改成英文為主、中文另一份；安裝頁只留必讀

**Status:** ready-for-agent

**Blocked by:** 55（Unraid 一節照實跑結果寫）、56（安裝步驟的第一步是下載 zip）

**讀:** `docs/research/usability-audit-2026-10-07.md` §2 E7、§6.3、§7、§8 P1-8、P2-13、P2-16、§9 第 5 點；`notes/r2-docs-and-research.md` §1（全節）；票 55 的研究檔；brief §19「第四輪可用性審計的八項」E7；專案 `CLAUDE.md`〈指令〉

## 為什麼

- 使用者要公開發佈、寫進 CV：r/selfhosted、Unraid 論壇與看 CV 的人讀英文。
- 使用者拍板（2026-10-08）：**README 改成英文為主、中文另一份**。
- 審計 E7：安裝頁現在的必讀約 2,000 字、35 個名詞，四個對照產品都是「拿檔案 → 改 2–4 個值 → `up -d` → 連到下一頁」。

## 做什麼

1. **`README.md` 改寫成英文**，給第一次來的自架使用者，依序是：
   - 一句話介紹＋截圖 3–4 張：精靈、作品頁搜尋、媒體庫、健康頁。可從審計截圖挑，或重拍英文介面。
   - 前置需求：Docker Engine 或 Docker Desktop，加 Compose v2。
   - 先申請 TMDB key（約 5 分鐘）。
   - 下載 zip（56）→ 改 `.env` 的幾個值 → `docker compose up -d` → 開精靈。
     - 要改的值：`DATA_ROOT`、PUID / PGID、`TZ`；已經在跑 Jellyfin / qBittorrent / Prowlarr 的人先改 `COMPOSE_PROFILES` 或 port。
   - 精靈每頁一句話。
   - 一節「**Status & known limitations**」，照實寫：
     - 公開 beta；只支援 Jellyfin 12+ 與 Prowlarr；沒有通知。
     - 實測過 Windows Docker Desktop 與 Unraid，其他 Linux 發行版還沒實測。
     - 換服務、重裝後要手動處理的已知問題，連到 59–65 那幾件。
     - 不要直接開到公網。
   - 連結到各份 guide、CHANGELOG、授權與 TMDB 歸屬。
2. **`README.zh-Hant.md`**：同一份內容的繁中版；兩份開頭互相連結。
3. **長段落搬到 `docs/` 的使用者 guide**（英文）：
   - 精靈逐頁細節、接既有服務（含 Unraid 的「Add another Path」寫法）、前置與版本下限、硬鏈接前提、升級、疑難排解、秘密與備份。
   - 每份 guide 開頭一句話說這頁給誰看。
4. **開發者內容搬走**：開發指令、目錄結構、實驗腳本搬到 `CONTRIBUTING.md`（或 `docs/development.md`，擇一）。
   - **專案 `CLAUDE.md`〈指令〉「README 是指令的單一來源」要同一個 commit 改成新的位置**；全域規則要求改目錄結構時同輪更新 CLAUDE.md。
5. **同時修掉文件小錯**：
   - 「四個容器掛同一個媒體根」→ 三個；
   - 「Berth 不存密碼」→ 存加鹽雜湊；
   - 套件內媒體庫不即時監看：手動丟進去的檔案不會自動出現（P2-13）；
   - 「唯一要離開 Berth 的一步是 TMDB」限定成套件內＋公開站。
6. `.env.example` 的註解與 README 對齊：`DATA_ROOT` 試跑可以不改、正式用要改到哪裡；`TZ` 要改成自己的時區。

## 驗收

- [ ] `README.md`（英文）的安裝必讀部分（從開頭到「精靈每頁一句話」）不超過約 700 英文字；照它在乾淨目錄實跑一次到精靈頁 1，附指令輸出
- [ ] `README.zh-Hant.md` 與英文版段落一一對應，兩份互相連結
- [ ] 原 README 每一段都有去處（保留、搬走或刪除），在票的 Comments 列對照表
- [ ] 專案 `CLAUDE.md` 的指令來源、README 內部連結、`docs/` 裡指向 README 段落的連結全部更新（用腳本掃斷鏈，結果貼在 Comments）
- [ ] 全部檢查綠燈；progress.md 記一行
