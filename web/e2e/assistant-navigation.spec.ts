import { expect, test, type Page } from '@playwright/test'

import { signIn } from './login.ts'
import { reopenOnNarrow } from './panel.ts'
import { shot } from './shot.ts'

// `assistant`（同 `assistant.spec.ts`）：換頁時側面板不重建（M5 票 15b）。最常見的換頁是點卡片裡的作品連結
// ——面板最主要的用法：桌機上邊開著面板邊看那一部；窄版上連結會收起面板（M5 票 15），回來再打開。

/**
 * 點了作品連結之後**等那一頁真的畫出來**才斷言：網址一換就問的話，舊的面板還沒被換掉，讀到的是換頁前的那一份
 * （第一版的 repro 在 1280 因此是假的綠）。窄版的面板開著時頁面藏著，先等頁面、再打開面板。
 */
async function landOnWork(page: Page) {
  await expect(page).toHaveURL(/\/media\/tv(:|%3A)209867$/)
  // 演練的 TMDB 替身只認得 SPY×FAMILY：這一部的作品頁印 id。換頁之前 `/weekly` 的 h1 是「週報」。窄版的面板
  // 被連結收起了，桌機的面板並排，兩種都看得到這一頁的 h1。
  await expect(page.locator('main#main').getByRole('heading', { level: 1 })).toHaveText('tv:209867')
  await reopenOnNarrow(page)
}

/** 問一次「最近入庫」，拿到一張帶作品連結的卡。 */
async function withRecentImports(page: Page) {
  await signIn(page, '/weekly')
  await page.getByRole('button', { name: '助理' }).click()
  const panel = page.getByRole('complementary', { name: '助理' })
  const input = panel.getByRole('textbox', { name: '跟助理說' })
  await panel.getByRole('button', { name: '新對話' }).click()
  await input.fill('這週入庫了什麼')
  await input.press('Enter')
  const card = panel.getByRole('region', { name: '最近 7 天入庫' })
  await expect(card).toBeVisible({ timeout: 15_000 })
  await expect(panel.getByRole('button', { name: '送出' })).toBeVisible()
  return { panel, input, work: card.getByRole('link', { name: '葬送的芙莉蓮' }) }
}

test('打了字還沒送出就點卡片裡的作品換頁：字還在', async ({ page }) => {
  const { panel, input, work } = await withRecentImports(page)

  await input.fill('這部的第二季')
  await work.click()
  await landOnWork(page)

  await expect(panel.getByRole('textbox', { name: '跟助理說' })).toHaveValue('這部的第二季')
  await shot(page, 'draft-kept')
})

test('回覆串流到一半時點卡片裡的作品換頁：回覆照樣接著畫完，還是同一則對話', async ({ page }) => {
  const { panel, input, work } = await withRecentImports(page)
  // 演練的回覆照抄這一句，每 0.08 秒六個字：這一句大約要吐六秒。
  const long = '請把這一段話完整照抄回來，'.repeat(36)

  await input.fill(long)
  await input.press('Enter')
  const log = panel.getByRole('log')
  const streaming = log.locator('[aria-busy="true"]')
  await expect(streaming.getByText(/（演練）收到/)).toBeVisible()
  await work.click()
  await landOnWork(page)

  // 換頁之後那一則還在吐字（不是只剩「回覆中…」、等存進對話才一次出現），接著畫完；最近入庫的卡還在同一則裡。
  await expect(streaming.getByText(/（演練）收到/)).toBeVisible()
  await expect(panel.getByText(/這台是演練伺服器，回覆是照抄的。/)).toBeVisible({ timeout: 15_000 })
  await expect(streaming).toHaveCount(0)
  await expect(panel.getByRole('region', { name: '最近 7 天入庫' })).toBeVisible()
  await shot(page, 'stream-finished')
})
