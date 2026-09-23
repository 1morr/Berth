import { expect, test } from '@playwright/test'

import { ADMIN, signIn } from './login.ts'

// `bundled`：乾淨的 compose，三個服務都判為套件內（plan §9.3）。八步走完、關掉精靈，
// 再以第 1 步那組帳密登入——那組帳密是精靈第 3 步替 Jellyfin 建的管理員。
test('精靈八步走完，之後以同一組帳密登入', async ({ page }) => {
  await page.goto('/')
  await expect(page).toHaveURL('/setup')

  // 1. 管理員
  await page.getByRole('textbox', { name: '帳號' }).fill(ADMIN.user)
  await page.getByRole('textbox', { name: '密碼' }).fill(ADMIN.password)
  await page.getByRole('button', { name: '建立管理員' }).click()

  // 2. 偵測服務：三個都是套件內，畫面停在第 2 步等人按「前往泊位 1」。
  await page.getByRole('button', { name: '開始探測' }).click()
  await page.getByRole('button', { name: '前往泊位 1' }).click()
  await expect(page.getByText('3 個服務已判定')).toBeVisible()

  // 3. Jellyfin 全自動接手
  await expect(page.getByRole('heading', { name: '接手這台 Jellyfin' })).toBeVisible()
  await page.getByRole('button', { name: '開始靠泊' }).click()

  // 4. qBittorrent
  await expect(page.getByRole('heading', { name: '套用建議的 qBittorrent 設定' })).toBeVisible()
  await page.getByRole('button', { name: /^套用這 \d+ 個鍵$/ }).click()

  // 5 / 6. 索引站（十個裡有五個連不上是常態）與 TMDB（替身認得任何一把 key）
  await expect(page.getByRole('heading', { name: '接上抓取來源' })).toBeVisible()
  await page.getByRole('button', { name: '加入這 10 個站' }).click()
  await page.getByRole('textbox', { name: '你的 TMDB API key' }).fill('0'.repeat(31) + '1')
  await page.getByRole('button', { name: '測試 TMDB' }).click()

  // 7. 三個媒體庫各成一條 Route。後端要每一條的五條纜繩都綠才把步驟推到 8（plan §9.3），
  //    所以下面看得到「完成設定」就是全綠。
  await page.getByRole('button', { name: '建立 3 條 Route 並檢查' }).click()

  // 8. 完成
  await expect(page.getByRole('heading', { name: '完成設定' })).toBeVisible()
  await expect(page.getByText('已繫上')).toHaveCount(3)
  await page.getByRole('button', { name: '完成設定' }).click()

  // 精靈關掉之後 `/` 要登入，不再導向精靈。
  await expect(page).toHaveURL(/\/login/)
  await signIn(page, '/jobs')
  await expect(page.getByRole('heading', { name: '下載', level: 1 })).toBeVisible()
  await page.goto('/')
  await expect(page).toHaveURL('/')
})
