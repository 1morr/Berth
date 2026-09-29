import { expect, test } from '@playwright/test'

import { signIn } from './login.ts'
import { shot } from './shot.ts'

// `healthy`：精靈已經跑完。之後的修改在設定頁（票 06i）：`/setup` 把 admin 導去那裡，
// 索引站那一頁加站並試搜、改 Prowlarr 的介面登入（自設一組），qBittorrent 那一頁改 WebUI 登入（沿用
// Jellyfin 帳密），
// TMDB 那一頁換一把 key（替身認得任何一把）。
test('精靈跑完之後：/setup 導向設定頁，加一個索引站並試搜、改兩個介面登入、換 TMDB key', async ({
  page,
}) => {
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

  // 套件內 Prowlarr 的介面登入在它自己的一區改（M4 票 07）：只換登入，說出舊的那一組不能再用。
  // 預設沿用 Jellyfin 帳密（M4 票 15）；這裡取消勾選、自己設一組。
  const login = main.getByRole('region', { name: '介面登入' })
  await login.getByRole('checkbox', { name: /沿用 Jellyfin 帳密/ }).uncheck()
  await login.getByRole('textbox', { name: '帳號' }).fill('deckhand')
  await login.getByLabel('密碼', { exact: true }).fill('changed-login')
  await login.getByLabel('再輸入一次密碼').fill('changed-login')
  await login.getByRole('button', { name: '更新登入' }).click()
  await expect(login.getByText(/之後用 deckhand 登入，舊的那一組不能再用/)).toBeVisible()
  await shot(page, 'indexer-login')

  // qBittorrent 那一區沿用 Jellyfin 帳密：帳號是擁有者、密碼打一次，Berth 先向 Jellyfin 驗過。
  await page.goto('/settings/qbittorrent')
  const webUi = main.getByRole('region', { name: '介面登入' })
  await expect(webUi.getByRole('checkbox', { name: /沿用 Jellyfin 帳密/ })).toBeChecked()
  await webUi.getByLabel('skipper 的 Jellyfin 密碼').fill('harbour')
  await webUi.getByRole('button', { name: '更新登入' }).click()
  await expect(webUi.getByText(/之後用 skipper 登入，舊的那一組不能再用/)).toBeVisible()
  await shot(page, 'qbittorrent-login')

  await page.goto('/settings/tmdb')
  await main.getByRole('textbox', { name: '你的 TMDB API key' }).fill('0'.repeat(31) + '2')
  await main.getByRole('button', { name: '測試 TMDB' }).click()
  await expect(main.getByText('驗證憑證')).toBeVisible()
  await expect(main.getByText('已完成')).toBeVisible()
  await shot(page, 'tmdb')
})
