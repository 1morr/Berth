import { expect, test } from '@playwright/test'

import { signIn } from './login.ts'
import { shot } from './shot.ts'

// `agent`：同 `downloads`（SPY×FAMILY 的五筆下載，`- 01` 停在待審核），另外 AI 開著、模型是照腳本回答的
// 替身（`scripts/fake_setup_server.py` 的 `why_not_script`）：先搜尋作品、再叫「為什麼沒入庫」，用工具結果的
// 結論分類回答。一個請求都不出網、不需要金鑰（M5 票 12）。桌機與手機各跑一次（playwright.config.ts）。

test('側面板問「為什麼沒入庫」得到結論，重新載入之後對話還在', async ({ page }) => {
  // 回覆裡的外部圖片一次都不能被請求（brief §14：圖片網址是外洩通道）。
  const outside: string[] = []
  page.on('request', (request) => {
    if (new URL(request.url()).hostname === 'tracker.example') outside.push(request.url())
  })

  await signIn(page, '/jobs')
  const toggle = page.getByRole('button', { name: '助理' })
  await toggle.click()
  await expect(toggle).toHaveAttribute('aria-expanded', 'true')

  const panel = page.locator('#agent-panel')
  const input = panel.getByRole('textbox', { name: '問助理' })
  await expect(input).toBeFocused()
  await input.fill('SPY×FAMILY 為什麼沒入庫')
  await input.press('Enter')

  const log = panel.getByRole('log', { name: '助理' })
  // 工具收成一行：先搜尋、再查為什麼沒入庫，都完成。
  const search = log.locator('details').filter({ hasText: '搜尋作品' })
  const why = log.locator('details').filter({ hasText: '查為什麼沒入庫' })
  await expect(search).toContainText('完成')
  await expect(why).toContainText('完成')
  // 票 10 的結論分類：`- 01` 停在待審核。
  await expect(log).toContainText('下載完了，停在審核等管理員（結論 awaiting_review）')
  await expect(log).toContainText('S01E01')
  // 展開看參數與結果的原文。
  await why.locator('summary').click()
  await expect(why).toContainText('"media_id": "tv:120089"')
  await expect(why).toContainText('"conclusion": "awaiting_review"')
  await shot(page, 'answered')

  await expectNoHorizontalScroll(page)

  // 重新載入：面板照舊開著（記在這個分頁），對話從伺服器接回來。
  await page.reload()
  await expect(panel.getByRole('log', { name: '助理' })).toContainText('awaiting_review')
  await expect(panel.getByRole('log', { name: '助理' })).toContainText('SPY×FAMILY 為什麼沒入庫')
  await shot(page, 'reloaded')

  // 換頁：桌機上兩邊都能操作，面板與對話跟著走。
  if ((page.viewportSize()?.width ?? 0) >= 1024) {
    await page
      .getByRole('navigation', { name: '主要導覽' })
      .getByRole('link', { name: '健康' })
      .click()
    await expect(page).toHaveURL('/health')
    // 網址先換、頁面後畫：等健康頁真的畫出來，才不會在轉場的那一瞬間打字。
    await expect(page.getByRole('heading', { level: 1, name: '健康' })).toBeVisible()
    await expect(panel.getByRole('log', { name: '助理' })).toContainText('awaiting_review')
  }

  // 外部圖片：畫成「沒有載入」與網址原文，不是 `<img>`。
  await input.fill('給我一張圖片')
  await input.press('Enter')
  await expect(panel.getByText('圖片沒有載入')).toBeVisible()
  await expect(panel.getByText('https://tracker.example/pixel.png')).toBeVisible()
  await expect(panel.locator('img')).toHaveCount(0)
  expect(outside).toEqual([])

  // 收起：Esc，焦點回到頁首那顆鍵。
  await input.press('Escape')
  await expect(page.getByRole('button', { name: '助理' })).toBeFocused()
  await expect(panel).toHaveCount(0)
})

test('斜線指令：打 / 給提示，/usage 看用量，/compact 換成摘要，重新載入之後摘要還在', async ({
  page,
}) => {
  await signIn(page, '/jobs')
  await page.getByRole('button', { name: '助理' }).click()
  const panel = page.locator('#agent-panel')
  const input = panel.getByRole('textbox', { name: '問助理' })
  const log = panel.getByRole('log', { name: '助理' })

  // 兩輪：`/compact` 只留最後一個，第一個換成摘要（M5 票 18）。
  await input.fill('SPY×FAMILY 為什麼沒入庫')
  await input.press('Enter')
  await expect(log).toContainText('awaiting_review')
  await input.fill('給我一張圖片')
  await input.press('Enter')
  await expect(panel.getByText('圖片沒有載入')).toBeVisible()

  // 打 `/`：輸入欄上方列出六個指令，上下鍵移動。
  await input.fill('/')
  const hint = panel.getByRole('listbox', { name: '指令' })
  await expect(hint.getByRole('option')).toHaveCount(6)
  await input.press('ArrowDown')
  await input.press('ArrowDown')
  await expect(hint.getByRole('option', { selected: true })).toContainText('/usage')
  await expect(input).toBeFocused()
  await shot(page, 'slash-hint')
  await expectNoHorizontalScroll(page)

  // Enter 先補完選到的那一個，再按一次才執行：不經過模型，結果接在對話後面。
  await input.press('Enter')
  await expect(input).toHaveValue('/usage')
  await input.press('Enter')
  const usage = log.getByRole('region', { name: '/usage' })
  await expect(usage.getByText('回覆')).toBeVisible()
  await expect(usage).toContainText('模型呼叫')
  await expect(hint).toHaveCount(0)
  await expect(input).toHaveValue('')
  await shot(page, 'slash-usage')

  await input.fill('/compact')
  await input.press('Enter')
  await expect(log).toContainText('已壓縮')
  const summary = log.locator('details').filter({ hasText: '較早的對話已壓縮成這段摘要' })
  await expect(summary).toBeVisible()
  // 第一輪的那則訊息不在了（它只剩摘要裡的一句）。
  await expect(log.getByText('SPY×FAMILY 為什麼沒入庫', { exact: true })).toHaveCount(0)
  await expect(log.getByText('給我一張圖片', { exact: true })).toBeVisible()
  await summary.locator('summary').click()
  await expect(summary).toContainText('使用者問過：SPY×FAMILY 為什麼沒入庫')
  await shot(page, 'slash-compacted')

  // 指令的結果只在這個分頁；壓縮後的歷史在伺服器上。
  await page.reload()
  await expect(
    panel.getByRole('log', { name: '助理' }).getByText('較早的對話已壓縮成這段摘要'),
  ).toBeVisible()
  await expect(panel.getByRole('region', { name: '/usage' })).toHaveCount(0)
})

async function expectNoHorizontalScroll(page: import('@playwright/test').Page) {
  const overflow = await page.evaluate(
    '[document.documentElement.scrollWidth, window.innerWidth, document.querySelector("#agent-panel").scrollWidth, document.querySelector("#agent-panel").clientWidth]',
  )
  const [pageWidth, viewport, panelWidth, panelClient] = overflow as number[]
  expect(pageWidth).toBeLessThanOrEqual(viewport)
  expect(panelWidth).toBeLessThanOrEqual(panelClient)
}
