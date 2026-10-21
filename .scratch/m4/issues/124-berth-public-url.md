# 124 — Berth 的對外網址：通知裡的連結

**Status:** ready-for-agent

**Blocked by:** 123

**讀:** plan §11.5〈通知〉的「連結」；`berth/services/deeplink.py`（Jellyfin `public_url` 的做法，照它的慣例）；`berth/api/settings.py`；票 123 的通知設定頁與 shape；`web/src/` 裡的路由表（作品頁、審核、Issue 的網址）

## 為什麼

通知要能點進 Berth 的那一頁，但 Berth 不知道自己從外面看是什麼網址——現在只有 Jellyfin 有 `public_url`。容器裡猜不出來（反向代理、Tailscale、NAS 的網域），所以交給管理員設一次。

## 做什麼

1. 通知設定頁加一格「Berth 的網址」：沒存過時預填瀏覽器當下的 origin（使用者按儲存才算數），存檔時驗證是 http / https 的絕對網址，結尾的 `/` 正規化。
2. 後端一支「把 Berth 內的路徑組成對外連結」的函式，沒設定時回「沒有連結」；通知內容組字的地方用它。
3. 「可以看了」附作品頁的連結；沒設定時照送、不附。

## 驗收

- [ ] 沒存過時欄位預填目前的 origin、存過時顯示存的值（vitest）
- [ ] 不是 http / https 絕對網址時 422，畫面說出原因（pytest＋vitest）
- [ ] 有設定時「可以看了」帶正確的作品頁連結，沒設定時不帶、照樣送出（pytest）
- [ ] 全部檢查、pytest、vitest 綠；CHANGELOG、progress.md 已更新
