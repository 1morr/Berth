import { expect, test } from '@playwright/test'

import { signIn } from './login.ts'
import { narrow, shot } from './shot.ts'

// `assistant`：同 `weekly`，AI 設定好了；`DemoChatProvider` 一段一段吐字、話裡有「入庫」時呼叫
// 「最近入庫」、有「限流」時演被限流 30 秒（M5 票 08，`.scratch/m5/side-panel-shape.md`）。

const PAGES = [
  '/',
  '/library',
  '/jobs',
  '/review',
  '/issues',
  '/rss',
  '/weekly',
  '/health',
  '/settings',
]

test('每一頁都開得到側面板，換頁與重整都還開著', async ({ page }) => {
  await signIn(page, '/health')
  await page.getByRole('button', { name: '助理' }).click()
  const panel = page.getByRole('complementary', { name: '助理' })
  await expect(panel.getByRole('textbox', { name: '跟助理說' })).toBeFocused()

  for (const path of PAGES) {
    await page.goto(path)
    await expect(panel).toBeVisible()
    await expect(page.getByRole('button', { name: '助理' })).toHaveAttribute(
      'aria-expanded',
      'true',
    )
    // 並排（桌機）或取代頁面（窄版），兩種都不撐出橫向捲動。
    const overflow = await page.evaluate<number>(
      'document.documentElement.scrollWidth - window.innerWidth',
    )
    expect(overflow, path).toBe(0)
    await expect(page.locator('main#main')).toBeVisible({ visible: !narrow(page) })
  }

  await panel.getByRole('button', { name: '關閉' }).click()
  await expect(panel).toHaveCount(0)
  await expect(page.getByRole('button', { name: '助理' })).toBeFocused()
  await page.reload()
  await expect(panel).toHaveCount(0)
})

test('串流的字一段一段出來，工具呼叫說正在查，限流說幾秒後再送', async ({ page }) => {
  await signIn(page, '/weekly')
  await page.getByRole('button', { name: '助理' }).click()
  const panel = page.getByRole('complementary', { name: '助理' })
  const input = panel.getByRole('textbox', { name: '跟助理說' })
  const log = panel.getByRole('log')

  await input.fill('你好，這個側面板現在能做什麼？請用一段話說明。')
  await input.press('Enter')
  // 講到一半：已經有字、那一塊還 `aria-busy`、送出鍵說回覆中。
  await expect(log.getByText(/（演練）收到/)).toBeVisible()
  await expect(log.locator('[aria-busy="true"]')).toHaveCount(1)
  await expect(panel.getByRole('button', { name: '回覆中…' })).toBeVisible()
  await shot(page, 'streaming')
  await expect(log.getByText(/回覆是照抄的。$/)).toBeVisible()
  await expect(panel.getByRole('button', { name: '送出' })).toBeVisible()

  await input.fill('這週入庫了什麼')
  await input.press('Enter')
  await expect(panel.getByText('正在查最近入庫')).toBeVisible()
  await shot(page, 'tool-running')
  await expect(panel.getByText('查過最近入庫')).toBeVisible()
  await expect(log.getByText(/這七天入庫了 \d+ 部作品/)).toBeVisible()

  await input.fill('觸發限流')
  await input.press('Enter')
  await expect(panel.getByText('AI 端點要 Berth 慢一點：30 秒後再送。')).toBeVisible()
  await expect(panel.getByText('等一下')).toBeVisible()

  // 重整之後三段都還在（存在 Berth），模型的字沒有塗成功色。
  await page.reload()
  await expect(log.getByText('這週入庫了什麼')).toBeVisible()
  await expect(panel.getByText('查過最近入庫')).toBeVisible()
  await expect(panel.getByText('AI 端點要 Berth 慢一點：30 秒後再送。')).toBeVisible()
  await expect(panel.locator('.bg-secured')).toHaveCount(0)
  await shot(page, 'reloaded')
})
