import { expect, test, type Locator, type Page } from '@playwright/test'

import { CREW, signIn } from './login.ts'
import { shot } from './shot.ts'

// 追更（M5.5 票 12，`.scratch/m5.5/tracking-shape.md`），`tracking` 情境：三部訂閱的作品——藥師少女第 5 集
// 四天前播、下載停滯（要你動手），芙莉蓮跟上了（準時），一部最後一集缺集播出滿 60 天（斷更很久）。沒有人接
// Discord，管理員打開時頁首說遲到只會顯示在這裡。桌機是表格、窄版一部一塊，同一份資料畫兩次、各自 `hidden`。

/** 頁面沒有橫向捲動。 */
async function fitsWidth(page: Page): Promise<boolean> {
  return page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
}

/** 這一段裡看得到的那一份（桌機的表格或窄版的清單）。 */
function shown(section: Locator, text: string): Locator {
  return section.getByText(text, { exact: true }).locator('visible=true')
}

test('追更：停滯說成「下載停滯」、斷更很久預設收起、沒接 Discord 時頁首有提示', async ({
  page,
}) => {
  await signIn(page, '/schedule/tracking')
  await expect(page.getByRole('heading', { level: 1, name: '追更' })).toBeVisible()
  const tabs = page.getByRole('navigation', { name: '新番' })
  await expect(tabs.getByRole('link', { name: '追更' })).toHaveAttribute('aria-current', 'page')
  await expect(tabs.getByRole('link', { name: '時間表' })).not.toHaveAttribute('aria-current')

  const hint = page.getByText('遲到只會顯示在這裡，不會通知你。')
  await expect(hint).toBeVisible()
  await expect(page.getByRole('link', { name: '到通知設定' })).toHaveAttribute(
    'href',
    '/settings/notifications',
  )

  const action = page.getByRole('region', { name: '要你動手' })
  await expect(shown(action, '藥師少女的獨語')).toBeVisible()
  await expect(shown(action, '晚 4 天')).toBeVisible()
  await expect(shown(action, '下載停滯')).toBeVisible()
  await expect(shown(action, '下載中')).toHaveCount(0)
  await expect(
    action.getByRole('link', { name: '看這筆下載' }).locator('visible=true'),
  ).toHaveAttribute('href', /^\/jobs\/[0-9a-f]{40}$/)

  const onTime = page.getByRole('region', { name: '準時' })
  await expect(shown(onTime, '葬送的芙莉蓮')).toBeVisible()
  await expect(shown(onTime, '跟上了')).toBeVisible()

  const dormant = page.getByRole('region', { name: '斷更很久' })
  await expect(dormant.getByText('斷了很久的番')).toHaveCount(0)
  expect(await fitsWidth(page)).toBe(true)
  await shot(page, '1-tracking')

  await dormant.getByText('斷更很久', { exact: true }).click()
  await expect(shown(dormant, '斷了很久的番')).toBeVisible()
  await expect(shown(dormant, '字幕組還沒發')).toBeVisible()
  expect(await fitsWidth(page)).toBe(true)
  await shot(page, '2-dormant-open')
})

test('一般使用者：打開追更被導走，分頁列沒有追更，API 403', async ({ page }) => {
  await signIn(page, '/schedule', CREW)
  const tabs = page.getByRole('navigation', { name: '新番' })
  await expect(tabs.getByRole('link')).toHaveCount(1)

  await page.goto('/schedule/tracking')
  await expect(page).toHaveURL(/\/health\?denied=true$/)
  expect((await page.request.get('/api/schedule/tracking')).status()).toBe(403)
  await shot(page, '3-crew-denied')
})
