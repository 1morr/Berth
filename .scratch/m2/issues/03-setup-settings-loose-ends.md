# 03 — 開工收尾（精靈與設定頁）

**Status:** done

**Blocked by:** 無 —— 可立即開工

**讀:** plan §7（前端那一節）、§9.3（精靈流程）、§11.3 的遺留清單 B 組；brief §16.3；`DESIGN.md`（語言鍵那一條）、`PRODUCT.md`

## 做什麼

M0 / M1 / M1.5 三輪收尾累積下來、落在**精靈與設定頁這一群**的小項。純前端（有兩條要動 i18n
檔），互相獨立，做到哪算哪不影響別的票。探索 / 媒體庫 / 詳情那一群在票 13。

**狀態與動作說得出後果**

1. Route 設定頁表單**沒改過**時「儲存」仍亮，按下去會重跑五條檢查卻沒有任何地方說它要做這件事。
2. 所有路徑都被佔用時「建立並檢查」仍畫成主動作——那時候它一定失敗。
3. 確認區的「取消」比主動作寬，視覺上像是在推人按取消。
4. 通過 TMDB 閘門之後 BTH 3 的詳情列不動（閘門過了，那一列還停在舊狀態）。
5. `complete.failed` 缺憑證時**錯怪後端**：訊息說後端出錯，實際是使用者還沒填憑證。
6. 精靈第 7 步的勾選表**標出已被佔用的路徑**（現在得按下去才知道）。

**文案與 i18n**

7. EN 三句：`Already so` → `Already there`、`Moored` → `Imported`、
   `10 of 46 episodes in` → `10 of 46 episodes imported`。
8. EN 子分頁 `Library paths` → `Routes`（CONTEXT.md 的詞是 Route）。
9. `routes.cutaway.category` 的 zh-Hant 值是英文。
10. 信心在同一塊展開區有**兩套詞**（`信心 high` 與「高信心」），統一成一套。

**視覺與無障礙**

11. 語言鍵選中態的 `assigned` 黃漆改中性色——`DESIGN.md` 自己說黃色是「已指派」的語意色，
    拿它當選中態是那份文件裡的一條矛盾，改色的同時把矛盾收掉。
12. TMDB 與索引站的 API key **三處**一起改 `PasswordField`（現在是明碼 input）。
13. `HealthPage` / `ServiceSettingsPage` / `SetupPage` 補 `<h1>`，並統一三頁 `h1` 的大小與可見性。
14. 非 admin 開 `/settings/*` 現在是**靜默 `redirect`**，改成帶一句訊息（`web/src/routes.tsx` 兩處）。
15. 窄版 Route 列截掉路徑尾巴，三條看起來一模一樣。
16. 健康頁全綠時一千像素裡同一顆綠章重複八次。

**可延**

17. 精靈每一步的左欄剖面與右欄纜繩列是同一份清單，兩份實作。這是重構不是缺陷，時間不夠就留
    Comments 給票 16。

## 驗收

- [x] 上面 1–16 每一條都有結果：修掉（附證據）或在 Comments 說明為什麼不修
- [x] 1–6 各有一個 vitest，斷言的是行為（按鈕狀態、訊息內容）而不是文字片段
- [x] 7–10 的 i18n 鍵在 `zh-Hant` 與 `en` 兩份都有值，沒有一邊是另一邊的語言
- [x] 13 的三頁各有唯一的 `<h1>`；14 的兩處轉址帶得出訊息（測試斷言訊息在畫面上）
- [x] playwright 實跑精靈與兩個設定頁，附截圖或文字結果（專案 CLAUDE.md 的 UI 規則）
- [x] lint、type、test 綠燈

## Comments

### 逐條結果

