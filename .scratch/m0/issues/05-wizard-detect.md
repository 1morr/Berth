# 05 — 精靈骨架、建立管理員與服務偵測（第 1–2 步）

**Status:** ready-for-agent

**Blocked by:** 03

**讀:** plan §9.3（第 1–2 步）、§6（setup 群組）、§7、§11.1（T0.6）；brief §16.3

## 做什麼

這是第一張 UI 票：開頭先跑 `/impeccable hooks on` 與 `/impeccable init`，新頁面先 `shape` 再實作。

乾淨環境開瀏覽器落在 `/setup`，走完精靈前兩步：建立 Berth 管理員（帳號、密碼，勾選「同一組帳密也套用到 qBittorrent 與 Prowlarr 介面」，預設勾），然後 Berth 逐一探測三個 compose 主機名，在畫面上逐服務顯示判定結果是「套件內」還是「既有」。setup 未完成時 `setup/*` 匿名開放、其他頁一律導向精靈。

**與 plan 的偏差**：plan §11.1 把 adapters（T0.4）與精靈（T0.6）分成兩個任務，本里程碑改成按精靈步驟垂直切票，每張票帶進自己需要的 adapter 能力、Fake 與契約測試。開工時確認這條已在 `docs/progress.md` 的「偏差與決定」。

## 驗收

- [ ] `GET /api/setup/status` 回目前步驟與各服務判定；setup 完成後 `setup/*` 需登入
- [ ] `POST /api/setup/admin` 存下管理員帳號與密碼雜湊，以及「套用到其他服務」的勾選
- [ ] `POST /api/setup/detect` 逐一探測 `jellyfin:8096` 的 `/System/Info/Public`、`qbittorrent:8080` 的 `/api/v2/app/version`（免密）、`prowlarr:9696` 的 `/ping`，並從唯讀掛載的 `/ext/prowlarr/config.xml` 讀 API key
- [ ] 判定規則正確：Jellyfin `StartupWizardCompleted=false`、qBittorrent 免密可進、Prowlarr 讀得到 key 且無索引站 → 套件內；否則既有並顯示連線表單
- [ ] 服務未就緒時輪詢至多 2 分鐘，UI 顯示等待狀態，逾時後可重試
- [ ] 三個服務可任意組合：把 Jellyfin 從 `COMPOSE_PROFILES` 拿掉後該服務顯示為既有並出現表單，其餘兩個仍判為套件內
- [ ] Prowlarr 讀不到 API key 時退回手動貼上，也支援 `PROWLARR__AUTH__APIKEY` 的部署方式
- [ ] 探測用到的三個 adapter 各有 `Protocol` 介面與 `Fake`，契約測試對 `tests/fixtures/http/` 的錄製回應綠燈
- [ ] 前兩步各自可重跑且不產生重複資料
- [ ] 未完成 setup 時直接開 `/` 會被導向 `/setup`
- [ ] playwright 對 Fake 後端跑通前兩步並附結果

## Comments
