import { defineConfig, devices } from '@playwright/test'

// 瀏覽器那一層的 e2e（plan §10）：每條流程對一個演練情境（`scripts/fake_setup_server.py`）跑。
// 替身是**有狀態**的，一條流程改過的東西另一條看得到，所以一條流程獨佔一台 server、
// 不重試（重跑一次面對的是被上一次改過的替身，綠了也不代表什麼）。
// 前端產物要先有：server 發的是 `web/dist`（`pnpm build`）。
//
// 精靈與接手它的設定頁（票 06h）在桌機與手機兩種寬度各走一次：390 的泊位板是 2+2+1、工作面
// 單欄，按得到的東西不一樣。兩次各自一台替身，理由同上。
const NARROW = { width: 390, height: 844 }

const FLOWS = [
  { name: 'wizard', spec: 'wizard', scenario: 'bundled', port: 8491 },
  { name: 'wizard-390', spec: 'wizard', scenario: 'bundled', port: 8501, viewport: NARROW },
  { name: 'existing', spec: 'existing', scenario: 'mixed', port: 8495 },
  { name: 'existing-390', spec: 'existing', scenario: 'mixed', port: 8505, viewport: NARROW },
  { name: 'cold-start', spec: 'cold-start', scenario: 'starting', port: 8496 },
  {
    name: 'cold-start-390',
    spec: 'cold-start',
    scenario: 'starting',
    port: 8506,
    viewport: NARROW,
  },
  { name: 'settings', spec: 'settings', scenario: 'healthy', port: 8497 },
  { name: 'settings-390', spec: 'settings', scenario: 'healthy', port: 8507, viewport: NARROW },
  { name: 'submit', spec: 'submit', scenario: 'import', port: 8492 },
  { name: 'review', spec: 'review', scenario: 'review', port: 8493 },
  { name: 'issues', spec: 'issues', scenario: 'issues', port: 8494 },
  { name: 'rss', spec: 'rss', scenario: 'rss', port: 8498 },
  { name: 'rss-390', spec: 'rss', scenario: 'rss', port: 8508, viewport: NARROW },
  { name: 'rss-exclusions', spec: 'rss-exclusions', scenario: 'rss', port: 8499 },
  {
    name: 'rss-exclusions-390',
    spec: 'rss-exclusions',
    scenario: 'rss',
    port: 8509,
    viewport: NARROW,
  },
] as const satisfies readonly {
  name: string
  spec: string
  scenario: string
  port: number
  viewport?: { width: number; height: number }
}[]

const origin = (port: number) => `http://127.0.0.1:${port}`

export default defineConfig({
  testDir: './e2e',
  forbidOnly: !!process.env.CI,
  retries: 0,
  // 本機預設的 worker 數會讓十一條同時開 Chromium，撞到 180 秒的啟動逾時（票 06h 實跑）；CI 照預設。
  workers: process.env.CI ? undefined : 4,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    ...devices['Desktop Chrome'],
    // 選擇器寫的是 zh-Hant 文案；語言由 `navigator.languages` 決定（`src/i18n/index.ts`）。
    locale: 'zh-TW',
    // 失敗時的證據：CI 把 `test-results/` 與 `playwright-report/` 上傳成 artifact。
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: FLOWS.map((flow) => ({
    name: flow.name,
    testMatch: `${flow.spec}.spec.ts`,
    use: {
      baseURL: origin(flow.port),
      ...('viewport' in flow ? { viewport: flow.viewport } : {}),
    },
  })),
  webServer: FLOWS.map(({ name, scenario, port }) => ({
    name,
    command: `uv run python scripts/fake_setup_server.py --scenario ${scenario} --port ${port}`,
    cwd: '..',
    url: `${origin(port)}/api/health`,
    // 永遠自己起一台：接手一台已經在跑的，等於接手一個被別人改過的替身。
    reuseExistingServer: false,
    timeout: 120_000,
  })),
})
