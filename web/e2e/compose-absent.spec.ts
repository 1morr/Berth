import { expect, test } from '@playwright/test'

import { shot } from './shot.ts'

// `berth-only`：只有 Berth（`COMPOSE_PROFILES=`，M4 票 30、brief §19 2026-10-01 的決定）。進頁只查主機名、
// 不對服務發請求；「套件內」照常列出，卡片說它沒在跑、給起回來的兩種補法（票 35），不預選、不停用。
test('只有 Berth：頁 1 的套件內卡片說 Jellyfin 沒在跑，照樣選得到', async ({ page }) => {
  const probed: string[] = []
  page.on('request', (request) => {
    if (/\/api\/setup\/services\//.test(request.url())) probed.push(request.url())
  })
  await page.goto('/')

  const bundled = page.getByRole('radio', { name: /^套件內/ })
  await expect(page.getByText('這套 compose 的 Jellyfin 沒在跑。')).toBeVisible()
  await expect(bundled).toBeEnabled()
  await expect(bundled).not.toBeChecked()
  // 與選了之後的補法同一組（`bringBack`）：停了就 start；不在 COMPOSE_PROFILES 裡就加回去，還沒選的都算在套件內。
  await expect(page.getByText('docker compose start jellyfin', { exact: true })).toBeVisible()
  await expect(
    page.getByText('COMPOSE_PROFILES=jellyfin,qbittorrent,prowlarr', { exact: true }),
  ).toBeVisible()
  await expect(page.getByText('docker compose up -d', { exact: true })).toBeVisible()
  expect(probed).toEqual([])
  await page.screenshot({ path: test.info().outputPath('1-absent-viewport.png') })
  await shot(page, '1-absent')

  // 卡片仍可選：選了照舊測，紅的是「找不到這個名字的主機」，補法在那一條上、卡片下不再重複。
  await bundled.click()
  await expect(page.getByText('找不到這個名字的主機', { exact: true })).toBeVisible()
  await expect(
    page.getByText('COMPOSE_PROFILES=jellyfin,qbittorrent,prowlarr', { exact: true }),
  ).toHaveCount(1)
  await expect(page.getByText('docker compose start jellyfin', { exact: true })).toHaveCount(1)
  await shot(page, '1-absent-chosen')
})
