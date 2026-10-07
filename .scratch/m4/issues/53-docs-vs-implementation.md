# 53 — 文件與實作不符清單收尾

**Status:** done

**Blocked by:** 32、33、36、37、40（它們各自改掉表上的幾列；這張收尾，避免來回改）

**讀:** `docs/research/wizard-audit-2026-10-06.md`（「文件與實作不符」整張表、改進清單 P2-10）；brief §19「精靈審計後的八項」；`PRODUCT.md`

## 為什麼

報告列了 16 處文件或文案與實作不符。大部分由前面的票在同一個 commit 修掉，這張逐列核對，處理剩下的。

## 做什麼

1. 表上每一列對一遍：已由前面的票處理的標「已由 NN 處理」。預期的對應：
   - README:27 → 32
   - CONTEXT:110-112、README:28、brief:519、brief:123 → 33
   - README:33、`choice.existing.*`、`routes.fix.existing.qbittorrentMount`、plan §9.5 → 36
   - CONTEXT:122、頁 4 lede vs 既有卡片 → 37
   - 完成頁（重裝時） → 40
   - README:29 → 44
2. 剩下的修掉，或在 Comments 寫明不改的理由：
   - `choice.existing.adds.jellyfin` 漏說頁 1 會建 API key
   - `jellyfin.fix.configuration` 寫死繁中與台灣
   - `connection.fix.whitelist` 與預置腳本的行為不符：先實跑確認預置腳本是不是只補「不存在」的鍵，再決定改文案還是改腳本
   - 票 09 票面與票 20 衝突：在票 09 的 Comments 標「已由 20 推翻」，不改它的驗收
3. brief §3、§16.3、§16.4 頂端的「待改寫」標記，確認相關的票都完成後拿掉。

## 驗收

- [x] 表上 16 列在 Comments 都有結論（已修／已由 NN 處理／不改＋理由）
- [x] `connection.fix.whitelist` 的結論有實跑佐證（指令與輸出）
- [x] 改過的文案 zh-Hant 與 en 並列（vitest）
- [x] brief 不再有 2026-10-06 的「待改寫」標記
- [x] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈

## Comments

**表上逐列結論**（報告的表其實是 17 列，票面寫 16；每列都對過現在的檔案）

| # | 列 | 結論 |
| --- | --- | --- |
| 1 | `CONTEXT.md:110-112` 既有服務「只做檢查…」 | 已由 33 處理（Existing service 改成「只建立與管理 Berth 擁有的物件」） |
| 2 | `CONTEXT.md:122` 泊位四「或任一 Torznab 端點」 | 已由 37 處理（CONTEXT 已無 Torznab） |
| 3 | `README.md:27` 套件內「套用五個建議鍵」 | 已由 32 處理（現在是「一個全域鍵都不寫」） |
| 4 | `README.md:28` 既有 Jellyfin 的加路徑是確認鍵 | 已由 33 處理（併進「建立並檢查」） |
| 5 | `README.md:29` 套件內加九站、既有「用你已經有的站」 | 套件內那一半已由 44 處理；既有那一半 44 沒改到（仍只說用已有的站），**已修**：補上可以測試推薦站、勾選加入、不移除你的站 |
| 6 | `README.md:33` 拿掉 `COMPOSE_PROFILES` 再 `up -d` | 已由 36 處理（兩步：改 profiles＋`docker compose stop`） |
| 7 | `choice.existing.*`「例如都是 /data」 | 已由 36 處理（`sameHost` 說只能是 `/data`；`existingMount.test.ts` 守） |
| 8 | `choice.existing.adds.jellyfin` 漏說 API key | **已修**：說頁 1 用管理員登入、建 API key「Berth」 |
| 9 | 頁 4 lede vs 既有卡片 | Torznab 那一半已由 37 處理；「還沒選」的 lede 仍說你自己的那一台「用你已經有的站」，**已修**：`indexer.lede.choose` 補「也可以加推薦的公開站」。選了之後的 `indexer.lede.existing` 與回頭看的 `setup.revisit.indexer.existing.can` 說「按一次加進去」、卡片說「勾起來的站」（code-review 抓到），**已修**成「勾選通過的加進去」；回頭看那句的「接的是 Prowlarr 時」是 Torznab 時代的殘句，一起拿掉 |
| 10 | `routes.fix.existing.qbittorrentMount`「移到它底下」 | 已由 36 處理（只多加一條 `/data`；`existingMount.test.ts` 守） |
| 11 | `jellyfin.fix.configuration` 寫死繁中、台灣 | **已修**：zh 改成「設定語言與 metadata 地區」，與 en 同義（en 本來就沒寫死） |
| 12 | `connection.fix.whitelist`「重啟讓預置腳本補上」 | **已修（改文案，不改腳本）**，實跑見下 |
| 13 | 完成頁（重裝時）「密碼是精靈裡設的那一組」 | 已由 40 處理（`complete.doors.instanceLogin`：這一輪沒設時說是那一台原本的） |
| 14 | `docs/design-brief.md:519`「偵測套件內…一鍵設定」 | 已由 33 處理（brief 已無這句） |
| 15 | brief:123 vs §16.4（`/data` 以外的值） | 已由 33 處理（§4.4 推翻，progress「偏差與決定」有記） |
| 16 | plan §9.5 NAS 範例 | 已由 36 處理（範例改成各自多掛 `/volume1/berth:/data`） |
| 17 | 票 09 票面「既有沒有勾選與加入」 | **已修**：票 09 的 Comments 標「已由 20 推翻」，驗收不改 |

