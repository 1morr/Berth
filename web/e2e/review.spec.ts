import { expect, test } from '@playwright/test'

import { signIn } from './login.ts'

// `review`：SPY×FAMILY 第二季兩集同一筆下載、以 medium 信心自動入庫、掛著 audit（M2 票 06）。
// 同一個 Job 的 audit 收成一組、一顆「全部確認」（M3 票 05）：收起時就說得出為什麼是 medium，
// 按下去整組從佇列上消失，重新整理也不回來——旗標真的在資料庫裡清掉了。
test('/review 一組 audit 全部確認', async ({ page }) => {
  await signIn(page, '/review')

  const audited = page.getByRole('region', { name: /^已入庫，等你看一眼/ })
  const group = audited
    .getByRole('listitem')
    .filter({
      has: page.getByRole('heading', { level: 3, name: 'SPY×FAMILY 間諜家家酒', exact: true }),
    })
  await expect(group).toContainText('2 個檔案，信心 medium：集號是換算的（各季集數累加）')

  await group.getByText('展開').first().click()
  await expect(group.getByRole('heading', { level: 4 })).toHaveText(['S02E01', 'S02E02'])

  await group.getByRole('button', { name: '全部確認' }).click()

  await expect(page.getByText('已確認 2 個，從佇列上收掉了。')).toBeVisible()
  await expect(group).toHaveCount(0)

  await page.reload()
  await expect(page.getByRole('heading', { level: 1, name: '審核' })).toBeVisible()
  await expect(audited.getByText('待確認', { exact: true })).toHaveCount(0)
})