| # | 結果 | 閘門 |
| --- | --- | --- |
| 1 | `dirty` 才亮，並在鍵下加一句「儲存會重跑下面那五條纜繩」 | `RouteSettingsPage.test.tsx`「沒改過時儲存按不下去」 |
| 2 | 選中的媒體庫沒有空路徑時 `disabled`（漆退成 `deck`，出路是 `NoFreePath` 的 Jellyfin 連結） | 同上檔「沒有空路徑時」 |
| 3 | `CONFIRM_ACTIONS`：取消改 `max-content`，不再吃掉剩下的寬 | `controls.test.tsx`「取消不吃掉剩下的寬度」 |
| 4 | BTH 3 的詳情列在拿得到 TMDB 判定之後改說閘門（待驗證 / 已驗證） | `SetupPage.services.test.tsx`「BTH 3 的詳情列跟著換」 |
| 5 | 422 不再怪後端：前端用手上的 `tmdb.verified` 說是第 6 還是第 7 步，並給回第 6 步的鍵 | `SetupPage.routes.test.tsx` 兩條（422 / 500） |
| 6 | 勾選表的寫入目標標出佔用者（既有 Route + 同一批前面的選擇），`aria-describedby` 帶名字 | `SetupPage.routes.test.tsx`「已經被別條 Route 佔用」 |
| 7 | `Already there`、`Ready`（見下方偏差）、`episodes imported` | 型別（`Translations<T>`） |
| 8 | 子分頁 `Routes` | 同上 |
| 9 | `routes.cutaway.category` zh 改「分類」 | 同上 |
| 10 | 抬頭改「信心 高 N / 中 N / 低 N」，不再把列舉值印進中文句 | `JobPlan.test.tsx`「同一套信心的詞」 |
| 11 | 語言鍵選中態改 `deck`+`ink`，DESIGN.md 三處與 Known contradictions 一併收掉 | `LanguageToggle.test.tsx` |
| 12 | 三處 API key 改 `PasswordField` | `SetupPage.services.test.tsx`「都是遮著的」 |
| 13 | `PAGE_TITLE` 一份，四頁共用；三頁補 `<h1>` | 三個頁面各一條 h1 測試 |
| 14 | `redirect` 帶 `?denied=true`，健康頁就地說明 | `HealthPage.test.tsx`（`it.each` 兩處） |
| 15 | `truncate` → `wrap-anywhere`，與 Route 設定頁同一種畫法 | `HealthPage.test.tsx`「不截斷寫入目標」 |
| 16 | `QUIET_FILL`：板子留漆，底下的卡片與列全綠時中性（字照留） | `HealthPage.test.tsx`「只有泊位板塗綠」 |

### 偏差：第 7 條的 `Moored` → `Imported` 改成 `Ready`

票面寫 `Moored` → `Imported`，但 `Moored` 只有兩個鍵（`routes.health.ok`、`health.state.ok`），
兩個都是健康標籤（zh 皆「已繫上」）；而「已入庫」那一格（`inventory.status.complete`）在 M1 票 13
就已經是 `Imported`。照字面改會把「五條纜繩全綠的 Route」與「連得上的 Jellyfin」標成 Imported。
**使用者 2026-09-22 拍板改 `Ready`**，zh 維持「已繫上」。plan §11.3 的 B 清單已同步。

### `/code-review` 抓到的四件事（都已修）

1. **第 3 條的測試原本是空閘門**：`toHaveClass(...CONFIRM_ACTIONS.split(' '))` 拿元件自己用的常數
   比它自己，把 `max-content` 改回 `auto` 照樣綠。改成對著決定寬度的那一段字面斷言，並**實跑雙向
   變異**：改回 `auto` → 紅；`gap-2` → `gap-3` → 綠。
2. **`completeFailure` 在 `tmdb.data` 還沒載回來時會指錯步**（說第 6 步，而真正卡住的可能是第 7 步）。
   改成兩份狀態都要**明確**說不行才指名，都說沒問題卻仍被擋就說「還有一步沒做完，但看不出是哪一步」
   （新增 `complete.unfinished` 與一條測試）。
3. **`LanguageToggle` 第二條測試近乎恆真**（`className` 不等於另一個）。改成斷言真正的非顏色訊號
   `aria-pressed`；第一條的正規表達式收緊成 `\bbg-assigned\b`，免得日後 `accent-[var(--color-assigned)]`
   這類合法用法誤紅。
