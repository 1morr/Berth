# 10 — 精靈完成與空媒體庫時落在探索；JSX 註解外露與它的閘門

**Status:** ready-for-agent

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

- [ ] 精靈完成 → 探索；有入庫紀錄的使用者登入 → 媒體庫；`?redirect=` 照舊優先（vitest，三條）
- [ ] 第 2 步畫面不再出現註解文字（playwright 文字結果）
- [ ] lint 規則的雙向變異測試；`pnpm -C web lint` 綠燈
- [ ] brief §19 那一列與 plan §7 同步
- [ ] lint、type、test、前端 e2e 綠燈

## Comments
