# 79 — 搜尋結果不再把 Prowlarr 的 API key 交給瀏覽器

**Status:** ready-for-agent

**Blocked by:** None — can start immediately（與 69 都改搜尋；79 先做，69 排在它之後）

**讀:** 票 76 的 Comments〈`/api/search` 把 Prowlarr 的 API key 交給一般使用者〉；M2 票 08（搜尋結果不落地）；brief §20.7（Prowlarr 代理連結每次搜尋都不一樣）；`berth/api/search.py`、`berth/services/search.py` 的 `download_url`；`berth/api/jobs.py` 的 `JobSourceIn`；`berth/api/gate.py`；`web/src/media/SubmitAction.tsx`

## 為什麼（2026-10-09 票 76 實作時發現）

- 搜尋結果的 `download_url` 是 Prowlarr 的代理下載連結：`http://prowlarr:9696/<id>/download?apikey=<Prowlarr key>&link=...`。
- `/search` 不在 `gate.ADMIN_PREFIXES`，任何登入的 Jellyfin 使用者都拿得到這把 key。前端只是把它原樣送回 `POST /jobs` 的 `source.url`。
- 拿到 Prowlarr 的 API key 就能改 Prowlarr 的設定、索引站與帳密。
- 同一個流程的反面：`source.url` 是任意字串，送單時 Berth 在伺服器端去抓它。登入的使用者能讓 Berth 去抓任何網址，包括內網。

## 做什麼

1. **連結不出伺服器**：
   - 搜尋時，Berth 在伺服器端記下每一筆結果的下載連結。回給前端的只有一個不透明的 id，不再有 `download_url`。
   - 送單（`POST /jobs`）收這個 id，由伺服器換回真正的連結。id 過期或不認得時，回一個說得出原因的拒絕（例如「這筆搜尋結果過期了，再搜一次」），走 i18n。
   - 怎麼記、記多久、重啟後怎麼辦，由實作決定，理由寫在 Comments。不必落地到資料庫：票 08 的「搜尋結果不落地」仍成立，過期重搜就好。
   - 先看成熟產品怎麼做（Sonarr / Radarr 的 interactive search 送單只送 guid 加 indexer id），說明採用了誰的慣例。
2. **`POST /jobs` 不再收任意網址**：手動送單只能指向這次搜尋記下的結果。其他還收網址的入口（一次性連結等）照實盤點：
   - 只有管理員能用的，記在 Comments；
   - 一般使用者也能用的，一起收緊，或在 Comments 寫明為什麼不用。
3. **API 破壞性變更**：`GET /search` 拿掉 `download_url`、`POST /jobs` 的 `source` 換成 id。同一 commit 改 API 型別、前端與 CHANGELOG（Security），plan §8.4 與 brief 同步，progress.md「偏差與決定」記一行。
4. 測試（雙向，寫在測試檔內）：
   - 一般使用者打 `GET /search`，回應全文搜不到 Prowlarr 的 API key；
   - 用 id 送單成功；
   - 用不認得或過期的 id 送單被拒；
   - 直接送一條任意網址，被拒或已經沒有這個欄位。

## 驗收

- [ ] `GET /search` 的回應不含任何 Prowlarr 的 API key；有測試守著（含一般使用者）
- [ ] `POST /jobs` 只收這次搜尋記下的結果 id，任意網址送不進來；過期或不認得的 id 有 i18n 的說法
- [ ] 其他收網址的入口已盤點並處理，結論在 Comments
- [ ] 實跑：隔離環境（專案名 `berth-t79`、另一組 port）用一般使用者搜尋並送單成功，瀏覽器 Network 面板的回應裡沒有 `apikey`，附截圖；**不准碰使用者的 `berth-local`**
- [ ] 全部檢查、pytest、vitest、前端 e2e 綠；CHANGELOG（Security）、plan、brief、progress.md 已更新
