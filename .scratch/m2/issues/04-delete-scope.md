# 04 — 刪除範圍 + `delete_job` + 方法層級門禁

**Status:** ready-for-agent

**Blocked by:** 無 —— 可立即開工

**讀:** plan §6（jobs 群組、門禁開頭那三段）、§7（`/jobs/:hash` 那一條）、§3.1（Job 狀態轉換）、§11.3 的決定 4 與 7；brief §9.2、§11

## 做什麼

M2 的第一個原語。票 06 的 audit 撤銷、票 08 的 rematch、票 05 的 `library_link_missing`
「連 complete 一起刪」、票 12 的 Job 詳情頁動作區，全部走它。

**命令與端點**：`DELETE /jobs/{hash}?unlink=&remove_torrent=&delete_files=&purge=`，四個旗標
（brief §9.2）：移除 library 硬鏈接 / 從 qBittorrent 移除 torrent（不刪檔）/ 刪除 complete 檔案 /
清除帳本與 Job 紀錄。`delete_files` 要求先 `remove_torrent`，否則拒絕。Job 進 `removed`，
寫 event `deleted` 並說得出刪了哪幾樣。

**四個旗標預設全不勾**（2026-09-22 定，brief §9.2）。Sonarr 的對話框預設勾「同時刪除檔案」，
但這裡的刪除以 Job 為單位而不是作品，預設刪檔會誤刪還在做種的東西。

**空間估算同步 `stat`**：逐一 `stat` 每一個來源與目標（慢而準，畫面上說「正在算」），不用來源
大小去猜。只有來源與所有鏈接都刪掉時才是真的釋放，畫面要說清楚這件事。

**對話框是一個元件**，這一輪掛在 `/jobs` 的展開區與 Media 詳情的版本清單；票 12 的 `/jobs/:hash`
掛的是同一個元件（plan §7 說它住在 Job 詳情頁與版本清單，而詳情頁還沒有）。

**門禁要多一個維度**。`api/gate.py` 的 `ADMIN_PREFIXES` 只比路徑前綴，而 `/jobs` 整組不能是
admin——`user` 要送得了單、看得到自己的 job。`DELETE /jobs/{hash}` 是 M2 第一個「同一條路徑、
不同方法、不同門禁」的端點（票 10 的 `POST /jobs/{hash}/reimport` 是第二個），所以在這一票把
規則擴成認得方法。形狀仍然是**預設拒絕**：規則在門禁一處，不散到 router 的相依裡。

## 驗收

- [ ] 四個旗標預設全不勾；`delete_files` 沒帶 `remove_torrent` 時是拒絕（有測試，不是靠 UI 擋）
- [ ] 四個旗標的每一種組合各自只做它該做的事：整合測試至少涵蓋「只移除鏈接」「移除 torrent 不刪檔」
      「刪檔（含 torrent）」「全勾」四條
- [ ] 空間估算逐一 `stat`；估算進行中畫面說得出「正在算」；只有來源與所有鏈接都刪時才報成真的釋放
- [ ] 刪完 Job 是 `removed`，時間線有 `deleted` 且說得出刪了哪幾樣
- [ ] `user` 登入時 `DELETE /jobs/{hash}` 回 403，而 `GET /jobs`、`POST /jobs`、`GET /jobs/{hash}/events`
      照常（整合測試對兩邊都斷言；把方法規則改回純前綴會讓它紅）
- [ ] 前端以 `user` 登入時看不到刪除入口（前端隱藏不是安全機制，後端那條是上一項）
- [ ] playwright 實跑一次刪除對話框（含估算中的畫面），附截圖或文字結果
- [ ] lint、type、test 綠燈

## Comments