**`connection.fix.whitelist` 的實跑**（linuxserver/qbittorrent:latest = `5.2.3_v2.0.15-ls478`，scratchpad 裡的空 `/config`，
掛 `deploy/preseed/qbittorrent`，`BERTH_IP=172.28.0.2`；跑完 `docker rm -f`）：

```
$ docker run -d --name berth-t53-qb -e BERTH_IP=172.28.0.2 -v …/config:/config -v …/deploy/preseed/qbittorrent:/custom-cont-init.d:ro lscr.io/linuxserver/qbittorrent:latest
[berth-preseed] added to /config/qBittorrent/qBittorrent.conf: WebUI\AuthSubnetWhitelistEnabled=true WebUI\AuthSubnetWhitelist=172.28.0.2/32
# 以 log 裡的臨時密碼登入 WebUI API，模擬使用者在 WebUI 取消勾選
$ docker exec berth-t53-qb curl … --data-urlencode 'json={"bypass_auth_subnet_whitelist_enabled":false}' …/api/v2/app/setPreferences
200
WebUI\AuthSubnetWhitelist=172.28.0.2/32
WebUI\AuthSubnetWhitelistEnabled=false
$ docker restart berth-t53-qb
[berth-preseed] already configured, leaving /config/qBittorrent/qBittorrent.conf untouched
WebUI\AuthSubnetWhitelist=172.28.0.2/32
WebUI\AuthSubnetWhitelistEnabled=false
```

預置腳本確實只補「不存在」的鍵；關掉勾選時清單本身留著。**選改文案**：brief §16.3「之後使用者在各服務介面改什麼都行」是決定（同一句原本寫「只在設定檔不存在時寫入一次」，
與 §20.7 的缺鍵才補不符，順手改掉），腳本每次強制打開會蓋掉使用者的選擇（也可能蓋掉他自己加的子網）。文案改說
到 qBittorrent 的「選項 → WebUI → 驗證」勾回「讓已在白名單中的 IP 子網路略過驗證」（標籤取自 qBittorrent 5.0 的
`webui_zh_TW.ts` 與 `preferences.html`）、預置那一行要留著；原本畫面上唯一可複製的 `docker compose restart qbittorrent`
拿掉（code-review 指出它只在兩個鍵整個不見時有用，照著按多半白跑），`ServiceChoice.test.tsx` 守著（加回就紅，實測過）。
不寫死 172.28.0.2：e2e 換了 `BERTH_IP`，說「Berth 的位址，結尾是 /32」。實跑結論與標籤來源補進 brief §20.7，plan §9.2 指過去。

**brief 的待改寫標記**：§16.3 頂端的「其餘待拆票後改寫」改成列出 D3 已由 37、44 寫進 Prowlarr 那一列；§19「精靈審計後的
八項」那一列的「其餘本文待改寫」改成 D2–D7 由哪幾張票寫進本文。§3、§16.4 頂端的 2026-10-06 註記本來就是「已改寫」的紀錄，
沒有待改寫字樣，留著當歷史（同 2026-09-29 的那幾段）。

**守著的測試**：`web/src/i18n/auditCopy.test.ts`（四句 × zh-Hant / en，樣式自己先做雙向檢查：抓得到原本的寫法、不誤抓無關的說法）。

**code-review（`6c402e2` 起）**

- 已修（Standards）：brief §16.3「預置只在設定檔不存在時寫入一次」與 §20.7 的缺鍵才補矛盾，改掉；實跑結論與 qBittorrent 標籤來源補進 brief §20.7（原本只在 plan 與票）；測試樣式放寬並補「換個說法照樣抓得到」（原本的反例只是新句原文）、`ALLOWLIST_OPTION` 註明逐字比對是刻意的；英文兩處語句（雙冒號、`on it on page 1`）。
- 已修（Spec）：拿掉重啟指令；頁 4 既有的「按一次加進去」兩句（見上表第 9 列）。
- 未處理（判斷題）：「重啟補不回來」的理由寫在 resources 註解、`ServiceChoice.tsx`、測試檔頭、plan、brief、CHANGELOG 幾處——各自的讀者不同，brief §20.7 是事實的單一來源，其他處只留一句指過去。

**驗證**：`uv run pre-commit run --all-files` 全部 Passed；`uv run pytest -m "not e2e"` 3620 passed（後端沒改）；`pnpm -C web typecheck` 綠；`pnpm -C web test` 88 files / 1379 passed；`pnpm -C web e2e` 35 passed（前一輪 exit 1、沒印出任何測試結果，輸出被濾掉看不到原因；原樣重跑綠燈）。
