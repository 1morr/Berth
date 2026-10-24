import { expect, test } from '@playwright/test'

import { signIn } from './login.ts'
import { narrow, shot } from './shot.ts'

// `assistant`（同 `assistant.spec.ts`）：在側面板讓助理送一筆單、提議加索引站並確認，再到 AI 活動頁
// （M5 票 14，`.scratch/m5/ai-activity-shape.md`）看這兩件、從頁面撤銷送單。

test('助理做過的寫入都列在 AI 活動頁：送單撤得掉，加索引站說撤不回，連得回那則對話', async ({
  page,
}) => {
  await signIn(page, '/media/tv:120089')
  await page.getByRole('button', { name: '助理' }).click()
  const panel = page.getByRole('complementary', { name: '助理' })
  const input = panel.getByRole('textbox', { name: '跟助理說' })
  await panel.getByRole('button', { name: '新對話' }).click()

  await input.fill('這部缺的集搜一下並下載')
  await input.press('Enter')
  await expect(panel.getByRole('region', { name: '送單' })).toBeVisible({ timeout: 15_000 })
  await expect(panel.getByRole('button', { name: '送出' })).toBeVisible()

  await input.fill('幫我加一個動畫的索引站')
  await input.press('Enter')
  const indexer = panel.getByRole('region', { name: '加索引站' })
  await indexer.getByRole('button', { name: '確認加入' }).click()
  await expect(indexer.getByText('已加入 dmhy。')).toBeVisible()

  // 抬頭列的「活動」；窄版的面板取代頁面，按了就收起來。
  await panel.getByRole('link', { name: '活動' }).click()
  await expect(page).toHaveURL('/ai-activity')
  if (narrow(page)) await expect(panel).toHaveCount(0)
  const main = page.locator('main#main')
  await expect(main.getByRole('heading', { level: 1, name: 'AI 活動' })).toBeVisible()
  if (!narrow(page)) {
    await expect(page.getByRole('navigation').getByRole('link', { name: 'AI 活動' })).toBeVisible()
  }

  // 新的在前：先是確認過的加索引站，再是 AI 直接做的送單。讀取的工具（缺集、搜尋）不列。
  const rows = main.getByRole('article')
  await expect(rows).toHaveCount(2)
  const added = rows.nth(0)
  await expect(added.getByRole('heading', { name: 'dmhy' })).toBeVisible()
  await expect(added.getByText('skipper 確認的')).toBeVisible()
  await expect(added.getByText('這一件做了就撤不回。')).toBeVisible()
  const sent = rows.nth(1)
  await expect(sent.getByRole('heading', { name: /^\[ANi\]/ })).toBeVisible()
  await expect(sent.getByText('AI 代 skipper 做的')).toBeVisible()
  await expect(sent.getByText('這一筆符合，而且正是缺的那幾集。')).toBeVisible()
  await expect(sent.getByText(/這次回覆 [\d,]+ tokens/)).toBeVisible()
  await sent.getByText('輸入').click()
  await expect(sent.getByText('source_id')).toBeVisible()
  await shot(page, 'activity')

  await sent.getByRole('button', { name: '撤銷送單' }).click()
  await expect(sent.getByText(/從 qBittorrent 移除這個 torrent/)).toBeVisible()
  await shot(page, 'undo-confirm')
  await sent.getByRole('button', { name: '撤銷送單' }).last().click()
  await expect(sent.getByText('已撤銷')).toBeVisible()
  await expect(sent.getByRole('button', { name: '撤銷送單' })).toHaveCount(0)
  await shot(page, 'undone')

  // 自己的對話連得回去：側面板打開那一則，送單卡照撤銷那一則說已撤銷。
  await sent.getByRole('button', { name: '出自對話「這部缺的集搜一下並下載」' }).click()
  const reopened = page.getByRole('complementary', { name: '助理' })
  await expect(
    reopened.getByRole('region', { name: '送單' }).getByText(/已撤銷這次送單/),
  ).toBeVisible()
  await shot(page, 'conversation')
})
