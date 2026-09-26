import { expect, test } from '@playwright/test'

import { signIn } from './login.ts'
import { shot } from './shot.ts'

// `rss-split-cour`（M3 票 13）：同 `rss`，但 TMDB 把《与你相恋》的兩個 cour 併成一季 24 集，而字幕組的
// 第二 cour 從 01 重數。綁定時補舊集，12 集以「只有集號、TMDB 一季」落在 S01E01–E12——錯的，正解是
// S01E13–E24。它們是這個 RSS Series 的第一批（播完一年後才發佈，不是剛播：證據不夠強，M4 票 11），在
// `/review` 是一組、一句話說在問什麼；在審核裡把第 1 集改成 S01E13 並「套用到這個 RSS Series」，其餘 11 集
// 跟著搬到 14–24，按一次「確認整個 Series」整組收掉。
const EPISODES = Array.from({ length: 12 }, (_, index) => `S01E${String(index + 13)}`)

test('split-cour 的第一批：改一集並套用到 RSS Series，其餘跟著對，全部確認', async ({ page }) => {
  // 替身 qBittorrent 收下就報完成，但 importer 一分鐘醒一次：12 集入庫要等它。
  test.setTimeout(300_000)
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
  await expect(row.getByRole('checkbox', { name: '同時補下載舊集' })).toBeChecked()
  await row.getByRole('button', { name: '綁定、送出 2 集並補舊集' }).click()
  await expect(page.getByText('綁好了，送出 12 集。')).toBeAttached()

  // 12 集都入庫之後，第一批在「已入庫，等你看一眼」是一組。
  await page.goto('/review')
  const audited = page.getByRole('region', { name: /^已入庫，等你看一眼/ })
  const group = audited.getByRole('listitem').filter({
    has: page.getByRole('heading', { level: 3, name: /與妳相戀到生命盡頭/ }),
  })
  await expect(async () => {
    await page.reload()
    await expect(group).toContainText(
      '確認 與妳相戀到生命盡頭 × 喵萌奶茶屋&LoliHouse 的季集對應：S01 E01–E12 由集號直接對應',
      { timeout: 2_000 },
    )
  }).toPass({ timeout: 240_000, intervals: [5_000] })

  await group.getByText('展開').first().click()
  const members = group.getByRole('heading', { level: 4 })
  // 錯的那一份：第二 cour 的 01–12 落在第一 cour 的位置上。
  await expect(members).toHaveCount(12)
  await expect(members.first()).toHaveText('S01E01')
  await shot(page, '1-first-batch')

  // 成員的 `article` 以它的標題為名（組那一個 `article` 也包著這個標題，`filter({ has })` 會兩個都中）。
  const first = group.getByRole('article', { name: 'S01E01', exact: true })
  await first.getByRole('button', { name: '改季集 S01E01' }).click()
  await expect(first.getByRole('spinbutton', { name: '季' })).toHaveValue('1')
  await first.getByRole('spinbutton', { name: '起集' }).fill('13')
  await expect(first.getByRole('checkbox', { name: '套用到這個 RSS Series' })).toBeChecked()
  await first.getByRole('button', { name: '套用', exact: true }).click()
  // 已入庫：按之前說清楚搬的不只這一集。
  await expect(first).toContainText('這個 RSS Series 還沒確認的其他集數也照新的季號與偏移搬過去')
  await shot(page, '2-correcting')
  await first.getByRole('button', { name: '確定修正' }).click()

  await expect(
    page.getByText('已修正，這個 RSS Series 改成第 1 季、集號偏移 +12。 其餘 11 集跟著搬過去了。'),
  ).toBeVisible({ timeout: 60_000 })
  // 人改的那一集是人決定的，離開清單；跟著搬的 11 集仍是第一批，等人按全部確認。
  await expect(group).toContainText(
    '確認 與妳相戀到生命盡頭 × 喵萌奶茶屋&LoliHouse 的季集對應：S01 E14–E24 照 Series 設的季號與偏移換算',
  )
  await expect(members).toHaveCount(11)
  expect((await members.allTextContents()).sort()).toEqual(EPISODES.slice(1))
  await expect(group).toContainText('第 1 季、集號偏移 +12')
  await shot(page, '3-corrected')

  await group.getByRole('button', { name: '確認整個 Series' }).click()
  await expect(page.getByText('已確認 11 個，從佇列上收掉了。')).toBeVisible()
  await expect(group).toHaveCount(0)

  // 重新整理也不回來：旗標與 Series 的 `confirmed` 真的寫進資料庫了。
  await page.reload()
  await expect(page.getByRole('heading', { level: 1, name: '審核' })).toBeVisible()
  await expect(audited.getByText('待確認', { exact: true })).toHaveCount(0)
  await shot(page, '4-confirmed')
})
