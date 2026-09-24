# 06c — 精靈第 1 步：剖面說實話（帳密寫到哪裡、偵測之前不知道是不是套件內）

**Status:** ready-for-agent

**Blocked by:** None — can start immediately（只動 `web/src/setup/AdminStep.tsx`、i18n 與它的測試）

**讀:** plan §9.3 第 1、2 步；brief §16.3（來源逐服務判斷）；`DESIGN.md` 的剖面（`Cutaway` / `CutawayRow`）；`web/src/setup/AdminStep.tsx`

## 做什麼

使用者 2026-09-24 重跑精靈時看到第 1 步左邊的「將會寫入」剖面，指出兩個問題。

**1. 標籤與值對不上。** 四列的值都是**帳號**（`account`），但 qBittorrent 那一列的標籤是「qBittorrent WebUI **密碼**（第 4 步）」，畫面讀起來像「密碼是 admin」。Prowlarr 那一列是「介面登入」，也只列出帳號。後端寫的其實是整組帳密：qBittorrent 的 `web_ui_username` 與 `web_ui_password`（`services/qbittorrent.py`），Prowlarr 的 forms 驗證加帳號密碼（`services/indexer.py`）。三個服務的標籤統一改成「帳密」，值寫成「帳號・密碼同上」，不顯示密碼本身。

**2. 偵測之前就把話說死了。** 偵測是第 2 步，第 1 步時 Berth 還不知道哪個服務是套件內的，畫面卻寫得像已經確定：

- 剖面的 Jellyfin / qBittorrent / Prowlarr 三列無條件寫「admin」。後端只寫**套件內**的（`indexer.py`、`qbittorrent.py` 的 `origin is BUNDLED` 條件）；既有 Jellyfin 是要求使用者用它自己的管理員登入（plan §9.3 第 1 步），不會建立管理員。
- lede「之後的步驟會用它建立 Jellyfin 管理員」同樣只在 Jellyfin 是套件內時成立。
- 勾選框的提示「只影響套件內的服務」是對的，但沒說要到第 2 步才知道，和左邊的剖面互相矛盾。

**不改步驟順序**：先建管理員是 Jellyfin 自己的啟動精靈、Home Assistant、Jellyseerr 共同的慣例，而且管理員不存在時精靈的 API 誰都呼叫得到，先把門關上。改的是剖面照 `status.services` 的狀態說話：

| 狀態 | Jellyfin 列 | qBittorrent / Prowlarr 列（勾選時） |
| --- | --- | --- |
| 還沒偵測（第一次走到第 1 步） | 「admin・密碼同上（第 2 步偵測到是套件內的才建立）」 | 「admin・密碼同上（第 2 步偵測到是套件內的才寫入）」 |
| 已偵測、套件內（回來按「改帳密」） | 「admin・密碼同上」 | 「admin・密碼同上」 |
| 已偵測、既有 | 「你自己的服務：用它的管理員登入，不建立」 | 「你自己的服務，不寫入」 |
| 沒勾選 | 照上面 | 「不套用」（現有的 `skipped`） |

lede 改成條件句（「Jellyfin 是套件內的話，之後會用它建立 Jellyfin 管理員」）；勾選框的提示補上「第 2 步會判斷每個服務是套件內還是你自己的」。

「已偵測」讀 `status.services` 裡該服務的判定：`origin` 是 `bundled` → 套件內，`existing` → 既有；`pending`、`timeout` 或清單裡沒有那個服務都當「還沒偵測」（`domain/enums.ServiceOrigin`）。判定到文案的對應是純函式，放在 `AdminStep.tsx` 旁邊。

## 驗收

- [ ] 剖面三個服務的標籤都是「帳密」，值是「帳號・密碼同上」，畫面上不出現密碼本身
- [ ] 未偵測、套件內、既有、沒勾選四種狀態的剖面文案各有前端測試；對應函式有單元測試，涵蓋探測中與逾時當成未偵測
- [ ] lede 與勾選框提示不再在偵測前斷定 Jellyfin 會被建立管理員
- [ ] zh-Hant 與 en 並列
- [ ] playwright 實跑：全新環境走到第 1 步（未偵測）一張；走完精靈回到第 1 步（已偵測）一張；1280 與 390。附結果
- [ ] plan §9.3 第 1 步的敘述若與畫面不一致，同步改
- [ ] lint、type、test 綠燈
