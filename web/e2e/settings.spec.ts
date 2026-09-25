import { expect, test } from '@playwright/test'

import { signIn } from './login.ts'
import { shot } from './shot.ts'

// `healthy`：精靈已經跑完。之後的修改在設定頁（票 06i）：`/setup` 把 admin 導去那裡，
// 索引站那一頁加站並試搜，TMDB 那一頁換一把 key（替身認得任何一把）。
test('精靈跑完之後：/setup 導向設定頁，加一個索引站並試搜、換 TMDB key', async ({ page }) => {
  await signIn(page, '/jobs')
  await page.goto('/setup')
  await expect(page).toHaveURL(/\/settings\//)

  await page.goto('/settings/indexers')
  const main = page.getByRole('main')
  await expect(main.getByRole('heading', { name: '索引站設定' })).toBeVisible()
  await main.getByRole('checkbox', { name: /YTS/ }).check()
  await main.getByRole('button', { name: '加入這 2 個站' }).click()
  await main.getByRole('button', { name: '試搜' }).click()
  const yts = page.getByTestId('trial').getByRole('listitem').filter({ hasText: 'YTS' }).first()
  await expect(yts.getByText(/\d+ 筆/)).toBeVisible()
  await shot(page, 'indexers')

  await page.goto('/settings/tmdb')
  await main.getByRole('textbox', { name: '你的 TMDB API key' }).fill('0'.repeat(31) + '2')
  await main.getByRole('button', { name: '測試 TMDB' }).click()
  await expect(main.getByText('驗證憑證')).toBeVisible()
  await expect(main.getByText('已完成')).toBeVisible()
  await shot(page, 'tmdb')
})
