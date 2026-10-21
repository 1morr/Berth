# 124 — Berth 的對外網址：通知裡的連結

**Status:** done

**Blocked by:** 123

**讀:** plan §11.5〈通知〉的「連結」；`berth/services/deeplink.py`（Jellyfin `public_url` 的做法，照它的慣例）；`berth/api/settings.py`；票 123 的通知設定頁與 shape；`web/src/` 裡的路由表（作品頁、審核、Issue 的網址）

## 為什麼

通知要能點進 Berth 的那一頁，但 Berth 不知道自己從外面看是什麼網址——現在只有 Jellyfin 有 `public_url`。容器裡猜不出來（反向代理、Tailscale、NAS 的網域），所以交給管理員設一次。

## 做什麼

1. 通知設定頁加一格「Berth 的網址」：沒存過時預填瀏覽器當下的 origin（使用者按儲存才算數），存檔時驗證是 http / https 的絕對網址，結尾的 `/` 正規化。
2. 後端一支「把 Berth 內的路徑組成對外連結」的函式，沒設定時回「沒有連結」；通知內容組字的地方用它。
3. 「可以看了」附作品頁的連結；沒設定時照送、不附。

## 驗收

- [x] 沒存過時欄位預填目前的 origin、存過時顯示存的值（vitest）
- [x] 不是 http / https 絕對網址時 422，畫面說出原因（pytest＋vitest）
- [x] 有設定時「可以看了」帶正確的作品頁連結，沒設定時不帶、照樣送出（pytest）
- [x] 全部檢查、pytest、vitest 綠；CHANGELOG、progress.md 已更新

## Comments

- 2026-10-21 實作（session 紀錄見 progress.md）。
- **連結寫在 embed description 的 Markdown，不放 embed 的 `url`**（票面沒說放哪）：`discord_dm.py embed-url` 對真的 Discord 量九種自架網址，`http://berth:8000` 這種沒有點的主機名放 `url` 是整則 `400` `URL_TYPE_INVALID_URL`，寫成 Markdown 九種都收（brief §20.23）。手機上各種網址的 Markdown 連結是否都可點沒有逐一看。
- **存在新的 `BerthSettings.public_url`，不在 `NotifySettings`**：它是 Berth 自己的網址，之後別的地方要連回 Berth 也讀它；端點暫時掛在 `/settings/notifications/berth-url`，有第二個消費點時再搬。
- **帶 `?` 或 `#` 的網址也擋**（code-review Spec 軸提的，有失效條件：`https://host?x=1` 接上路徑成 `?x=1/media/…`）。驗證與 Jellyfin 的對外網址共用 `deeplink.normalized_public_url`，所以 Jellyfin 那一格同一條規則，兩邊的錯誤文案都改說「不帶 ? 或 #」。已經存進去的舊值不重驗。
- code-review 已改：`set_berth_url` 搬回 `services/notify` 的「設定」段；`public_address` 改名 `normalized_public_url`。
- code-review 未處理：
  - 作品頁路徑 `deeplink.MEDIA_PAGE`（`/media/{media_id}`）與前端 `web/src/routes.tsx` 的 `/media/$mediaId` 只靠註解綁著，沒有閘門；前端改路由時通知連結會靜靜壞掉。要守得有一份兩邊都讀的來源，現在只有這一條路徑，沒做。
  - 同一個概念的名字：設定欄位 `public_url`、API 欄位 `berth_url`、畫面「Berth 的網址」。API 那一層叫 `berth_url` 是因為它掛在通知的回應裡，與 bot、Discord ID 並列；沒改。
  - `BerthUrlSection` 的「草稿 ?? 存的值、儲存、已儲存」與 Jellyfin、qBittorrent 設定頁是第三份同形；不違反標準，沒抽。
  - 票 125 開放「我的 Discord」給一般使用者時，`PUT /settings/notifications/berth-url` 要留在管理員那道門後面。
  - 欄位底下「還沒儲存：預填的是你現在開著 Berth 的網址」在使用者改了欄位但還沒存時，說的仍是預填那一句；留給里程碑收尾的 critique。
