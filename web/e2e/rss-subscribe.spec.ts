import { expect, test } from '@playwright/test'

import { signIn } from './login.ts'
import { shot } from './shot.ts'

// 從詳情頁訂閱（M3 票 19），`rss` 情境：《与你相恋到生命尽头》的詳情頁。Mikan 以原文標題搜到番組 4009，
// 訂閱喵萌奶茶屋&LoliHouse 就是它的單一 feed——整季 12 集進下載列表，這一段列出綁好的那個 RSS Series。
// 接著以英文標題建 acg.rip 搜尋 feed：長出的字幕組都綁在這部作品上，第一輪就地停在預覽。
//
// **先等那 12 集入庫再建搜尋 feed**（M4 票 121b）：acg.rip 那一份裡也有喵萌奶茶屋&LoliHouse 的 11、12 集，
// 發佈名與 Mikan 的一字不差。預覽照當下的帳本去重，入庫了就是「重複」、還沒入庫就是「會送出」；替身
// qBittorrent 收下就完成，入庫約在訂閱後 5 秒落地，不等的話預覽讀到哪一種看誰先到。
const DETAIL = '/media/tv:262000'

test('詳情頁訂閱 Mikan 番組 × 字幕組，再建 acg.rip 搜尋 feed 看第一輪', async ({ page }) => {
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
  await block.getByRole('button', { name: '建立搜尋 feed' }).click()
  await expect(block.getByRole('button', { name: '只追之後的' })).toBeVisible()
  // 長出的字幕組都已經綁在這部作品上：沒有一筆要等綁定。喵萌奶茶屋&LoliHouse 的 11、12 集剛從 Mikan
  // 入庫，是重複（帳本那一層：acg.rip 不報 info hash），其餘 28 筆會送出。
  await expect(block).toContainText('會送出 28 · 綁定之後送 0 · 排除 0 · 重複 2')
  await block.getByRole('button', { name: '看重複（2 筆）' }).click()
  await expect(block.getByText(/媒體庫裡已經有同一個版本/)).toHaveCount(2)
  await expect(block).toContainText('S01E11 [WEB][1080p][CHS+CHT+JP][LoliHouse].mkv')
  await expect(block).toContainText('S01E12 [WEB][1080p][CHS+CHT+JP][LoliHouse].mkv')
  await shot(page, '3-acgrip-first-round')

  await block.getByRole('button', { name: '只追之後的' }).click()
  await expect(block.getByRole('button', { name: '只追之後的' })).toHaveCount(0)
  await shot(page, '4-acgrip-primed')

  // 「只追之後的」一筆都不送：下載列表仍是 Mikan 的那 12 筆。
  await page.goto('/jobs?filter=all')
  await expect(jobs).toHaveCount(12)
})
