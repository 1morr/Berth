import eslintReact from '@eslint-react/eslint-plugin'
import js from '@eslint/js'
import { defineConfig, globalIgnores } from 'eslint/config'
import prettier from 'eslint-config-prettier/flat'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import globals from 'globals'
import tseslint from 'typescript-eslint'

/**
 * 後端的原文不當標題（M4 票 21，`.scratch/m4/error-layers-shape.md`）：精靈、設定頁與健康頁裡，`.error` /
 * `.message` 不能直接畫成 JSX 子節點——人話由代碼選（`components/failures.ts`），原文只經
 * `TechnicalDetails` 的 `lines`（屬性，不是子節點）進畫面。`src/lint.test.ts` 用這份設定檔雙向驗它。
 */
const RAW = '[property.name=/^(error|message)$/]'
const CHILD = ':matches(JSXElement, JSXFragment) > JSXExpressionContainer'
const RAW_TEXT_SELECTORS = [
  `${CHILD} > MemberExpression${RAW}`,
  `${CHILD} > ChainExpression > MemberExpression${RAW}`,
  `${CHILD} > LogicalExpression > MemberExpression.right${RAW}`,
  `${CHILD} > LogicalExpression > ChainExpression.right > MemberExpression${RAW}`,
  `${CHILD} > ConditionalExpression > MemberExpression.consequent${RAW}`,
  `${CHILD} > ConditionalExpression > MemberExpression.alternate${RAW}`,
]

export default defineConfig([
  // `src/api/schema.d.ts` 是 `pnpm gen:api` 的產物：不 lint、不格式化，只由 tsc 檢查。
  globalIgnores(['dist', 'src/api/schema.d.ts']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat['recommended-latest'],
      reactRefresh.configs.vite,
      // prettier 放最後，關掉所有和格式化衝突的規則。
      prettier,
    ],
    // 只開需要型別資訊的這兩條，不開整包 `recommendedTypeChecked`。整包在這個 repo 上
    // 抓到的 36 條全是 TanStack Router 的 `throw redirect(...)`（框架慣用法，不是錯）
    // 與測試裡 `RequestInit.body` / `JSON.parse` 的型別噪音，沒有一條是真的缺陷。
    // 這兩條才是票 01 當初把它延後的理由：非同步呼叫忘了 await（票 07 的門禁全靠 await）。
    //
    // `@eslint-react` 也只開一條，不整包 recommended：`// 註解` 寫在 JSX 子節點裡會印在畫面上
    // （M4 票 10，精靈第 2 步實際印出來過），tsc 與 prettier 都看不出來。`eslint-plugin-react`
    // 的 peerDependencies 到 ESLint 9.7 為止，所以用這一套。`src/lint.test.ts` 守著它還開著。
    plugins: { '@eslint-react': eslintReact },
    rules: {
      '@typescript-eslint/no-floating-promises': 'error',
      '@typescript-eslint/no-misused-promises': 'error',
      '@eslint-react/jsx-no-comment-textnodes': 'error',
    },
    languageOptions: {
      ecmaVersion: 2023,
      globals: globals.browser,
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
  },
  {
    files: [
      'src/setup/**/*.tsx',
      'src/components/**/*.tsx',
      'src/settings/**/*.tsx',
      'src/health/**/*.tsx',
      'src/pages/SetupPage.tsx',
      'src/pages/*SettingsPage.tsx',
      'src/pages/HealthPage.tsx',
    ],
    ignores: ['**/*.test.tsx'],
    rules: {
      'no-restricted-syntax': [
        'error',
        ...RAW_TEXT_SELECTORS.map((selector) => ({
          selector,
          message:
            'Backend text is not a headline: pick the sentence from the failure code and put the original in <TechnicalDetails lines={…} />.',
        })),
      ],
    },
  },
])
