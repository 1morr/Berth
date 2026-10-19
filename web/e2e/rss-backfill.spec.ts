import { expect, test } from '@playwright/test'

import { signIn } from './login.ts'
import { shot } from './shot.ts'

// 補舊集（M3 票 12），`rss-legacy-feed` 情境：聚合 feed 裡《与你相恋》喵萌奶茶屋&LoliHouse 只剩 11、12
// 兩集，單一 feed 是 01–12。綁定一律補舊集（M4 票 78），聚合 feed 沒帶到的 01–10 一起送——整季 12 集進
// 下載列表。走手動綁定：這個 Feed 是票 105 之前加的、劇集那一格空著，認出來的那一部停在待綁定、作品
// 預填成候選（加 Feed 時選了 Route 的話它會自動綁上，見 `rss.spec.ts`）。
test('中途訂閱的一部：綁定時補舊集，整季都進下載列表', async ({ page }) => {
  await signIn(page, '/rss')

  const feed = page.getByRole('article', { name: 'mikanani.me' })
  // 背景迴圈可能先輪到它（Feed 一開始就在）：不看這一輪新幾筆，看待綁定裡有沒有那一部。
  await feed.getByRole('button', { name: '立即輪詢' }).click()
  const pending = page.getByRole('region', { name: '待綁定' })
  await expect(pending).toContainText('11 個待綁定')
  const row = pending.getByRole('article', { name: /与你相恋到生命尽头/ })
  await row.getByRole('button', { name: /選《與妳相戀到生命盡頭》/ }).click()
  await row.getByRole('combobox', { name: '入庫到' }).selectOption('Anime')
  // 補幾集要讀了單一 feed 才知道：確認區說整季，鍵上不寫數字。
  await expect(row.getByText(/Feed 沒帶到的集數一起送出/)).toBeVisible()
  await expect(row.getByRole('checkbox')).toHaveCount(0)
  await shot(page, '1-backfill')
  await row.getByRole('button', { name: '綁定並送出' }).click()
  await expect(pending).toContainText('10 個待綁定')
  await expect(page.getByText('綁好了，送出 12 集。')).toBeAttached()

  // 補下來的寫成聚合 Feed 的 Item：最近的 Feed Item 裡 01–12 都送出去了。
  const items = page.getByRole('region', { name: '最近的 Feed Item' })
  await expect(items.getByRole('link', { name: '看這一筆下載' })).toHaveCount(12)
  // 補漏看得見（M4 票 108）：段落說明每天補什麼，那一列說上次補漏是什麼時候。
  const series = page.getByRole('region', { name: /RSS Series/ })
  await expect(series.getByText(/每天再讀一次它在 Mikan 上的整季清單/)).toBeVisible()
  await expect(series.getByRole('article', { name: /LoliHouse/ })).toContainText('上次補漏：')
  await shot(page, '2-bound')

  // 入庫了的不在預設的「在路上」（M4 票 04）：看全部。
  await page.goto('/jobs?filter=all')
  const jobs = page.getByRole('listitem').filter({ hasText: 'Kimi ga Shinu made Koi wo Shitai' })
  await expect(jobs).toHaveCount(12)
  await expect(jobs.first()).toContainText('RSS')
  await shot(page, '3-jobs')
})
