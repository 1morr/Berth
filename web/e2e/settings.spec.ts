import { expect, test } from '@playwright/test'

import { signIn } from './login.ts'
import { shot } from './shot.ts'

// `healthy`：精靈已經跑完。之後的修改在設定頁（票 06i）：`/setup` 把 admin 導去那裡，
// 索引站那一頁加站並試搜、改 Prowlarr 的介面登入（換帳號與密碼），qBittorrent 那一頁設 WebUI 登入
// （這個情境裡還沒設過），Jellyfin 那一頁的連線是唯讀摘要，TMDB 那一頁換一把 key（替身認得任何一把）。
test('精靈跑完之後：/setup 導向設定頁，加一個索引站並試搜、改兩個介面登入、換 TMDB key', async ({
  page,
}) => {
  await signIn(page, '/jobs')
  await page.goto('/setup')
  await expect(page).toHaveURL(/\/settings\//)

  // 進來只讀（M4 票 09）：不測任何一站、不送任何寫入。
  const writes: string[] = []
  page.on('request', (request) => {
    if (request.method() !== 'GET' && request.url().includes('/api/setup/')) {
      writes.push(request.url())
    }
  })
  await page.goto('/settings/indexers')
  const main = page.getByRole('main')
  await expect(main.getByRole('heading', { name: 'Prowlarr 設定' })).toBeVisible()
  await expect(main.getByTestId('added')).toBeVisible()
  await page.waitForLoadState('networkidle')
  expect(writes).toEqual([])
  await main.getByRole('button', { name: '測試 YTS' }).click()
  await main.getByRole('checkbox', { name: 'YTS' }).check()
  await main.getByRole('button', { name: '加入 1 個站' }).click()
  // 「搜尋全部」搜的是按下去那一刻已加入的站：加站回來之前按，YTS 那一列會停在「還沒搜」（M4 票 13c）。
  const yts = page.getByTestId('trial').getByRole('listitem').filter({ hasText: 'YTS' }).first()
  await expect(yts).toBeVisible()
  await main.getByRole('button', { name: '搜尋全部' }).click()
  await expect(yts.getByText(/\d+ 筆/)).toBeVisible()
  await shot(page, 'indexers')

  // 套件內 Prowlarr 的介面登入在它自己的一區改（M4 票 07）：只換登入，說出舊的那一組不能再用。
  // 一般的改帳密表單（M4 票 78）：沒有精靈的「沿用 Jellyfin 帳密」。
  const login = main.getByRole('region', { name: '介面登入' })
  await expect(login.getByRole('checkbox')).toHaveCount(0)
  await login.getByRole('textbox', { name: '帳號' }).fill('deckhand')
  await login.getByLabel('新密碼').fill('changed-login')
  await login.getByLabel('再輸入一次密碼').fill('changed-login')
  await login.getByRole('button', { name: '儲存' }).click()
  await expect(login.getByText(/之後用 deckhand 登入，舊的那一組不能再用/)).toBeVisible()
  await shot(page, 'indexer-login')

  // qBittorrent 那一區：這個情境裡還沒設過，帳號那一格是空的，同一張表單設一組。
  await page.goto('/settings/qbittorrent')
  const webUi = main.getByRole('region', { name: '介面登入' })
  await expect(main.getByText(/還沒有設過/)).toBeVisible()
  await webUi.getByRole('textbox', { name: '帳號' }).fill('skipper')
  await webUi.getByLabel('新密碼').fill('changed-login')
  await webUi.getByLabel('再輸入一次密碼').fill('changed-login')
  await webUi.getByRole('button', { name: '儲存' }).click()
  await expect(webUi.getByText(/之後用 skipper 登入，舊的那一組不能再用/)).toBeVisible()
  await shot(page, 'qbittorrent-login')

  // Jellyfin 的連線是唯讀摘要（M4 票 78）：套件內那一台沒有二選一、沒有表單。
  await page.goto('/settings/jellyfin')
  const connection = main.getByRole('region', { name: '連線' })
  await expect(connection.getByText('套件內', { exact: true })).toBeVisible()
  await expect(connection.getByRole('status')).toContainText('連上了')
  await expect(connection.getByRole('radio')).toHaveCount(0)
  await shot(page, 'jellyfin-connection')

  await page.goto('/settings/tmdb')
  await main.getByRole('textbox', { name: '你的 TMDB API key' }).fill('0'.repeat(31) + '2')
  await main.getByRole('button', { name: '測試 TMDB' }).click()
  await expect(main.getByText('驗證憑證')).toBeVisible()
  await expect(main.getByText('已完成')).toBeVisible()
  await shot(page, 'tmdb')
})
