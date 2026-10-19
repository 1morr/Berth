import { expect, test } from '@playwright/test'

import { signIn } from './login.ts'
import { shot } from './shot.ts'

// 作品頁的「只下載現有的」（M4 票 112），`rss` 情境：《与你相恋到生命尽头》的 Nix-Raws 只出了一筆
// 01–12 合集。先照舊訂閱：合集被全域的「不自動下載合集」擋下，回報說出筆數與理由、指向「只下載
// 現有的」；從那裡勾合集送出，是一般的手動送單，Feed 只有訂閱建的那一條。
const DETAIL = '/media/tv:262000'
const BATCH = /\[Nix-Raws\].*01-12 合集/

test('只出合集的字幕組：訂閱說出擋下的，再從「只下載現有的」送出合集', async ({ page }) => {
  await signIn(page, DETAIL)
  const block = page.getByRole('region', { name: 'RSS 訂閱' })

  await block.getByRole('button', { name: '新增訂閱' }).click()
  await block.getByRole('button', { name: '与你相恋到生命尽头' }).click()
  await block.getByRole('button', { name: /Nix-Raws/ }).click()
  await block.getByRole('combobox', { name: '入庫到' }).selectOption('Anime')
  await expect(block.getByRole('button', { name: '只下載現有的' })).toBeVisible()
  await shot(page, '1-picked')
  await block.getByRole('button', { name: '訂閱並送出' }).click()

  await expect(
    block.getByText(
      '已訂閱，送出 0 集。1 筆是合集、區間或季包，沒有自動下載。要下載，用「只下載現有的」。',
    ),
  ).toBeVisible()
  await block.getByRole('button', { name: '只下載現有的' }).click()
  const list = block.getByRole('list', { name: '勾選要送出的' })
  await expect(list.getByText('合集', { exact: true })).toBeVisible()
  // 作品與 Route 帶好了：資料夾名就在送出鍵上方，不必再選作品。
  await expect(
    block.getByText('Kimi ga Shinu made Koi wo Shitai (2026) [tmdbid-262000]'),
  ).toBeVisible()
  await list.getByRole('checkbox', { name: BATCH }).check()
  await shot(page, '2-existing-picked')
  await block.getByRole('button', { name: '送出 1 筆' }).click()

  await expect(block.getByText('送出 1 筆；0 筆本來就在了；0 筆沒有送出。')).toBeVisible()
  await expect(list.getByText('已送出')).toBeVisible()
  await shot(page, '3-existing-sent')

  await page.goto('/jobs?filter=all')
  await expect(page.getByRole('listitem').filter({ hasText: 'Nix-Raws' })).toHaveCount(1)
  // 只有訂閱建的那一條 Feed；一次性下載沒有加。
  const feeds = await (await page.request.get('/api/rss/feeds')).json()
  expect(feeds.map((feed: { name: string }) => feed.name)).toEqual([
    '与你相恋到生命尽头 · Nix-Raws',
  ])
})
