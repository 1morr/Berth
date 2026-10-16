import { expect, test } from '@playwright/test'

import { signIn } from './login.ts'
import { shot } from './shot.ts'

// `rss-legacy-feed`（M4 票 105）：同 `rss`，但聚合 feed 是票 105 之前加的——TV 與 Anime 兩條都收劇集，
// migration 推不出劇集那一格。Feed 列標「要選 Route」；輪詢之後那一部認出來了、停在待綁定
// （`route_ambiguous`）。按「改 Route」選 Anime：確認區說會當場綁上 1 部，存下之後它不經人手綁上、
// 補齊整季，下載列表上有它的集數。
test('舊 Feed 沒有 Route → 改 Route → 當場綁上 → 下載列表上有它', async ({ page }) => {
  await signIn(page, '/rss')

  const feed = page.getByRole('article', { name: 'mikanani.me' })
  await expect(feed.getByText('要選 Route')).toBeVisible()
  await expect(feed).toContainText('沒說劇集送進哪一條')
  await expect(feed).toContainText('電影送進 Movies')
  await shot(page, '1-unset')

  // 背景迴圈可能先輪到它（Feed 一開始就在）：這一輪新幾筆不一定，自動綁定一定是 0。
  await feed.getByRole('button', { name: '立即輪詢' }).click()
  await expect(feed.getByRole('status')).toContainText('（自動綁定 0 個）、送出 0 筆')
  const pending = page.getByRole('region', { name: '待綁定' })
  await expect(pending).toContainText('11 個待綁定')
  await expect(pending.getByRole('article', { name: /与你相恋到生命尽头/ })).toContainText(
    '作品認出來了，但 Anime, TV 都收得下它',
  )

  await feed.getByRole('button', { name: '改 Route' }).click()
  const panel = feed.getByRole('group', { name: /自動綁定到這裡/ })
  await expect(panel).toContainText('停在待綁定的 1 部會當場綁上')
  await expect(panel.getByRole('combobox', { name: '電影送進' })).toHaveValue(/\d+/)
  await panel.getByRole('combobox', { name: '劇集送進' }).selectOption('Anime')
  await shot(page, '2-change-routes')
  await panel.getByRole('button', { name: '存下並綁上 1 部' }).click()

  // 綁定照預設補舊集（brief §15）：聚合 feed 帶到的兩集之外，番組的單一 feed 補齊整季 12 集。
  await expect(feed.getByText('存下了：當場綁上 1 部、送出 12 筆。')).toBeVisible()
  await expect(feed.getByText('要選 Route')).toHaveCount(0)
  await expect(feed).toContainText('劇集送進 Anime')
  await expect(pending).toContainText('10 個待綁定')
  const bound = page
    .getByRole('region', { name: 'RSS Series' })
    .getByRole('article', { name: '與妳相戀到生命盡頭' })
  await expect(bound.locator('header')).toContainText('Anime')
  await bound.getByRole('article', { name: 'LoliHouse' }).locator('summary').click()
  // 依據換成 Feed 挑的 Route；「不只一條都收得下」那一句不再是它的理由。
  await expect(bound.getByText('這個 Feed 設定送進 Anime')).toBeVisible()
  await expect(bound.getByText(/都收得下它/)).toHaveCount(0)
  await shot(page, '3-bound')

  // 入庫了的不在預設的「在路上」（M4 票 04）：看全部。
  await page.goto('/jobs?filter=all')
  const jobs = page.getByRole('listitem').filter({ hasText: 'Kimi ga Shinu made Koi wo Shitai' })
  await expect(jobs).toHaveCount(12)
  await expect(jobs.first()).toContainText('RSS')
  await expect(jobs.first()).toContainText('已入庫', { timeout: 60_000 })
  await shot(page, '4-jobs')
})
