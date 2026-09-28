import { expect, test } from '@playwright/test'

import { ADMIN } from './login.ts'
import { shot } from './shot.ts'

// `starting`：四個容器同時起來（票 06g 量到的時間線，照探測次數演）。Jellyfin 先回不像它自己的
// 東西、再回兩次 503，qBittorrent 第一次連不上，Prowlarr 連不上五次。第 1 步照常輪詢到 Jellyfin
// 起來才給表單，第 2 步照常輪詢到兩個都判定完成——**全程不按「重新探測」**，使用者也不必按
// （票 06h 的冷啟動閘門，瀏覽器這一層；M4 票 06 起 Jellyfin 在第 1 步）。
test('冷啟動：服務還在啟動時開始精靈，不按重新探測就判定完成', async ({ page }) => {
  let redetects = 0
  page.on('request', (request) => {
    if (request.method() === 'POST' && /\/api\/setup\/detect$/.test(request.url())) {
      if (JSON.parse(request.postData() ?? '{}').restart) redetects += 1
    }
  })
  await page.goto('/')
  await expect(page).toHaveURL('/setup')

  // 1. Jellyfin 還在啟動：那一條纜繩說探測中，帳密表單等它起來才出現。
  const jellyfin = page.getByRole('main').getByRole('list').first()
  await expect(jellyfin.getByText('探測中').first()).toBeVisible()
  await expect(page.getByRole('textbox', { name: 'Jellyfin 帳號' })).toHaveCount(0)
  await shot(page, '1-starting')
  await expect(page.getByRole('heading', { name: '建立 Jellyfin 管理員' })).toBeVisible({
    timeout: 60_000,
  })
  await page.getByRole('textbox', { name: 'Jellyfin 帳號' }).fill(ADMIN.user)
  await page.getByRole('textbox', { name: '密碼', exact: true }).fill(ADMIN.password)
  await page.getByRole('textbox', { name: '再輸入一次密碼' }).fill(ADMIN.password)
  await page.getByRole('button', { name: '建立管理員並登入' }).click()
  await page.getByRole('button', { name: '前往下一個泊位' }).click()

  // 2. 其餘兩個：啟動中的樣子說成探測中，不是失敗、不是既有。
  const detect = page.waitForRequest('**/api/setup/detect')
  await page.getByRole('button', { name: '開始探測' }).click()
  await detect
  const services = page.getByRole('main').getByRole('list').first()
  await expect(services.getByText('探測中').first()).toBeVisible()
  await expect(services.getByText(/還在啟動/)).toBeVisible()
  await shot(page, '2-starting')

  await expect(page.getByText('2 個服務已判定')).toBeVisible({ timeout: 60_000 })
  await expect(services.getByText('套件內')).toHaveCount(2)
  await shot(page, '2-detected')
  expect(redetects).toBe(0)
  await page.getByRole('button', { name: '前往泊位 1' }).click()
  await expect(page.getByRole('heading', { name: '接手這台 Jellyfin' })).toBeVisible()
})
