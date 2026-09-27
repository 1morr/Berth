import { expect, test } from '@playwright/test'

import { signIn } from './login.ts'

// `downloads`：SPY×FAMILY 已經有五筆下載（`scripts/fake_setup_server.py` 的 `_seed_downloads`）——排隊中、
// 下載中（替身 qBittorrent 每一輪多 7%）、待審核、已入庫一個待確認、已入庫確認過。作品頁的「下載」段
// 預設列前四筆（M4 票 12）。桌機與手機各跑一次（playwright.config.ts）。
const QUEUED = 'SPY×FAMILY - 08'
const LIVE = 'SPY×FAMILY - 25'
const HELD = 'SPY×FAMILY - 01'
const TO_CONFIRM = 'SPY×FAMILY - 05'
const DONE = 'SPY×FAMILY - 04'

test('作品頁列出這部作品還沒了結的下載，展開看得到檔案，進度自己動', async ({ page }) => {
  await signIn(page, '/media/tv:120089')

  const section = page.getByRole('region', { name: '下載' })
  const row = (name: string) => section.locator('details').filter({ hasText: name })
  await expect(section.getByText('還沒了結 4')).toHaveAttribute('aria-current', 'true')
  for (const name of [QUEUED, LIVE, HELD, TO_CONFIRM]) await expect(row(name)).toBeVisible()
  await expect(row(DONE)).toHaveCount(0)
  await expect(row(QUEUED)).toContainText('已送出')
  await expect(row(HELD)).toContainText('待審核')
  await expect(row(TO_CONFIRM)).toContainText('1 個待確認')

  // 即時：替身每一輪多 7%（過了 95% 回到 5%），poller 每 5 秒一輪，推播一秒內併成一次重問（票 04）。
  const progress = async () =>
    Number((await row(LIVE).locator('summary').innerText()).match(/進度 (\d+)%/)?.[1] ?? -1)
  await expect.poll(progress, { timeout: 20_000 }).toBeGreaterThan(0)
  const first = await progress()
  await expect.poll(progress, { timeout: 20_000 }).not.toBe(first)

  // 展開：檔名、大小與 pre-plan 對到的季集。替身 TMDB 只列第一季的兩集，所以這一份的預估停在待審，
  // 提案的季集照樣說得出來。
  await row(LIVE).locator('summary').click()
  const file = row(LIVE)
    .getByRole('listitem')
    .filter({ hasText: `${LIVE} [1080P]` })
  await expect(file).toContainText('S01E25', { timeout: 20_000 })
  await expect(file).toContainText('待審')
  await expect(file).toContainText('1.3 GB')
  await expect(row(LIVE).getByRole('link', { name: '下載詳情' })).toHaveAttribute(
    'href',
    '/jobs/' + 'd2'.repeat(20),
  )

  // 季表的「下載中」「卡住」連到那一筆。
  const seasons = page.getByRole('region', { name: '季集與入庫' })
  await seasons.getByText('Season 1', { exact: true }).click()
  const episodes = seasons.getByRole('table', { name: 'S01 的每一集' })
  await expect(
    episodes.getByRole('row').filter({ hasText: 'S01E25' }).getByRole('link', { name: '下載中' }),
  ).toHaveAttribute('href', '/jobs/' + 'd2'.repeat(20))
  await expect(
    episodes.getByRole('row').filter({ hasText: 'S01E01' }).getByRole('link', { name: '卡住' }),
  ).toHaveAttribute('href', '/jobs/' + 'd3'.repeat(20))

  // 「全部」多出確認過的那一筆。
  await section.getByRole('button', { name: '全部 5' }).click()
  await expect(row(DONE)).toBeVisible()
  await expect(section.getByText('全部 5')).toHaveAttribute('aria-current', 'true')

  // 窄版不橫向捲動整頁（發佈名、檔名都整行換行）。
  // 字串而不是函式：e2e 的 tsconfig 沒有 DOM 型別，這一行在瀏覽器裡跑。
  const overflow = await page.evaluate(
    'document.documentElement.scrollWidth - document.documentElement.clientWidth',
  )
  expect(overflow).toBe(0)
})
