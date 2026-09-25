import { expect, test } from '@playwright/test'

import { ADMIN } from './login.ts'
import { shot } from './shot.ts'

// `starting`：四個容器同時起來（票 06g 量到的時間線，照探測次數演）。Jellyfin 先回不像它自己的
// 東西、再回兩次 503，qBittorrent 第一次連不上，Prowlarr 連不上五次。第 2 步照常輪詢到三個都
// 判定完成——**全程不按「重新探測」**，使用者也不必按（票 06h 的冷啟動閘門，瀏覽器這一層）。
test('冷啟動：服務還在啟動時開始精靈，不按重新探測就判定完成', async ({ page }) => {
  await page.goto('/')
  await expect(page).toHaveURL('/setup')
  await page.getByRole('textbox', { name: '帳號' }).fill(ADMIN.user)
  await page.getByRole('textbox', { name: '密碼' }).fill(ADMIN.password)
  await page.getByRole('button', { name: '建立管理員' }).click()

  const detect = page.waitForRequest('**/api/setup/detect')
  await page.getByRole('button', { name: '開始探測' }).click()
  await detect
  let redetects = 0
  page.on('request', (request) => {
    if (request.method() === 'POST' && /\/api\/setup\/detect$/.test(request.url())) {
      if (JSON.parse(request.postData() ?? '{}').restart) redetects += 1
    }
  })

  // 啟動中的兩種樣子都說成探測中，不是失敗、不是既有。
  const services = page.getByRole('main').getByRole('list').first()
  await expect(services.getByText('探測中').first()).toBeVisible()
  await expect(services.getByText(/還在啟動/)).toBeVisible()
  await shot(page, '2-starting')

  await expect(page.getByText('3 個服務已判定')).toBeVisible({ timeout: 60_000 })
  await expect(services.getByText('套件內')).toHaveCount(3)
  await shot(page, '2-detected')
  expect(redetects).toBe(0)
  await page.getByRole('button', { name: '前往泊位 1' }).click()
  await expect(page.getByRole('heading', { name: '接手這台 Jellyfin' })).toBeVisible()
})
