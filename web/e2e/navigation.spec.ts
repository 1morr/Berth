import { expect, test, type Page } from '@playwright/test'

import { CREW, signIn } from './login.ts'
import { shot } from './shot.ts'

// 頁首收斂（M5.5 票 07，`.scratch/m5.5/navigation-shape.md`）。`weekly` 情境：產品自己產生了最近兩週的
// 週報，而產生當下等著的那幾件（審核、Issue、待綁定）現在還等著，頁首有數字可看。

/** 主導覽每一項的可存取名稱（帶件數的念成「待處理 3 件」）。 */
async function navNames(page: Page): Promise<string[]> {
  const nav = page.getByRole('navigation', { name: '主要導覽' })
  await expect(nav).toBeVisible()
  const links = nav.getByRole('link')
  const names: string[] = []
  for (let i = 0; i < (await links.count()); i += 1) {
    names.push((await links.nth(i).getAttribute('aria-label')) ?? (await links.nth(i).innerText()))
  }
  return names
}

/** 頁面沒有橫向捲動（390 寬時頁首換行，不撐開整頁）。 */
async function fitsWidth(page: Page): Promise<boolean> {
  return page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
}

test('管理員：五個導覽項帶件數、帳號選單用鍵盤開關、舊網址都打得開', async ({ page }) => {
  await signIn(page, '/jobs')
  const counts = (await (await page.request.get('/api/waiting')).json()) as {
    review: number
    issue: number
    rss: number
  }
  // 情境裡三份清單都有東西：數字各歸各頁，加起來才是 Discord 的 N。
  expect(counts.review + counts.issue).toBeGreaterThan(0)
  expect(counts.rss).toBeGreaterThan(0)

  const waiting = counts.review + counts.issue
  await expect
    .poll(() => navNames(page))
    .toEqual(['探索', `新番 ${counts.rss} 件`, '媒體庫', '下載', `待處理 ${waiting} 件`])
  expect(await fitsWidth(page)).toBe(true)
  await shot(page, 'admin-header')

  // 帳號選單：Enter 打開、下一個 Tab 進到第一項、Esc 收起，焦點回到觸發鍵。
  const trigger = page.getByRole('button', { name: '帳號：skipper' })
  await trigger.focus()
  await page.keyboard.press('Enter')
  await expect(trigger).toHaveAttribute('aria-expanded', 'true')
  await expect(page.getByText('管理員', { exact: true })).toBeVisible()
  for (const name of ['設定', '健康', '週報']) {
    await expect(page.getByRole('link', { name, exact: true })).toBeVisible()
  }
  await shot(page, 'admin-menu')
  await page.keyboard.press('Tab')
  await expect(page.getByRole('link', { name: '設定', exact: true })).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(trigger).toHaveAttribute('aria-expanded', 'false')
  await expect(trigger).toBeFocused()

  // 待處理：分頁列帶各自的件數；在 /issues 上它仍是當前區塊。
  await page
    .getByRole('navigation', { name: '主要導覽' })
    .getByRole('link', { name: /^待處理/ })
    .click()
  await expect(page).toHaveURL('/review')
  // 連結指的就是這一頁：`aria-current="page"`（TanStack 自己掛，`SectionLink` 不蓋掉它）。
  await expect(
    page.getByRole('navigation', { name: '主要導覽' }).getByRole('link', { name: /^待處理/ }),
  ).toHaveAttribute('aria-current', 'page')
  const tabs = page.getByRole('navigation', { name: '待處理' })
  await tabs.getByRole('link', { name: /^Issue/ }).click()
  await expect(page).toHaveURL('/issues')
  await expect(page.getByRole('heading', { level: 1, name: 'Issue' })).toBeVisible()
  await expect(
    page.getByRole('navigation', { name: '主要導覽' }).getByRole('link', { name: /^待處理/ }),
  ).toHaveAttribute('aria-current', 'true')
  await shot(page, 'admin-issues')

  // 舊網址都打得開，Discord 週報連的 `/weekly/{id}` 也是（`services/deeplink.py`）。
  const [latest] = (await (await page.request.get('/api/weekly')).json()) as { id: number }[]
  const pages: [string, string, string][] = [
    ['/rss', '/rss', '訂閱'],
    ['/review', '/review', '審核'],
    ['/issues', '/issues', 'Issue'],
    ['/settings', '/settings/jellyfin', 'Jellyfin'],
    ['/health', '/health', '健康'],
    ['/weekly', '/weekly', '週報'],
    [`/weekly/${latest!.id}`, `/weekly/${latest!.id}`, '週報'],
  ]
  // 新番這一票只有「訂閱」一個分頁（M5.5 票 09 才加時間表），帶待綁定的件數。
  await page.goto('/rss')
  const airing = page.getByRole('navigation', { name: '新番' })
  await expect(airing.getByRole('link')).toHaveCount(1)
  await expect(airing.getByRole('link', { name: `訂閱 ${counts.rss} 件` })).toHaveAttribute(
    'aria-current',
    'page',
  )

  for (const [path, landed, heading] of pages) {
    await page.goto(path)
    await expect(page).toHaveURL(landed)
    await expect(page.getByRole('heading', { level: 1, name: heading })).toBeVisible()
  }
  // 選單裡的頁面上，觸發鍵畫成當前（重橫線加 `deck` 底），人知道自己在哪。
  await expect(trigger).toHaveClass(/bg-deck/)
  await shot(page, 'admin-weekly')
})

test('一般使用者：只有探索、媒體庫、下載與帳號選單，件數端點 403', async ({ page }) => {
  await signIn(page, '/jobs', CREW)

  await expect.poll(() => navNames(page)).toEqual(['探索', '媒體庫', '下載'])
  expect((await page.request.get('/api/waiting')).status()).toBe(403)
  expect(await fitsWidth(page)).toBe(true)

  await page.getByRole('button', { name: '帳號：deckhand' }).click()
  await expect(page.getByText('使用者', { exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: '設定', exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: '健康', exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: '週報', exact: true })).toHaveCount(0)
  await shot(page, 'crew-menu')

  // 點外面收起。
  await page.getByRole('main').click({ position: { x: 5, y: 5 } })
  await expect(page.getByRole('link', { name: '健康', exact: true })).toHaveCount(0)
})
