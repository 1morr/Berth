# 25 — 補法照原因給，不照檢查項目給

**Status:** ready-for-agent

**Blocked by:** None — can start immediately（與 24 都碰頁 3，不改同一段；衝突時 24 先）

**讀:** `docs/research/wizard-qa-2026-10-01.md`（第 4、10、11、12、13、19 條）；plan §9.3 第 3 點、§9.5；票 19、21 的 `## Comments`；
`web/src/components/routeChecks.ts`、`web/src/components/failures.ts`

## 為什麼（2026-10-01 精靈實測）

- **Berth 自己寫不進去時補法指錯（P1，兩邊實測證實）。** `remedyFor` 沒有特判 `berth_cannot_write`，照檢查項目落
  （`web/src/components/routeChecks.ts:151-176`）：寫不進寫入目標 → 「Jellyfin 沒掛 /data」＋jellyfin 片段；寫不進分類目錄 →
  「qBittorrent 沒掛 /data」；建不了分類目錄 → 「同名分類衝突」；目錄被刪 → 「不在 /data 底下」。照做都修不好。
  截圖 B5-08/09、E12-03～06。`save_path_missing` 也落到 berth 掛載片段（程式碼疑點）。
- **協定錯說成連不上（既有）。** https 填到 http 的 port（SSL WRONG_VERSION）、位址沒寫 `http://`（UnsupportedProtocol）
  都歸成 `unreachable`、叫人確認 port（`berth/adapters/http.py:127-132`）；位址欄不驗格式。截圖 E2-06～09。
- **library_path 的補法叫人改選新路徑，但 Route 已鎖（既有）。** 沒說要先刪這條 Route（`resources.ts:855`）。截圖 E8-07。
- **非管理員在精靈期間看到「Berth 後端可能沒在跑」（既有）。** 實際是 403（`SetupPage.tsx:390`、`resources.ts:40`）。
  同類：擁有者被搶先成立時的 401 說成「後端出錯了」。截圖 E10-05、E12-11。
- **只有 Berth 時選套件內 Prowlarr，說成「讀不到 API key」（既有）。** 先查 key 才連線（`berth/services/setup.py:462-465`），
  要貼了 key 才說主機名解不到。截圖 E9-07～09。
- **qBittorrent 停掉時頁 2 綠紅並存（全新）。** 連線卡綠，下方紅「主機名解不到：不在這套 compose 裡」（原因錯），沒有重新
  測試鍵、前進鍵照在；容器恢復要重新整理（`ServiceChoice.tsx:674-679`、`QbittorrentStep.tsx:219-259`）。截圖 B9-04～07。

## 做什麼

1. `berth_cannot_write`（以及 `save_path_missing`）有自己的補法：說是 Berth 自己寫不進 `<路徑>`，指向 PUID/PGID 與目錄權限，
   不給別的容器的片段。「目錄不存在」與「不在 /data 底下」分開。
2. 連線例外多分兩種：TLS 協定不符、位址缺 scheme；人話分別說「這個 port 講的是 http／https」「位址要以 http:// 開頭」。
   位址欄前端先驗 scheme（照 *arr 的做法不自動補，直接提示）。
3. library_path 的補法：Route 已建好時說「先刪這條 Route，再選新的 Berth 路徑」。
4. 對 Berth 自己的 401／403 分開說：沒登入 → 請登入；不是管理員 → 「精靈只有 Jellyfin 管理員能繼續」；擁有者已在別處成立 →
   說出來並給登入連結。
5. 套件內 Prowlarr 先連線再讀 key：主機名解不到時照 Jellyfin、qBittorrent 的句子。
6. 頁 2 連線卡跟著最新的失敗變紅、出現「重新測試」，套用中斷時不留前進鍵；原因照實際例外。

## 驗收

- [ ] vitest：`berth_cannot_write` 在檢查 1、3、5 都給同一條「Berth 寫不進」的補法、沒有 jellyfin／qbittorrent 片段（雙向：
      真正的 `probe_unseen`、`jellyfin_cannot_see` 仍給各自的片段）
- [ ] 整合測試：https 對 http、缺 scheme 各得到新的理由；真正連不上仍是 `unreachable`
- [ ] vitest：非管理員、未登入、擁有者已存在三種 401／403 各有自己的人話
- [ ] 整合測試：只有 Berth 時選套件內 Prowlarr → `not_deployed`，不是 `api_key_missing`
- [ ] playwright 對 `berth-existing` 與套件內各實跑：唯讀目錄、https 對 http、非管理員登入、停掉 qBittorrent。附截圖或文字結果
- [ ] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈
