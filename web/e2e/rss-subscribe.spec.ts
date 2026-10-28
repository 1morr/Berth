import { expect, test } from '@playwright/test'

import { signIn } from './login.ts'
import { shot } from './shot.ts'

// 從詳情頁訂閱（M3 票 19），`rss` 情境：《与你相恋到生命尽头》的詳情頁。Mikan 以原文標題搜到番組 4009，
// 訂閱喵萌奶茶屋&LoliHouse 就是它的單一 feed——整季 12 集進下載列表，這一段列出綁好的那個 RSS Series。
// 接著以英文標題訂閱 acg.rip（M5 票 26）：先搜、列出搜到的字幕組，選喵萌奶茶屋&LoliHouse、看它的第一批，
// 第一批選「只追之後的」，按下去才建、只綁那一組（第一輪就在這裡選，不再到 RSS 頁）。
//
// **先等那 12 集入庫再訂閱**（M4 票 121b）：acg.rip 那一份裡喵萌奶茶屋&LoliHouse 的 11、12 集發佈名與
// Mikan 的一字不差。送單前照當下的帳本去重，入庫了就是「重複」、一筆都不送；替身 qBittorrent 收下就完成，
// 入庫約在訂閱後 5 秒落地，不等的話送不送看誰先到。
const DETAIL = '/media/tv:262000'

test('詳情頁訂閱 Mikan 番組 × 字幕組，再訂閱 acg.rip 的一個字幕組', async ({ page }) => {
  await signIn(page, DETAIL)
  const block = page.getByRole('region', { name: 'RSS 訂閱' })
  await expect(block).toContainText('還沒有 RSS Series 綁在這部作品上。')

  await block.getByRole('button', { name: '新增訂閱' }).click()
  await block.getByRole('button', { name: '与你相恋到生命尽头' }).click()
  await block.getByRole('button', { name: /LoliHouse/ }).click()
  await block.getByRole('combobox', { name: '入庫到' }).selectOption('Anime')
  await expect(block.getByText(/讀這個字幕組在 Mikan 上的整季/)).toBeVisible()
  // 每日補漏說得出補什麼、完結就停（M4 票 108），與 /rss 的 RSS Series 段落同一句。
  await expect(block.getByText(/讀這個字幕組在 Mikan 上的整季/)).toContainText('完結之後就不再讀')
  await shot(page, '1-mikan-picked')
  await block.getByRole('button', { name: '訂閱並送出' }).click()

  await expect(block.getByText('已訂閱，送出 12 集。')).toBeVisible()
  await expect(block.getByText('MIKAN')).toBeVisible()
  // 字幕組說 Mikan 番組頁上的名字（挑的時候讀過的，M4 票 13），不是發佈名讀出的那一串。
  await expect(block.getByText('LoliHouse', { exact: true })).toBeVisible()
  await expect(block.getByText('第一批待確認')).toBeVisible()
  await shot(page, '2-mikan-subscribed')

  // 入庫了的不在預設的「在路上」（M4 票 04）：看全部。
  await page.goto('/jobs?filter=all')
  const jobs = page.getByRole('listitem').filter({ hasText: 'Kimi ga Shinu made Koi wo Shitai' })
  await expect(jobs).toHaveCount(12)
  await expect(jobs.filter({ hasText: '已入庫' })).toHaveCount(12, { timeout: 60_000 })

  await page.goto(DETAIL)
  await block.getByRole('button', { name: '新增訂閱' }).click()
  await block.getByRole('button', { name: /^ACG\.RIP/ }).click()
  await expect(
    block.getByRole('button', { name: 'Kimi ga Shinu made Koi wo Shitai' }),
  ).toHaveAttribute('aria-pressed', 'true')
  await block.getByRole('combobox', { name: '入庫到' }).selectOption('Anime')
  // 以預填的詞搜一次，列出搜到的字幕組（筆數、最近更新、最新一筆）；沒選之前沒有訂閱鍵。
  await expect(block.getByRole('button', { name: /^北宇治字幕组\s*6 筆/ })).toBeVisible()
  await expect(block.getByRole('button', { name: /^ANi\s*2 筆/ })).toBeVisible()
  await expect(block.getByRole('button', { name: /訂閱並送出第一批/ })).toHaveCount(0)
  await shot(page, '3-acgrip-subgroups')

  await block.getByRole('button', { name: /^喵萌奶茶屋&LoliHouse/ }).click()
  // 第一批列出這一組的兩筆（12 也是那一顆鍵上的「最新一筆」，所以看 11）。
  await expect(block.getByText(/^\[喵萌奶茶屋&LoliHouse\].* - 11 /)).toBeVisible()
  // 第一批的兩個選擇（同 RSS 頁第一輪那兩顆），預設下載這些並追之後的；這裡選只追之後的。
  await expect(block.getByRole('button', { name: /^下載這些並追之後的/ })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await expect(block.getByRole('button', { name: '訂閱並送出第一批（2 筆）' })).toBeVisible()
  await shot(page, '4-acgrip-picked')
  await block.getByRole('button', { name: /^只追之後的/ }).click()
  await shot(page, '5-acgrip-later')
  await block.getByRole('button', { name: '訂閱，只追之後的' }).click()

  await expect(
    block.getByText(
      '已訂閱「acg.rip · Kimi ga Shinu made Koi wo Shitai · 喵萌奶茶屋&LoliHouse」，只追之後的：現有的一筆都沒送。',
    ),
  ).toBeVisible()
  // 只綁選的那一組：作品這一段多一列 acg.rip；第一輪已經選過，現有的兩筆記成略過。
  await expect(block.getByRole('listitem').filter({ hasText: 'ACG.RIP' })).toHaveCount(1)
  const feeds = (await (await page.request.get('/api/rss/feeds')).json()) as {
    id: number
    kind: string
    primed_at: string | null
  }[]
  const keyword = feeds.find((feed) => feed.kind === 'acgrip')
  expect(keyword?.primed_at).not.toBeNull()
  const items = (await (
    await page.request.get(`/api/rss/feeds/${String(keyword?.id)}/preview`)
  ).json()) as { status: string }[]
  expect(items.map((item) => item.status)).toEqual(['passed', 'passed'])
  await shot(page, '6-acgrip-subscribed')

  // 只追之後的一筆都不送：下載列表仍是 Mikan 的那 12 筆。
  await page.goto('/jobs?filter=all')
  await expect(jobs).toHaveCount(12)
})
