import { defineConfig, devices } from '@playwright/test'

// 瀏覽器那一層的 e2e（plan §10）：每條流程對一個演練情境（`scripts/fake_setup_server.py`）跑。
// 替身是**有狀態**的，一條流程改過的東西另一條看得到，所以一條流程獨佔一台 server、
// 不重試（重跑一次面對的是被上一次改過的替身，綠了也不代表什麼）。
// 前端產物要先有：server 發的是 `web/dist`（`pnpm build`）。
const FLOWS = [
  { spec: 'wizard', scenario: 'bundled', port: 8491 },
  { spec: 'submit', scenario: 'import', port: 8492 },
  { spec: 'review', scenario: 'review', port: 8493 },
  { spec: 'issues', scenario: 'issues', port: 8494 },
] as const

const origin = (port: number) => `http://127.0.0.1:${port}`

export default defineConfig({
  testDir: './e2e',
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    ...devices['Desktop Chrome'],
    // 選擇器寫的是 zh-Hant 文案；語言由 `navigator.languages` 決定（`src/i18n/index.ts`）。
    locale: 'zh-TW',
    // 失敗時的證據：CI 把 `test-results/` 與 `playwright-report/` 上傳成 artifact。
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: FLOWS.map(({ spec, port }) => ({
    name: spec,
    testMatch: `${spec}.spec.ts`,
    use: { baseURL: origin(port) },
  })),
  webServer: FLOWS.map(({ scenario, port }) => ({
    name: scenario,
    command: `uv run python scripts/fake_setup_server.py --scenario ${scenario} --port ${port}`,
    cwd: '..',
    url: `${origin(port)}/api/health`,
    // 永遠自己起一台：接手一台已經在跑的，等於接手一個被別人改過的替身。
    reuseExistingServer: false,
    timeout: 120_000,
  })),
})
