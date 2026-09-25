import { expect, test } from '@playwright/test'

import { signIn } from './login.ts'
import { shot } from './shot.ts'

// `rss`（M3 票 08）：同 `healthy`，加上 Mikan 與 TMDB 的替身，一個請求都不出網。聚合 feed 是票 07
// 錄下來的那一份，替身 qBittorrent 收下 torrent 就報成完成，之後的規劃與入庫是產品自己的程式碼。
// 票 09 起輪詢會自動綁定：那一部認得出來，但 TV 與 Anime 兩條 Route 都收劇集，所以留在待綁定、
// 作品預填成候選，這裡走「一鍵選定」那一條。
test('加 Feed → 輪詢 → 待綁定的那一部一鍵選定候選 → 下載列表上有它的兩集', async ({ page }) => {
  await signIn(page, '/rss')
  await shot(page, '1-empty')

  await page.getByLabel(/RSS 網址/).fill('https://mikanani.me/RSS/MyBangumi?token=REDACTED')
  await page.getByRole('button', { name: '加入', exact: true }).click()
  const feed = page.getByRole('article', { name: 'mikanani.me' })
  // token 就是憑證：畫面上只留前四碼。
  await expect(feed).toContainText('token=REDA…')

  await feed.getByRole('button', { name: '立即輪詢' }).click()
  await expect(feed.getByRole('status')).toHaveText(
    '這一輪：新 12 筆、長出 11 個 RSS Series（自動綁定 0 個）、送出 0 筆。',
  )
  const pending = page.getByRole('region', { name: '待綁定' })
  await expect(pending).toContainText('11 個待綁定')
  await shot(page, '2-polled')

  const row = pending.getByRole('article', { name: /与你相恋到生命尽头/ })
  // 為什麼沒自動綁：作品認出來了（同名、開播日期對得上），但兩條 Route 都收得下它。
  await expect(row).toContainText('沒有自動綁定：')
  await expect(row).toContainText('作品認出來了，但 Anime, TV 都收得下它')
  await row.getByRole('button', { name: /選《與妳相戀到生命盡頭》/ }).click()
  await expect(
    row.getByRole('list', { name: '候選' }).getByRole('button', { name: /與妳相戀到生命盡頭/ }),
  ).toHaveAttribute('aria-pressed', 'true')
  await row.getByRole('combobox', { name: '入庫到' }).selectOption('Anime')
  // 確認區塊重述會被寫死的資料夾名與要送出的集數。
  await expect(row).toContainText('Kimi ga Shinu made Koi wo Shitai (2026) [tmdbid-262000]')
  await shot(page, '3-binding')
  await row.getByRole('button', { name: '綁定並送出 2 集' }).click()
  await expect(pending).toContainText('10 個待綁定')
  await expect(page.getByRole('region', { name: 'RSS Series' })).toContainText('入庫到 Anime')

  await page.goto('/jobs')
  const jobs = page.getByRole('listitem').filter({ hasText: 'Kimi ga Shinu made Koi wo Shitai' })
  await expect(jobs).toHaveCount(2)
  await expect(jobs.first()).toContainText('RSS')
  await expect(jobs.first()).toContainText('已入庫', { timeout: 60_000 })
  await shot(page, '4-jobs')
})
