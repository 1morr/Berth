# 118 — 精靈介面登入的兩個小尾巴

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** 票 07、80、104；`web/src/setup/interfaceLogin.ts`（:196、:219 預填、`ownerUnfit`）；`web/src/i18n/resources.ts`（:4138 附近 `Reusing the Jellyfin login`）；`web/src/setup/QbittorrentStep.tsx`、`IndexerStep.tsx`

## 為什麼

協調者審查（2026-10-20）票 104 留下的兩件小事：

1. 票 104 起，頁 2／4 的「已沿用 Jellyfin 帳密」改讀後端記錄，重新整理後也留著。中文「已沿用」是完成式，英文 `Reusing the Jellyfin login (…)` 是進行式，讀起來像在說現況；擁有者事後在 Berth 以外改了密碼時，英文更容易誤導。
2. 帳號欄預填擁有者名字是票 07 定的設計（頁 2、4 共用同一個 hook）。但擁有者名字不合 qBittorrent 的帳號規則（`ownerUnfit`）時，頁 2 仍預填這個不合格的帳號，要送出才報錯。Prowlarr 沒有規則，頁 4 不受影響。

## 做什麼

1. en 改成完成式，說的是「設定成」而不是「正在沿用」，例如 `Set to your Jellyfin login ({{user}})`；zh-Hant 不動。
2. `ownerUnfit` 時不預填帳號，其餘照舊。

## 驗收

- [ ] en 的已沿用句是完成式（vitest）
- [ ] 擁有者名字不合 qBittorrent 規則時，頁 2 帳號欄是空的；合規則時照舊預填（vitest，zh-Hant 與 en）
- [ ] 全部檢查、vitest 綠；CHANGELOG、progress.md 已更新
