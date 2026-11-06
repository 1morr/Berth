# 09 — `rss.subscribe` 退回關鍵字來源，拿掉舊的四支工具

**Status:** ready-for-agent

**Blocked by:** 07、08

**讀:** spec〈範圍〉C3、〈驗收〉；研究文檔 §4 C3 與 `subscribe` 草稿；plan §7〈確認卡〉「訂閱的字幕組由人選」；票 08 的 Comments

## 為什麼

把 C3 收尾：Mikan 找不到時伺服器自己改走 nyaa / acg.rip 關鍵字，模型就不用再懂兩條路。改完之後，給模型的工具從 22 支減到 18 支。

## 做什麼

1. `rss.subscribe` 在 Mikan 找不到番組、或番組上沒有模型給的那個字幕組時，改走關鍵字來源（沿用 `subscribe_search` 的搜尋、字幕組與第一批）。
2. 卡片列出找到的字幕組**與來源**（Mikan / 關鍵字站），由人選一個；兩條路都有那個字幕組時怎麼排、預選哪一個，在這張票定並寫進 Comments。讀不到來源時照舊不出卡（`feed_unreachable`）。
3. 給模型的工具清單拿掉 `bangumi.search_bangumi`、`bangumi.read_bangumi`、`rss.subscribe_mikan`、`rss.subscribe_search`。命令本身留著，RSS 頁還在用。
4. 照研究文檔的草稿改寫 `subscribe` skill（≤ 20 行），讓 skill 總行數 ≤ 80。
5. 確認卡的訂閱列顯示來源，文案走 i18n。
6. 文件：brief §14、plan §6〈rss〉〈agent〉、§7〈確認卡〉。

## 驗收

- [ ] Mikan 沒有番組時走關鍵字來源，卡片寫出來源；Mikan 有番組但沒有那個字幕組時也是（整合測試）
- [ ] 給模型的工具 18 支，由測試斷言清單
- [ ] RSS 頁的 Mikan 訂閱與關鍵字訂閱行為不變（既有測試綠）
- [ ] `subscribe` skill ≤ 20 行，skill 總行數閘門綠
- [ ] 卡片的來源顯示有 vitest；brief §14、plan §6、§7 已改
- [ ] 全部檢查、pytest、vitest 綠；progress.md 已更新

## Comments
