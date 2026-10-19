import { expect, test } from '@playwright/test'

import { addFeed } from './feed.ts'
import { signIn } from './login.ts'
import { shot } from './shot.ts'

// 排除條件三層與去重（M3 票 10），`rss` 情境。全域擋 ANi（`Baha` 是它的片源）、寫壞的正則存不進去、
// 建議項一鍵加入；《与你相恋》自動綁好（整季補齊）之後在那個 RSS Series 上擋掉 1–10 集，再加它的單一 feed：
// 排除條件在寫下那一刻就看，1–10 被 RSS Series 那一層擋下；12 被新增表單上就帶著的 Feed 規則擋下
// （M4 票 110）；11 過得了，送單時與聚合 feed 同一個 hash，是重複。每一筆都說得出為什麼。
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

  await addFeed(page, 'https://mikanani.me/RSS/MyBangumi?token=REDACTED')
  const aggregate = page.getByRole('article', { name: 'mikanani.me' })
  await aggregate.getByRole('button', { name: '立即輪詢' }).click()
  await expect(aggregate.getByRole('status')).toContainText('新 12 筆')

  const items = page.getByRole('region', { name: '最近的 Feed Item' })
  // ANi 在聚合 feed 裡有五筆，全域那一條擋下它們。
  await expect(items.getByText('全域的排除條件「Baha」擋下')).toHaveCount(5)
  await shot(page, '2-global-rule')

  // 加 Feed 時說了劇集送進 Anime（M4 票 105）：《与你相恋》輪詢時就自動綁上、整季補齊。
  await expect(aggregate.getByRole('status')).toContainText('（自動綁定 1 個）、送出 12 筆')

  const bound = page
    .getByRole('region', { name: 'RSS Series' })
    .getByRole('article', { name: '與妳相戀到生命盡頭' })
  // Series 層的排除條件在字幕組那一列展開後的「進階」裡（M4 票 13）。
  await bound.getByRole('article', { name: 'LoliHouse' }).locator('summary').click()
  await bound.getByRole('button', { name: '排除條件（0 條）' }).click()
  await bound.getByLabel('加一條排除條件').fill('/ - (0\\d|10) \\[/')
  await bound.getByRole('button', { name: '加入規則' }).click()
  await expect(bound.getByRole('button', { name: '排除條件（1 條）' })).toBeVisible()

  // 新增表單上先寫 Feed 那一層（M4 票 110）：跟著「加入」一起存，第一輪寫下的那一刻就看。
  const onAdd = page.getByRole('group', { name: '排除條件' })
  await onAdd.getByLabel('加一條排除條件').fill('/ - 12 \\[/')
  await onAdd.getByRole('button', { name: '加入規則' }).click()
  await expect(onAdd.getByRole('button', { name: '拿掉「/ - 12 \\[/」' })).toBeVisible()
  await shot(page, '3-rules-on-add')
  await addFeed(page, 'https://mikanani.me/RSS/Bangumi?bangumiId=4009&subgroupid=370', {
    name: '与你相恋 單一',
  })
  const single = page.getByRole('article', { name: '与你相恋 單一' })
  await expect(single.getByRole('button', { name: '排除條件（1 條）' })).toBeVisible()
  await expect(onAdd.getByText('沒有排除條件。')).toBeVisible()
  await single.getByRole('button', { name: '立即輪詢' }).click()
  await expect(single.getByRole('status')).toHaveText(
    '這一輪：新 12 筆、長出 0 個 RSS Series（自動綁定 0 個）、送出 0 筆。',
  )
  await expect(items.getByText(/同一個 torrent 已經送過了/)).toHaveCount(1)
  await expect(items.getByText('這個 Feed 的排除條件「/ - 12 \\[/」擋下')).toHaveCount(1)
  await expect(items.getByText('這個 RSS Series 的排除條件「/ - (0\\d|10) \\[/」擋下')).toHaveCount(
    10,
  )
  await expect(items.getByText('重複', { exact: true })).toHaveCount(1)
  // 綁定時整季補齊、送出 12 筆；重複的那一筆連到 11 那一筆下載：十三條連結。
  await expect(items.getByRole('link', { name: '看這一筆下載' })).toHaveCount(13)
  await shot(page, '4-duplicates')
})
