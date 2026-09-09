import js from '@eslint/js'
import { defineConfig, globalIgnores } from 'eslint/config'
import prettier from 'eslint-config-prettier/flat'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import globals from 'globals'
import tseslint from 'typescript-eslint'

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
    rules: {
      '@typescript-eslint/no-floating-promises': 'error',
      '@typescript-eslint/no-misused-promises': 'error',
    },
    languageOptions: {
      ecmaVersion: 2023,
      globals: globals.browser,
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
  },
])
