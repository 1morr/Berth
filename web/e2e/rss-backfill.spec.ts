import { expect, test } from '@playwright/test'

import { signIn } from './login.ts'
import { shot } from './shot.ts'

// 補舊集（M3 票 12），`rss` 情境：聚合 feed 裡《与你相恋》喵萌奶茶屋&LoliHouse 只剩 11、12 兩集，
// 單一 feed 是 01–12。綁定時預設勾選補舊集，聚合 feed 沒帶到的 01–10 一起送——整季 12 集進下載列表。
test('中途訂閱的一部：綁定時預設補舊集，整季都進下載列表', async ({ page }) => {
  await signIn(page, '/rss')

  await page.getByLabel(/RSS 網址/).fill('https://mikanani.me/RSS/MyBangumi?token=REDACTED')
  await page.getByRole('button', { name: '加入', exact: true }).click()
  const feed = page.getByRole('article', { name: 'mikanani.me' })
  await feed.getByRole('button', { name: '立即輪詢' }).click()
  await expect(feed.getByRole('status')).toContainText('新 12 筆')

  const pending = page.getByRole('region', { name: '待綁定' })
  const row = pending.getByRole('article', { name: /与你相恋到生命尽头/ })
  await row.getByRole('button', { name: /選《與妳相戀到生命盡頭》/ }).click()
  await row.getByRole('combobox', { name: '入庫到' }).selectOption('Anime')
  // 補幾集要讀了單一 feed 才知道：鍵上只說聚合 feed 帶到的兩集「並補舊集」。
  const backfill = row.getByRole('checkbox', { name: '同時補下載舊集' })
  await expect(backfill).toBeChecked()
  await expect(backfill).toHaveAccessibleDescription(/Feed 沒帶到的集數一起送出/)
  await shot(page, '1-backfill')
  await row.getByRole('button', { name: '綁定、送出 2 集並補舊集' }).click()
  await expect(pending).toContainText('10 個待綁定')
  await expect(page.getByText('綁好了，送出 12 集。')).toBeAttached()

  // 補下來的寫成聚合 Feed 的 Item：最近的 Feed Item 裡 01–12 都送出去了。
  const items = page.getByRole('region', { name: '最近的 Feed Item' })
  await expect(items.getByRole('link', { name: '看這一筆下載' })).toHaveCount(12)
  await shot(page, '2-bound')

  await page.goto('/jobs')
  const jobs = page.getByRole('listitem').filter({ hasText: 'Kimi ga Shinu made Koi wo Shitai' })
  await expect(jobs).toHaveCount(12)
  await expect(jobs.first()).toContainText('RSS')
  await shot(page, '3-jobs')
})
