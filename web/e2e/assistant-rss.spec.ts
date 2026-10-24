import { expect, test } from '@playwright/test'

import { signIn } from './login.ts'
import { reopenOnNarrow } from './panel.ts'
import { shot } from './shot.ts'

// `assistant-rss`：同 `rss`（《与你相恋》的 Mikan 搜尋頁、番組頁、單一 feed 都是替身），AI 設定好了。在作品頁
// 說「訂閱」時 `DemoChatProvider` 先查作品名、搜 Mikan、列字幕組、訂閱 LoliHouse（M5 票 11）。

const KIMI = '/media/tv:262000'

test('在作品頁說「訂閱這部的 Mikan RSS」：直接訂好、沒有確認卡，卡上撤銷得掉', async ({ page }) => {
  await signIn(page, KIMI)
  await page.getByRole('button', { name: '助理' }).click()
  const panel = page.getByRole('complementary', { name: '助理' })
  const input = panel.getByRole('textbox', { name: '跟助理說' })

  await input.fill('訂閱這部的 Mikan RSS')
  await input.press('Enter')
  const card = panel.getByRole('region', { name: '訂閱' })
  await expect(card.getByText('与你相恋到生命尽头 · LoliHouse')).toBeVisible({ timeout: 15_000 })
  await expect(card.getByText(/當場送出 12 筆/)).toBeVisible()
  await expect(card.getByText(/下一次輪詢/)).toBeVisible()
  await expect(panel.getByText('訂閱好了')).toBeVisible()
  // 網址是 Berth 自己組的：沒有確認卡。
  await expect(panel.getByRole('button', { name: /^確認/ })).toHaveCount(0)
  await expect(panel.getByRole('button', { name: '送出' })).toBeVisible()
  await shot(page, 'subscribed')

  // RSS 頁上看得到這個 Feed：桌機並排；窄版換頁時面板不照記憶打開，先看到那一頁，再打開面板（M5 票 15）。
  await page.goto('/rss')
  const feedOnPage = page.locator('main#main').getByText('与你相恋到生命尽头 · LoliHouse')
  await expect(feedOnPage.first()).toBeVisible()
  await reopenOnNarrow(page)

  await card.getByRole('button', { name: '撤銷訂閱' }).click()
  await expect(card.getByText(/已經下載完的留著/)).toBeVisible()
  await shot(page, 'undo-confirm')
  await card.getByRole('button', { name: '撤銷訂閱' }).last().click()
  await expect(card.getByText(/已撤銷這個訂閱/)).toBeVisible()
  await expect(card.getByRole('button', { name: '撤銷訂閱' })).toHaveCount(0)
  // RSS 頁跟著換：那個 Feed 不在了。
  await expect(feedOnPage).toHaveCount(0)
  await shot(page, 'unsubscribed')

  // 重整之後卡片照存下的那一則說已撤銷。
  await page.reload()
  await reopenOnNarrow(page)
  await expect(
    panel.getByRole('region', { name: '訂閱' }).getByText(/已撤銷這個訂閱/),
  ).toBeVisible()
})