4. **`BerthBoard` 硬寫 `'prowlarr'` 字面值**，而 `components/berths.ts` 檔頭寫明「哪一格是哪個服務」
   只放在那裡。改成 `SOURCE_SLOT`。

另外三件小的：`QUIET_FILL` 改名 `UNPAINTED_FILL` 並指回 DESIGN.md 既有的 *The Usual Stays
Unpainted Rule*、常態那一格直接用 `SIGNAL_FILL.neutral` 不再抄一份類名；`routes.tsx` 兩份一模一樣的
admin 守衛抽成 `requireAdminPage`；`CONFIRM_ACTIONS` 的註釋原本只說「就地確認」，但它也用在新增表單的
送出列，改成說實話。

### 兩個知情的擴散（不是缺陷，但票面沒要求）

- **第 16 條的退漆越出健康頁**：改的是共用元件 `RouteIdentity` 與 `ServiceCard`，所以 `/settings/routes`
  與 `/settings/services` 的狀態色塊也一起退漆。這是刻意的——`RouteIdentity` 的檔頭本來就寫「健康頁與
  Route 設定頁的那一列共用，同一件事不該有兩種畫法」，只在一頁退漆才會製造分岔。
- **`.impeccable/design.json` 仍留著語言鍵那條舊的 Known contradiction**，與現在的 `DESIGN.md` 不一致。
  它的同步是**票 13 第 18 項**（`/impeccable document`）的範圍，本票不動；記在這裡是為了讓讀票的人
  知道這個缺口存在而不是被忽略。

### 合併後補記（2026-09-22）

- **第 8 條只改了子分頁，EN 的頁標題仍是 `Library paths`**（`routeSettings.title`、`setup` 那一組的
  `routes.title`，另有一句散文寫「manage routes under Settings → Library paths」指向已改名的那個分頁）。
  票面寫的就是「子分頁」，所以這一票沒做錯；但 CONTEXT.md 的詞是 Route，分頁與標題現在各叫各的。
  留給下一張碰設定頁文案的票。

### 第 17 條（可延）未做，留給票 16

精靈每一步的左欄剖面與右欄纜繩列仍是兩份實作。這是重構不是缺陷，本票已動 13 個檔案，
不在同一輪混進去。

### playwright 實跑（1280 與 390）

`--scenario routes`：第 1 條（儲存 `disabled: true` → 改名後 `false`）、第 2 條（`建立並檢查`
`disabled: true`，`background-color` 實測 `oklch(0.99 0.002 245)` = `deck`，不是 `assigned`）、
第 3 條（確定刪除 224px vs 取消 67px，`grid-template-columns: 224px 66.6px`）、第 8 條（子分頁 `Routes`）、
第 11 條（選中鍵 `bg` = `deck`、未選 = `well`，無黃漆）。
`--scenario bundled`：第 13 條（唯一 `<h1>`「設定精靈」18px）、第 12 條（TMDB 欄 `type=password`）、
第 4 條（過閘門前後 `TMDB 待驗證` → `TMDB 已驗證`，格子轉 `secured`）、第 5 條（真後端 422 的
`detail` 確認是英文散文，所以前端只能靠 status + 自己手上的 `verified` 判斷）。
`--scenario mixed`：第 9 條（剖面表頭「分類」）、第 6 條的勾選表渲染（空路徑不被誤標）。
`--scenario healthy`（`routes` 那一台）：第 13、15、16 條——`/health` 390px 全綠時看得見的綠章
**4 顆且全在泊位板內**，三條 Route 的路徑尾巴（movies / tv / anime）都讀得到。
第 14 條以 `deckhand` 登入實跑，`/settings/routes` → `/health?denied=true` 並顯示說明。

**第 6 條的「正例」沒有在瀏覽器裡跑到**：fake 的 `mixed` 情境裡兩個媒體庫不共用路徑，
做不出「別條 Route 佔走這個媒體庫的某一條路徑」的狀態；瀏覽器裡驗到的是反例（空路徑不被誤標）。
正例由 vitest 蓋（fixture 讓既有 Route 佔走兩條 `locations` 的其中一條）。
