import { expect, test } from '@playwright/test'

import { signIn } from './login.ts'
import { shot } from './shot.ts'

// 排除條件三層與去重（M3 票 10），`rss` 情境。全域擋 ANi（`Baha` 是它的片源）、寫壞的正則存不進去、
// 建議項一鍵加入；綁好《与你相恋》（不補舊集）之後在那個 RSS Series 上擋掉 1–10 集，再加它的單一 feed：
// 11、12 與聚合 feed 同一個 hash，是重複；1–10 被 RSS Series 那一層擋下。每一筆都說得出為什麼。
test('三層排除與重複：清單上每一筆都說得出為什麼沒下載', async ({ page }) => {
  await signIn(page, '/rss')

  const rules = page.getByRole('region', { name: '排除條件' })
  await expect(rules.getByRole('checkbox', { name: /不自動下載合集/ })).toBeChecked()
  const field = rules.getByLabel('加一條排除條件')
  await field.fill('/[简繁/')
  await rules.getByRole('button', { name: '加入規則' }).click()
  await expect(rules).toContainText('存不進去：/[简繁/: unterminated character set')
  await expect(field).toHaveValue('/[简繁/')
  await shot(page, '1-broken-regex')

  await field.fill('Baha')
  await rules.getByRole('button', { name: '加入規則' }).click()
  await expect(rules.getByRole('button', { name: '拿掉「Baha」' })).toBeVisible()
  await rules.getByRole('button', { name: '加入「720p」' }).click()
  await expect(rules.getByRole('button', { name: '拿掉「720p」' })).toBeVisible()
  await expect(rules.getByRole('button', { name: '加入「720p」' })).toHaveCount(0)

  await page.getByLabel(/RSS 網址/).fill('https://mikanani.me/RSS/MyBangumi?token=REDACTED')
  await page.getByRole('button', { name: '加入', exact: true }).click()
  const aggregate = page.getByRole('article', { name: 'mikanani.me' })
  await aggregate.getByRole('button', { name: '立即輪詢' }).click()
  await expect(aggregate.getByRole('status')).toContainText('新 12 筆')

  const items = page.getByRole('region', { name: '最近的 Feed Item' })
  // ANi 在聚合 feed 裡有五筆，全域那一條擋下它們。
  await expect(items.getByText('全域的排除條件「Baha」擋下')).toHaveCount(5)
  await shot(page, '2-global-rule')

  const pending = page.getByRole('region', { name: '待綁定' })
  const row = pending.getByRole('article', { name: /与你相恋到生命尽头/ })
  await row.getByRole('button', { name: /選《與妳相戀到生命盡頭》/ }).click()
  await row.getByRole('combobox', { name: '入庫到' }).selectOption('Anime')
  await row.getByRole('checkbox', { name: '同時補下載舊集' }).uncheck()
  await row.getByRole('button', { name: '綁定並送出 2 集' }).click()

  const bound = page
    .getByRole('region', { name: 'RSS Series' })
    .getByRole('article', { name: '與妳相戀到生命盡頭' })
  await bound.getByRole('button', { name: '排除條件（0 條）' }).click()
  await bound.getByLabel('加一條排除條件').fill('/ - (0\\d|10) \\[/')
  await bound.getByRole('button', { name: '加入規則' }).click()
  await expect(bound.getByRole('button', { name: '排除條件（1 條）' })).toBeVisible()

  await page
    .getByLabel(/RSS 網址/)
    .fill('https://mikanani.me/RSS/Bangumi?bangumiId=4009&subgroupid=370')
  await page.getByLabel(/名稱/).fill('与你相恋 單一')
  await page.getByRole('button', { name: '加入', exact: true }).click()
  const single = page.getByRole('article', { name: '与你相恋 單一' })
  await single.getByRole('button', { name: '立即輪詢' }).click()
  await expect(single.getByRole('status')).toHaveText(
    '這一輪：新 12 筆、長出 0 個 RSS Series（自動綁定 0 個）、送出 0 筆。',
  )
  await expect(items.getByText(/同一個 torrent 已經送過了/)).toHaveCount(2)
  await expect(items.getByText('這個 RSS Series 的排除條件「/ - (0\\d|10) \\[/」擋下')).toHaveCount(
    10,
  )
  await expect(items.getByText('重複', { exact: true })).toHaveCount(2)
  // 重複的兩筆連到聚合 feed 送出的那兩筆下載，連同那兩筆自己：四條連結。
  await expect(items.getByRole('link', { name: '看這一筆下載' })).toHaveCount(4)
  await shot(page, '3-duplicates')
})
