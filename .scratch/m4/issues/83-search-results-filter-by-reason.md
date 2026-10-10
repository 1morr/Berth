# 83 — 搜尋結果：每一筆說得出為什麼被收起來或略過，使用者用篩選按鈕自己看

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** M4 票 69 的 Comments（筆數的定義、已知限制）、票 49（`fits`）、票 08（自己打關鍵字不篩）；`berth/services/search.py`（模組說明、`search_torrents`、`_about`、`_fits`、`_take`、`SearchView`）；`berth/parser` 的 `mentions` 與 `fits`；`web/src/media/SearchPanel.tsx`、`SearchResults.tsx`、`searchResult.ts`；brief §13、plan §8.4

## 為什麼（2026-10-10 使用者）

目前結果分四類：合併、名字對不上、收起來（年份或類型不符、同名動畫的集號、成人分類）、結果表。畫面只說了「100 筆名字對不上（已略過）」，那 100 筆後端根本沒送到前端；「收起來」的也只能整批展開，每一筆沒寫是因為哪一條被收起來。使用者不知道被略過的是什麼，也就沒辦法判斷 Berth 是不是判斷錯了。

票 69 留下的《Law & Order》混進衍生劇《Law & Order: SVU》也在這張處理：不再硬擋或硬放，改成單獨一類。

## 做什麼

照 Sonarr 手動搜尋的慣例（被拒絕的發佈照樣列出，每一筆標上理由，使用者自己決定抓不抓）。動手前先查證 Sonarr 的做法，結論寫進 brief §20 並附來源。

1. **後端每一筆帶理由**：
   - 每一筆歸到一類：符合、年份不符、類型不符（電影搜到季集）、同名作品的集號、成人分類、**只對上部分名字（可能是衍生劇）**、名字對不上。理由要細到什麼程度，在 shape 時定。
   - 「名字對不上」的也送出來，每類照舊各站輪流取、有上限（The Pirate Bay 對查不到的關鍵字會回熱門清單，全送會讓回應變很大）。
   - 筆數照樣加得起來（`returned = merged + 各類筆數`）。
   - 「只對上部分名字」：照 Sonarr 解析季集記號前面那一段片名，再跟作品的名字比對；不是比對整串是否包含。規則先查證。
2. **前端用篩選按鈕**：
   - 結果表上方一排按鈕，一類一顆，按鈕上帶筆數。預設只開「符合」，其他類按了才一起列出。
   - 每一列標出它屬於哪一類；不是「符合」的那幾類，用一句話說出原因。
   - 可以只看某個站。
   - 解析度、字幕語言這類篩選不在這張。
   - 現在「收起來」的展開區由這組按鈕取代，不要兩種都留著。
3. **自己打關鍵字**：照票 08 不篩，全部列出。要不要標出類別，在 shape 時定。
4. **UI 走 `/impeccable`**：先 `shape`，把稿子給使用者確認後才實作；收尾做 `critique` / `polish`。

## 驗收

- [ ] shape 稿使用者確認過，路徑寫在 Comments
- [ ] 每一類各有一筆例子，後端分得對；「只對上部分名字」以 `Law.and.Order.SVU.S28E01` 搜《Law & Order》為例；pytest 守，做變異驗證
- [ ] 回應的大小有上限；筆數加得起來；pytest
- [ ] 篩選按鈕的開與關、筆數、每一列的理由（兩種語言）、只看某個站；vitest
- [ ] `berth bench` 的 `auto_wrong` 不上升（若有動到解析器）
- [ ] Playwright 實跑：《Nosferatu》(1922) 與《Law & Order》各搜一次，每一類都點開看，1280 與 390 寬各一張截圖。用隔離環境（專案名 `berth-t83`、另一組 port）；**不准碰使用者的 `berth-local`**
- [ ] 全部檢查、pytest、vitest、前端 e2e 綠；`pnpm gen:api` 沒有差異；CHANGELOG、progress.md 已更新

## Comments
