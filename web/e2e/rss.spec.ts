import { expect, test } from '@playwright/test'

import { signIn } from './login.ts'
import { shot } from './shot.ts'

// `rss`（M3 票 08）：同 `healthy`，加上 Mikan 與 TMDB 的替身，一個請求都不出網。聚合 feed 是票 07
// 錄下來的那一份，替身 qBittorrent 收下 torrent 就報成完成，之後的規劃與入庫是產品自己的程式碼。
// TV 與 Anime 兩條 Route 都收劇集：加 Feed 時要說劇集送進哪一條（M4 票 105，沒有「不指定」），輪詢就
// 自動綁定那一部，不經一鍵候選。綁定一律補舊集（票 12、M4 票 78）：聚合 feed 帶到兩集，單一 feed 補齊
// 整季 12 集。
test('加 Feed 選 Route → 輪詢 → 那一部自動綁定 → 下載列表上有它的整季', async ({ page }) => {
  await signIn(page, '/rss')
  await shot(page, '1-empty')

  await page.getByLabel(/RSS 網址/).fill('https://mikanani.me/RSS/MyBangumi?token=REDACTED')
  // 劇集兩條要選；電影只有 Movies，預填好。
  await expect(page.getByRole('combobox', { name: '電影送進' })).toHaveValue(/\d+/)
  await expect(page.getByRole('button', { name: '加入', exact: true })).toBeDisabled()
  await page.getByRole('combobox', { name: '劇集送進' }).selectOption('Anime')
  // 輪詢間隔（M4 票 109）：固定檔位，預設 15 分鐘。
  const interval = page.getByRole('combobox', { name: '輪詢間隔' })
  await expect(interval).toHaveValue('900')
  await interval.selectOption('1 小時')
  await shot(page, '1a-adding')
  await page.getByRole('button', { name: '加入', exact: true }).click()
  const feed = page.getByRole('article', { name: 'mikanani.me' })
  await expect(feed).toContainText('每 1 小時')
  // token 就是憑證：畫面上只留前四碼。
  await expect(feed).toContainText('token=REDA…')
  // 就地改間隔：存下之後收起，那一列說出新值；不當場輪詢。
  await feed.getByRole('button', { name: '改輪詢間隔' }).click()
  await feed.getByRole('combobox', { name: '輪詢間隔' }).selectOption('24 小時')
  await shot(page, '1b-changing-interval')
  await feed.getByRole('button', { name: '存下間隔' }).click()
  await expect(feed.getByRole('status')).toHaveText('存下了：之後每 24 小時輪詢一次。')
  await expect(feed).toContainText('每 24 小時')
  await expect(feed.getByRole('combobox', { name: '輪詢間隔' })).toHaveCount(0)
  await shot(page, '1c-interval-saved')
  await expect(feed).toContainText('劇集送進 Anime')
  await expect(feed).toContainText('電影送進 Movies')
  await expect(feed.getByText('要選 Route')).toHaveCount(0)

  await feed.getByRole('button', { name: '立即輪詢' }).click()
  await expect(feed.getByRole('status')).toHaveText(
    '這一輪：新 12 筆、長出 11 個 RSS Series（自動綁定 1 個）、送出 12 筆。',
  )
  const pending = page.getByRole('region', { name: '待綁定' })
  await expect(pending).toContainText('10 個待綁定')
  await expect(pending.getByRole('article', { name: /与你相恋到生命尽头/ })).toHaveCount(0)
  await shot(page, '2-polled')

  // 以作品呈現（M4 票 13）：作品名與 Route 在塊上，字幕組一列、來源說番組名而不是 Mikan 的數字 id。
  const work = page
    .getByRole('region', { name: 'RSS Series' })
    .getByRole('article', { name: '與妳相戀到生命盡頭' })
  await expect(work.locator('header')).toContainText('Anime')
  const loli = work.getByRole('article', { name: 'LoliHouse' })
  await expect(loli.getByRole('link', { name: 'Mikan：与你相恋到生命尽头' })).toBeVisible()
  await expect(loli).toContainText('最近 E12')
  // 綁上的依據說出是 Feed 挑的 Route。
  await loli.locator('summary').click()
  await expect(loli.getByText('這個 Feed 設定送進 Anime')).toBeVisible()
  await loli.locator('summary').click()
  await shot(page, '3-bound')

  // 入庫了的不在預設的「在路上」（M4 票 04）：看全部。
  await page.goto('/jobs?filter=all')
  const jobs = page.getByRole('listitem').filter({ hasText: 'Kimi ga Shinu made Koi wo Shitai' })
  await expect(jobs).toHaveCount(12)
  await expect(jobs.first()).toContainText('RSS')
  await expect(jobs.filter({ hasText: '已入庫' })).toHaveCount(12, { timeout: 60_000 })
  await shot(page, '4-jobs')

  // 回到 RSS 頁：那一列說出下了什麼，展開看得到它的每一筆；最近的 Feed Item 說出來自哪、屬於誰。
  await page.goto('/rss')
  await expect(loli).toContainText('已入庫 12')
  await loli.locator('summary').click()
  // 自動綁上的那一列在同一個展開裡還有依據那一串：認的是帶下載連結的那一份。
  const own = loli
    .getByRole('list')
    .filter({ has: page.getByRole('link', { name: '看這一筆下載' }) })
  // 單一 feed 補下來的也是這個 Series 的 Item（寫在聚合 Feed 底下）。
  await expect(own.getByRole('listitem')).toHaveCount(12)
  await expect(own.getByRole('listitem').first()).toContainText('E12')
  await expect(own.getByRole('link', { name: '看這一筆下載' })).toHaveCount(12)
  const recent = page.getByRole('region', { name: /最近的 Feed Item/ })
  await expect(
    recent.getByText('來自 mikanani.me · 與妳相戀到生命盡頭 × LoliHouse').first(),
  ).toBeVisible()
  await expect(recent.getByText('來自 mikanani.me · 待綁定').first()).toBeVisible()
  const text = (await page.locator('main').innerText()) + (await page.locator('main').textContent())
  expect(text).not.toMatch(/Mikan \d|mikan:\d|4009|× 370/)
  await shot(page, '4b-rss-by-work')

  // 兩集都只寫集號、單季、發佈時剛播、播出日對得上：證據夠強，系統確認了這個 Series（M4 票 11）。
  // 審核頁沒有它的第一批，作品頁的 RSS 訂閱說已確認，下載的時間線說出依據。
  await page.goto('/review')
  await expect(page.getByRole('heading', { level: 1, name: '審核' })).toBeVisible()
  await expect(page.getByText(/的季集對應/)).toHaveCount(0)
  await page.goto('/media/tv:262000')
  const block = page.getByRole('region', { name: 'RSS 訂閱' })
  await expect(block.getByText('第一批已確認')).toBeVisible()
  await page.goto('/jobs?filter=all')
  // 列是原生 `<details>`：先展開，詳情頁的連結在裡面。
  await jobs.first().locator('summary').click()
  await jobs.first().getByRole('link', { name: '下載詳情' }).click()
  // 詳情頁的計劃歷史與完整時間線各畫一次（它屬於計劃歷史，`jobs/eventTypes.ts`）。
  await expect(page.getByText(/第一批的證據夠強，系統確認了這個 RSS Series/).first()).toBeVisible()
  await expect(page.getByText('S01E11 S01E12').first()).toBeVisible()
  await shot(page, '5-series-confirmed')
})
