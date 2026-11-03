import { expect, test, type Locator, type Page } from '@playwright/test'

import { CREW, signIn } from './login.ts'
import { shot } from './shot.ts'

// 時間表（M5.5 票 09，`.scratch/m5.5/schedule-shape.md`），`schedule` 情境：時鐘停在 2026-09-25 週五，
// 《与你相恋》第 12 集週四播（09-24），另外六部分在這一週。未訂閱的卡片點進作品頁，用 acg.rip 的
// 「只追之後的」訂閱（一筆都不送，不會被入庫搶先變成「已入庫」），回到時間表那張卡就是「已訂閱」。
// 接著換一般使用者：看得到時間表與狀態，看不到「訂閱」分頁，回應裡沒有字幕組與 Feed。

const KIMI = '與妳相戀到生命盡頭'

/** 桌機是七欄；窄版（< lg）一次一天，預設今天（週五），所以先選週四。 */
async function thursday(page: Page): Promise<Locator> {
  // 先等資料到（讀取中兩種版面都還沒有），再看是哪一種。
  await expect(page.getByRole('heading', { level: 2 }).first()).toBeVisible()
  const wide = page.getByTestId('schedule-week')
  if (await wide.isVisible()) return wide
  await page.getByRole('group', { name: '選一天' }).getByRole('button', { name: '週四' }).click()
  return page.getByTestId('schedule-day')
}

/** 窄版的日期鍵預設按著今天（週五）；桌機沒有這一排。 */
async function todayIsPicked(page: Page): Promise<void> {
  const picker = page.getByRole('group', { name: '選一天' })
  if (!(await picker.isVisible())) return
  await expect(picker.getByRole('button', { name: /今天/ })).toHaveAttribute('aria-pressed', 'true')
}

/** 頁面沒有橫向捲動。 */
async function fitsWidth(page: Page): Promise<boolean> {
  return page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
}

test('時間表：點未訂閱的卡片進作品頁訂閱，下一次打開那張卡變「已訂閱」', async ({ page }) => {
  await signIn(page, '/schedule')
  await expect(page.getByRole('heading', { level: 1, name: '時間表' })).toBeVisible()
  const tabs = page.getByRole('navigation', { name: '新番' })
  await expect(tabs.getByRole('link', { name: '時間表' })).toHaveAttribute('aria-current', 'page')
  await expect(tabs.getByRole('link', { name: /^訂閱/ })).toBeVisible()

  await expect(page.getByRole('heading', { level: 2 }).first()).toBeVisible()
  await todayIsPicked(page)
  const view = await thursday(page)
  const card = view.getByRole('link', { name: KIMI })
  await expect(card).toHaveAccessibleDescription('S01E12')
  expect(await fitsWidth(page)).toBe(true)
  await shot(page, '1-schedule')

  await card.click()
  await expect(page).toHaveURL(/\/media\/tv(:|%3A)262000$/)
  const block = page.getByRole('region', { name: 'RSS 訂閱' })
  await expect(block).toContainText('還沒有 RSS Series 綁在這部作品上。')
  await block.getByRole('button', { name: '新增訂閱' }).click()
  await block.getByRole('button', { name: /^ACG\.RIP/ }).click()
  await block.getByRole('combobox', { name: '入庫到' }).selectOption('Anime')
  await block.getByRole('button', { name: /^喵萌奶茶屋&LoliHouse/ }).click()
  await block.getByRole('button', { name: /^只追之後的/ }).click()
  await block.getByRole('button', { name: '訂閱，只追之後的' }).click()
  await expect(block.getByText(/只追之後的：現有的一筆都沒送。/)).toBeVisible()

  await page.goto('/schedule')
  await expect(
    (await thursday(page)).getByRole('link', { name: KIMI }),
  ).toHaveAccessibleDescription('S01E12 已訂閱')
  await shot(page, '2-subscribed')

  // 只看已訂閱：只剩這一張。
  await page.getByRole('button', { name: '只看已訂閱' }).click()
  await expect((await thursday(page)).getByRole('link')).toHaveCount(1)
  await shot(page, '3-subscribed-only')
})

test('一般使用者：看得到時間表與狀態，沒有「訂閱」分頁，回應裡沒有字幕組與 Feed', async ({
  page,
}) => {
  await signIn(page, '/schedule', CREW)

  const nav = page.getByRole('navigation', { name: '主要導覽' })
  await expect(nav.getByRole('link', { name: '新番' })).toHaveAttribute('href', '/schedule')
  const tabs = page.getByRole('navigation', { name: '新番' })
  await expect(tabs.getByRole('link')).toHaveCount(1)
  await expect(tabs.getByRole('link', { name: '時間表' })).toBeVisible()

  // 上一條流程訂閱過這一部（同一台替身）：一般使用者看得到「已訂閱」這個類別。
  await expect(
    (await thursday(page)).getByRole('link', { name: KIMI }),
  ).toHaveAccessibleDescription('S01E12 已訂閱')
  expect(await fitsWidth(page)).toBe(true)
  await shot(page, '4-crew')

  const body = (await (await page.request.get('/api/schedule')).json()) as {
    cards: Record<string, unknown>[]
  }
  expect(body.cards.length).toBeGreaterThan(0)
  for (const row of body.cards) {
    expect(Object.keys(row).sort()).toEqual(
      [
        'air_date',
        'episode',
        'media_id',
        'poster_url',
        'poster_url_en',
        'season',
        'status',
        'title',
        'title_en',
        'tmdb_id',
      ].sort(),
    )
  }
  expect((await page.request.get('/api/rss/series')).status()).toBe(403)
  await page.goto('/rss')
  await expect(page).not.toHaveURL('/rss')
})
