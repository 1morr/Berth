# 10 — 精靈完成與空媒體庫時落在探索；JSX 註解外露與它的閘門

**Status:** done

**Blocked by:** None — can start immediately

**讀:** brief §19 2026-09-24「探索頁只放 TMDB 牆、登入後落在媒體庫」與 2026-09-26「精靈與探索的試跑回饋」兩列；plan §7；`web/src/auth/destination.ts`

## 為什麼

- **落地頁**：2026-09-24 拍板「登入後落在媒體庫」（`web/src/auth/destination.ts:7` `HOME = '/library'`），那是給日常
  使用的——接著看的兩列在那裡。可是剛跑完精靈、或 Berth 還沒入庫過任何東西時，媒體庫是空的（2026-09-26 使用者試跑；
  `berth-lab` 接既有服務時同樣落在一個「還沒有任何作品」的空牆）。第一件要做的事是找片，應該落在探索。
- **程式碼註解顯示在畫面上**：`web/src/setup/DetectStep.tsx:110` 把 `// 探測做完、…（StepFrame，票 06h）。` 寫在
  JSX 子節點裡，精靈第 2 步探測完就印在「前往泊位 1」上方（套件內與既有兩種都看得到，2026-09-26 實測）。
  這種錯 `react/jsx-no-comment-textnodes` 規則會擋，專案沒裝任何提供它的 ESLint 外掛。

## 做什麼

1. 沒有指定去處時：精靈剛完成、或這位使用者看得到的媒體庫裡 Berth 一筆帳本都沒有 → 探索（`/`）；其他 → 媒體庫。
   規則寫成純函式、放在 `destination.ts` 旁邊。
2. `DetectStep.tsx:110` 改成 `{/* … */}`。
3. 閘門：用 context7 查 `eslint-plugin-react` 與 `@eslint-react/eslint-plugin` 哪個支援 ESLint flat config 與目前的 React 版本、
   仍在維護，裝其一並開 `jsx-no-comment-textnodes`（只開這一條以外有價值的再說，不整包 recommended）。
   雙向變異寫在 eslint 的測試或 `web/src/lint.test.ts` 類的地方：造一個違規證明會紅，改無關格式證明不紅。

## 驗收

- [x] 精靈完成 → 探索；有入庫紀錄的使用者登入 → 媒體庫；`?redirect=` 照舊優先（vitest，三條）
- [x] 第 2 步畫面不再出現註解文字（playwright 文字結果）
- [x] lint 規則的雙向變異測試；`pnpm -C web lint` 綠燈
- [x] brief §19 那一列與 plan §7 同步
- [x] lint、type、test、前端 e2e 綠燈

## Comments

- 2026-09-27 實作：「精靈剛完成」沒有另一個旗標——精靈跑完是登出狀態，下一次登入時帳本必然是空的，由「帳本一筆都沒有」那一條接住（vitest 走整條：完成設定 → 登入 → `/`）。規則在 `web/src/auth/destination.ts`（`internalRedirect`、`home`），後端欄位是 `GET /inventory` 的 `has_imports`。外掛選 `@eslint-react/eslint-plugin`：`eslint-plugin-react` 的 peerDependencies 到 ESLint ^9.7。
- code-review 已處理：`destination` 問媒體庫不重試（原本多卡約 7 秒）；`libraries_with_imports` 改回與牆同一個 `owning_route` 判斷；測試的媒體庫 fixture 收成 `inventoryLibraries()`；`lint.test.ts` 的反例改成大括號、字串、屬性裡都有 `//`。
- code-review 未處理（判斷題，留著）：
  - 帳本算任何一列，字幕與 Extras 也算（票面字面）。只有 Berth 補字幕的媒體庫會落在媒體庫，那裡接著看的兩列是空的。
  - `GET /inventory` 每次載入切換列多跑每條 Route 一次查詢（找到一列就停）。媒體庫頁每次進場付這個成本，量級與牆的 `_survey` 相比很小，沒量。
  - `destination.ts` 同時放純規則與問媒體庫的那一支；分檔只換來多一個 import。
  - e2e 的 `/票 06h|StepFrame/` 斷言只擋得住那一行字，通用的防線是 lint 規則；留著是因為票要 playwright 的文字結果。
  - `api/inventory.py` 的 `InventoryLibraryChoiceOut(**InventoryLibraryOut.model_validate(row).model_dump(), …)` 繞一圈（`BrowsableLibrary` 是 dataclass、`sorts` 是 property，`model_validate` 沒有 `update`）。
