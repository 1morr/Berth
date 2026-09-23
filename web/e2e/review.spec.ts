import { expect, test } from '@playwright/test'

import { signIn } from './login.ts'

// `review`：SPY×FAMILY 第二季兩集以 medium 信心自動入庫、掛著 audit（M2 票 06）。
// 確認之後那一列從佇列上消失，重新整理也不回來——旗標真的在資料庫裡清掉了。
test('/review 確認一筆 audit', async ({ page }) => {
  await signIn(page, '/review')

  const audited = page.getByRole('region', { name: /^已入庫，等你看一眼/ })
  const episode = audited
    .getByRole('listitem')
    .filter({ has: page.getByRole('heading', { name: 'SPY×FAMILY 間諜家家酒 S02E01' }) })
  await expect(episode).toContainText('待確認')
  await episode.getByRole('button', { name: '確認' }).click()

  await expect(page.getByText('已確認，這一列從佇列上收掉了。')).toBeVisible()
  await expect(episode).toHaveCount(0)

  await page.reload()
  const other = page.getByRole('heading', { name: 'SPY×FAMILY 間諜家家酒 S02E02' })
  await expect(other).toBeVisible()
  await expect(page.getByRole('heading', { name: 'SPY×FAMILY 間諜家家酒 S02E01' })).toHaveCount(0)
})
