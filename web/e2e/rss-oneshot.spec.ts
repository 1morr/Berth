import { expect, test } from '@playwright/test'

import { signIn } from './login.ts'
import { shot } from './shot.ts'

// 一次性 RSS 連結（M3 票 18），`rss` 情境：喵萌奶茶屋&LoliHouse《与你相恋》的單一 feed 是 01–12。
// 讀一次、選作品與 Route、勾三集 → `/jobs` 上三筆手動送單；/rss 上不長出任何 Feed。
test('Mikan 單一 feed：列出整季，勾三集就是三筆下載，不建 Feed', async ({ page }) => {
  await signIn(page, '/rss')

  const region = page.getByRole('region', { name: '一次性 RSS 連結' })
  await region
    .getByLabel(/要讀的網址/)
    .fill('https://mikanani.me/RSS/Bangumi?bangumiId=4009&subgroupid=370')
  await region.getByRole('button', { name: '讀取' }).click()
  const list = region.getByRole('list', { name: '勾選要送出的' })
  await expect(list.getByRole('checkbox')).toHaveCount(12)
  await expect(region).toContainText('讀到 12 筆')
  await shot(page, '1-read')

  await region.getByRole('button', { name: /與妳相戀到生命盡頭/ }).click()
  // TV 與 Anime 都收劇集，從沒送過單：留給人選。
  await region.getByRole('combobox', { name: '入庫到' }).selectOption('Anime')
  // 清單照那部作品重讀：季集換算成 S01Exx。
  await expect(list).toContainText('S01E05')
  for (const episode of ['01', '02', '03']) {
    // 字串是子字串比對：` - 01 [WebRip` 只配得到第 1 集。
    await list.getByRole('checkbox', { name: ` - ${episode} [WebRip` }).check()
  }
  await shot(page, '2-picked')
  await region.getByRole('button', { name: '送出 3 筆' }).click()
  await expect(region.getByRole('status')).toHaveText('送出 3 筆；0 筆本來就在了；0 筆沒有送出。')
  await expect(list.getByText('已送出', { exact: true })).toHaveCount(3)
  await shot(page, '3-sent')

  // 不建 Feed：Feed 段仍是空狀態，最近的 Feed Item 那一段不出現。
  await expect(page.getByRole('region', { name: /^Feed/ })).toContainText('還沒有 Feed')
  await expect(page.getByRole('region', { name: '最近的 Feed Item' })).toHaveCount(0)

  await page.goto('/jobs')
  const jobs = page.getByRole('listitem').filter({ hasText: 'Kimi ga Shinu made Koi wo Shitai' })
  await expect(jobs).toHaveCount(3)
  await shot(page, '4-jobs')
})

// 合集照樣勾得了（排除條件只管自動下載）；讀不到、認不出的各說各的。
test('acg.rip 搜尋 feed 標出合集；認不出與讀不到說得出是哪一種', async ({ page }) => {
  await signIn(page, '/rss')

  const region = page.getByRole('region', { name: '一次性 RSS 連結' })
  const field = region.getByLabel(/要讀的網址/)
  await field.fill('https://example.com/rss')
  await region.getByRole('button', { name: '讀取' }).click()
  await expect(region).toContainText('認不得這個網址')

  await field.fill('https://nyaa.si/?page=rss&q=nothing')
  await region.getByRole('button', { name: '讀取' }).click()
  await expect(region).toContainText('現在讀不到這個網址')
  await shot(page, '1-unreachable')

  await field.fill('https://acg.rip/.xml?term=Kamiina+Botan')
  await region.getByRole('button', { name: '讀取' }).click()
  const list = region.getByRole('list', { name: '勾選要送出的' })
  await expect(list.getByRole('checkbox')).toHaveCount(30)
  await expect(list.getByText('合集', { exact: true }).first()).toBeVisible()
  const batch = list.getByRole('checkbox', { name: /01-12 合集/ }).first()
  await batch.check()
  await expect(batch).toBeChecked()
  await shot(page, '2-collection')
})
