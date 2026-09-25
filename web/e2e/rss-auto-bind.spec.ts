import { expect, test } from '@playwright/test'

import { signIn } from './login.ts'
import { shot } from './shot.ts'

// `rss`（M3 票 21）：同 `rss.spec.ts` 那一份聚合 feed，但加 Feed 時說了「自動綁定送進 Anime」——
// 使用者拍板照 Sonarr Import List 的 Root Folder。TV 與 Anime 兩條 Route 都收劇集，所以沒選時那一部
// 留在待綁定（`rss.spec.ts`）；選了就不經人手：輪詢 → 自動綁定 → 下載列表上有它的集數。
test('加 Feed 時選 Route → 輪詢 → 那一部自動綁定 → 下載列表上有它', async ({ page }) => {
  await signIn(page, '/rss')

  await page.getByLabel(/RSS 網址/).fill('https://mikanani.me/RSS/MyBangumi?token=REDACTED')
  await page.getByLabel('自動綁定送進').selectOption('Anime')
  await page.getByRole('button', { name: '加入', exact: true }).click()
  const feed = page.getByRole('article', { name: 'mikanani.me' })
  await expect(feed).toContainText('自動綁定送進 Anime')

  await feed.getByRole('button', { name: '立即輪詢' }).click()
  // 綁定照預設補舊集（brief §15）：聚合 feed 帶到的兩集之外，番組的單一 feed 補齊整季 12 集。
  await expect(feed.getByRole('status')).toContainText('（自動綁定 1 個）、送出 12 筆')
  await expect(page.getByRole('region', { name: '待綁定' })).toContainText('10 個待綁定')
  const bound = page
    .getByRole('region', { name: 'RSS Series' })
    .getByRole('article', { name: '與妳相戀到生命盡頭' })
  await expect(bound).toContainText('入庫到 Anime')
  // 綁上的依據說出是 Feed 挑的 Route，不是「只有一條」。
  await expect(bound).toContainText('收得下它的 Route 不只一條，這個 Feed 設定送進 Anime')
  await shot(page, '1-bound')

  await page.goto('/jobs')
  const jobs = page.getByRole('listitem').filter({ hasText: 'Kimi ga Shinu made Koi wo Shitai' })
  await expect(jobs.first()).toContainText('RSS')
  await expect(jobs.first()).toContainText('已入庫', { timeout: 60_000 })
  await shot(page, '2-jobs')
})
