import { expect, test } from '@playwright/test'

import { ADMIN } from './login.ts'
import { shot } from './shot.ts'

// `starting`：四個容器同時起來（票 06g 量到的時間線，照測試次數演）。Jellyfin 先回不像它自己的
// 東西、再回兩次 503，qBittorrent 第一次連不上，Prowlarr 連不上五次。選了套件內之後照常每 3 秒
// 重測到它起來——**全程不按「重新測試」**，使用者也不必按（票 06h 的冷啟動閘門，瀏覽器這一層；
// M4 票 15 起不偵測，選了才測）。
test('冷啟動：服務還在啟動時選套件內，不按重新測試就連上', async ({ page }) => {
  let retestsByHand = 0
  let probesBeforeChoosing = 0
  let chosen = false
  page.on('request', (request) => {
    const url = request.url()
    if (request.method() === 'POST' && /\/api\/setup\/services\/[a-z]+$/.test(url)) chosen = true
    if (/\/api\/setup\/services\/[a-z]+\/test$/.test(url) || /qbittorrent\/diff$/.test(url)) {
      if (!chosen) probesBeforeChoosing += 1
      if (JSON.parse(request.postData() ?? '{}').restart) retestsByHand += 1
    }
  })
  await page.goto('/')
  // 精靈的頁在網址上（M4 票 30）：讀回狀態之後補上 `?step=1`。
  await expect(page).toHaveURL(/\/setup(\?step=1)?$/)

  // 1. 還沒選：一個請求都不發，也沒有帳密表單。
  await expect(page.getByRole('heading', { name: '先選 Jellyfin 是哪一台' })).toBeVisible()
  await expect(page.getByRole('textbox', { name: 'Jellyfin 帳號' })).toHaveCount(0)
  expect(probesBeforeChoosing).toBe(0)

  // 選了套件內：Jellyfin 還在啟動，那一條說啟動中與倒數，帳密表單等它起來才出現。
  await page.getByRole('radio', { name: /套件內/ }).click()
  await expect(page.getByText('啟動中').first()).toBeVisible()
  await expect(page.getByText(/還在啟動/)).toBeVisible()
  await shot(page, '1-starting')
  await expect(page.getByRole('heading', { name: '建立 Jellyfin 管理員' })).toBeVisible({
    timeout: 60_000,
  })
  await page.getByRole('textbox', { name: 'Jellyfin 帳號' }).fill(ADMIN.user)
  await page.getByRole('textbox', { name: '密碼', exact: true }).fill(ADMIN.password)
  await page.getByRole('textbox', { name: '再輸入一次密碼' }).fill(ADMIN.password)
  await page.getByRole('button', { name: '建立管理員並登入' }).click()
  await page.getByRole('button', { name: '前往下一個泊位' }).click()

  // 2. qBittorrent 第一次連不上：說成啟動中，不是失敗、不是既有；起來之後給偏好的差異。
  await expect(page.getByRole('heading', { name: '先選 qBittorrent 是哪一台' })).toBeVisible()
  await page.getByRole('radio', { name: /套件內/ }).click()
  await expect(page.getByRole('heading', { name: '套用建議的 qBittorrent 設定' })).toBeVisible({
    timeout: 60_000,
  })
  await expect(page.getByText('連上了').first()).toBeVisible()
  await shot(page, '2-connected')
  expect(retestsByHand).toBe(0)
})
