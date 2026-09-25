import { expect, test } from '@playwright/test'

import { signIn } from './login.ts'
import { shot } from './shot.ts'

// 從詳情頁訂閱（M3 票 19），`rss` 情境：《与你相恋到生命尽头》的詳情頁。Mikan 以原文標題搜到番組 4009，
// 訂閱喵萌奶茶屋&LoliHouse 就是它的單一 feed——整季 12 集進下載列表，這一段列出綁好的那個 RSS Series。
// 接著以英文標題建 acg.rip 搜尋 feed：長出的字幕組都綁在這部作品上，第一輪就地停在預覽。
const DETAIL = '/media/tv:262000'

test('詳情頁訂閱 Mikan 番組 × 字幕組，再建 acg.rip 搜尋 feed 看第一輪', async ({ page }) => {
  await signIn(page, DETAIL)
  const block = page.getByRole('region', { name: 'RSS 訂閱' })
  await expect(block).toContainText('還沒有 RSS Series 綁在這部作品上。')

  await block.getByRole('button', { name: '新增訂閱' }).click()
  await block.getByRole('button', { name: '与你相恋到生命尽头' }).click()
  await block.getByRole('button', { name: /LoliHouse/ }).click()
  await block.getByRole('combobox', { name: '入庫到' }).selectOption('Anime')
  await expect(block.getByRole('checkbox', { name: '同時補下載舊集' })).toBeChecked()
  await shot(page, '1-mikan-picked')
  await block.getByRole('button', { name: '訂閱並補舊集' }).click()

  await expect(block.getByText('已訂閱，送出 12 集。')).toBeVisible()
  await expect(block.getByText('MIKAN')).toBeVisible()
  await expect(block.getByText('喵萌奶茶屋&LoliHouse', { exact: true })).toBeVisible()
  await expect(block.getByText('第一批待確認')).toBeVisible()
  await shot(page, '2-mikan-subscribed')

  await block.getByRole('button', { name: '新增訂閱' }).click()
  await block.getByRole('button', { name: /^ACG\.RIP/ }).click()
  await expect(
    block.getByRole('button', { name: 'Kimi ga Shinu made Koi wo Shitai' }),
  ).toHaveAttribute('aria-pressed', 'true')
  await block.getByRole('combobox', { name: '入庫到' }).selectOption('Anime')
  await block.getByRole('button', { name: '建立搜尋 feed' }).click()
  await expect(block.getByRole('button', { name: '只追之後的' })).toBeVisible()
  // 長出的字幕組都已經綁在這部作品上：30 筆全在「會送出」，沒有一筆要等綁定。
  await expect(block).toContainText('會送出 30 · 綁定之後送 0')
  await shot(page, '3-acgrip-first-round')

  await block.getByRole('button', { name: '只追之後的' }).click()
  await expect(block.getByRole('button', { name: '只追之後的' })).toHaveCount(0)
  await shot(page, '4-acgrip-primed')

  await page.goto('/jobs')
  const jobs = page.getByRole('listitem').filter({ hasText: 'Kimi ga Shinu made Koi wo Shitai' })
  await expect(jobs).toHaveCount(12)
})
