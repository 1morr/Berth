import { expect, test } from '@playwright/test'

import { signIn } from './login.ts'
import { shot } from './shot.ts'

// 新搜尋 feed 的第一輪預覽（M3 票 11），`rss` 情境。acg.rip 的搜尋 feed 是票 07 錄下來的那一份：
// 《上伊那牡丹》30 筆，8 筆是合集。第一輪停在頁首的「等你決定」，一筆都不送；合集在「排除」那一組；
// 選「只追之後的」之後那一塊消失，整份歷史在 Feed Item 清單上是「略過」。
test('新 acg.rip feed：預覽看得到合集被排除，只追之後的略過整份歷史', async ({ page }) => {
  await signIn(page, '/rss')

  await page.getByLabel(/RSS 網址/).fill('https://acg.rip/.xml?term=Kamiina+Botan')
  await page.getByRole('button', { name: '加入', exact: true }).click()
  const feed = page.getByRole('region', { name: /^Feed/ }).getByRole('article', { name: 'acg.rip' })
  await expect(feed).toContainText('第一輪還沒決定，一筆都不送')
  const first = page.getByRole('region', { name: /等你決定/ })
  await expect(first).toContainText('第一輪還沒輪到')

  await feed.getByRole('button', { name: '立即輪詢' }).click()
  await expect(feed.getByRole('status')).toContainText('新 30 筆')
  await expect(feed.getByRole('status')).toContainText('送出 0 筆')
  const block = first.getByRole('article', { name: 'acg.rip' })
  await expect(block).toContainText('會送出 0')
  await expect(block).toContainText('綁定之後送 22')
  await expect(block).toContainText('排除 8')
  await shot(page, '1-preview')

  await block.getByRole('button', { name: '看排除（8 筆）' }).click()
  await expect(block.getByText(/不是單集/)).toHaveCount(8)
  await expect(block).toContainText('[01-12 合集]')
  await expect(block).toContainText('[第01-12話]')
  await shot(page, '2-excluded')

  await block.getByRole('button', { name: '只追之後的' }).click()
  await expect(page.getByRole('region', { name: /等你決定/ })).toHaveCount(0)
  await expect(feed).not.toContainText('第一輪還沒決定')
  const items = page.getByRole('region', { name: '最近的 Feed Item' })
  await expect(items.getByText('略過', { exact: true })).toHaveCount(22)
  await expect(items.getByText('已排除', { exact: true })).toHaveCount(8)
  await shot(page, '3-passed')
})
