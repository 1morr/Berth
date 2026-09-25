import { expect, test } from '@playwright/test'

import { signIn } from './login.ts'
import { shot } from './shot.ts'

// `rss-split-cour-airing`（M3 票 14b）：同 `rss-split-cour`，但第二 cour 正在播。綁定時補舊集，12 集照字面
// 對到一月播出的 S01E01–E12，而發佈當時在播的是七月之後的那幾集——播出日比對把 12 份計劃整批擋在審核，
// 一集都沒入庫。在其中一份把第 1 集改成 S01E13 並「套用到這個 RSS Series」：其餘 11 份重新規劃、通過比對、
// 自動入庫（仍是第一批，等全部確認）；改的那一份照人說的留著，核准之後才入庫。
const FIRST = '[LoliHouse] Kimi ga Shinu made Koi wo Shitai - 01 [1080p].mkv'
const EPISODES = Array.from({ length: 11 }, (_, index) => `S01E${String(index + 14)}`)

test('連載中的 split-cour：整批擋在審核 → 改一列套用到 RSS Series → 其餘自動入庫', async ({
  page,
}) => {
  // 替身 qBittorrent 收下就報完成，但規劃器與 importer 一分鐘醒一次：12 份計劃與 11 集入庫都要等它們。
  test.setTimeout(420_000)
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
  await row.getByRole('button', { name: '綁定、送出 2 集並補舊集' }).click()
  await expect(page.getByText('綁好了，送出 12 集。')).toBeAttached()

  // 12 份計劃都規劃完、都停在「要你決定」，理由是播出日對不上；一集都沒入庫。
  await page.goto('/review')
  const decide = page.getByRole('region', { name: /^要你決定/ })
  const plans = decide.getByRole('article').filter({ hasText: '播出日對不上' })
  await expect(async () => {
    await page.reload()
    await expect(plans).toHaveCount(12, { timeout: 2_000 })
  }).toPass({ timeout: 300_000, intervals: [5_000] })
  const audited = page.getByRole('region', { name: /^已入庫，等你看一眼/ })
  await expect(audited).toHaveCount(0)

  const edit = page.getByRole('button', { name: `改 ${FIRST}` })
  // 以檔名認那一份：按下「改」之後那顆按鈕就收起來了。
  const held = plans.filter({ hasText: FIRST })
  await expect(held).toContainText('S01E01 在 2026-01-08 播出')
  await shot(page, '1-held')

  await edit.click()
  await held.getByRole('spinbutton', { name: '起集' }).fill('13')
  await expect(held.getByRole('checkbox', { name: '套用到這個 RSS Series' })).toBeChecked()
  await shot(page, '2-correcting')
  await held.getByRole('button', { name: '套用', exact: true }).click()

  // 結果畫在頁上：其餘 11 份從佇列上消失了，只念出來的話看得見的人不知道它們去了哪。
  await expect(
    page.getByText(
      '已修正，這個 RSS Series 改成第 1 季、集號偏移 +12。 11 筆等審核的下載照新的值重新規劃了。 這一份照你改的留著，核准之後才入庫。',
    ),
  ).toBeVisible({ timeout: 60_000 })
  await expect(plans).toHaveCount(1)
  await expect(held).toContainText('S01E13')
  await shot(page, '3-corrected')

  // 其餘 11 集通過播出日比對、自動入庫：第一批，在「已入庫，等你看一眼」是一組。
  const group = audited.getByRole('listitem').filter({
    has: page.getByRole('heading', { level: 3, name: /與妳相戀到生命盡頭/ }),
  })
  await expect(async () => {
    await page.reload()
    await expect(group).toContainText('RSS Series 的第一批：11 個檔案', { timeout: 2_000 })
  }).toPass({ timeout: 180_000, intervals: [5_000] })
  await group.getByText('展開').first().click()
  const members = group.getByRole('heading', { level: 4 })
  await expect(members).toHaveCount(11)
  expect((await members.allTextContents()).sort()).toEqual(EPISODES)

  // 改的那一份照人說的核准入庫。
  await held.getByRole('button', { name: '核准並入庫' }).click()
  await expect(page.getByText('已核准，開始入庫。')).toBeVisible()
  await expect(plans).toHaveCount(0)
  await shot(page, '4-approved')
})
