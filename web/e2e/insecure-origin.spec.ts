import { expect, test } from '@playwright/test'

import { signIn } from './login.ts'
import { shot } from './shot.ts'

// `insecure-origin`：使用者多半用區網 IP 走 HTTP 開 Berth（`http://192.168.x.x:8383`），那不是 secure context，
// 只在 HTTPS / localhost 才有的 API（`crypto.randomUUID`、`navigator.clipboard`…）都是 `undefined`。其他專案都開
// `http://127.0.0.1`——瀏覽器把它當 secure context——0.4.0 的 `crypto.randomUUID` crash 因此綠著出貨。
// 這一條開 `http://berth.test:<port>`（Chromium 的 `--host-resolver-rules` 指回本機，playwright.config.ts），
// 情境同 `agent`：登入、問助理、複製一個 hash。

test('用不是 localhost 的 HTTP 網址開：整個 App、助理面板與複製都照常', async ({ page }) => {
  const crashes: string[] = []
  page.on('pageerror', (error) => crashes.push(error.message))

  await signIn(page, '/jobs')
  // 先證明這一條真的在 HTTP 下跑：設定被改回 127.0.0.1，這裡就紅，不會悄悄變成另一條普通的流程。
  // 字串而不是函式：e2e 的 tsconfig 沒有 DOM 型別（同 agent.spec.ts）。
  expect(
    await page.evaluate(
      '[window.isSecureContext, typeof crypto.randomUUID, typeof navigator.clipboard]',
    ),
  ).toEqual([false, 'undefined', 'undefined'])

  const toggle = page.getByRole('button', { name: '助理' })
  await toggle.click()
  const panel = page.locator('#agent-panel')
  const input = panel.getByRole('textbox', { name: '問助理' })
  await input.fill('SPY×FAMILY 為什麼沒入庫')
  await input.press('Enter')
  await expect(panel.getByRole('log', { name: '助理' })).toContainText('awaiting_review')

  // 「新對話」換一個 id（0.4.0 crash 的那一行）。
  await panel.getByRole('button', { name: '新對話' }).click()
  await expect(panel.getByRole('log', { name: '助理' })).not.toContainText('awaiting_review')
  await toggle.click()

  // 剪貼簿 API 不在：Job 詳情頁的 hash 退回選取再複製，按鍵照樣變成「已複製」。
  // 在頁面裡問：`page.request` 走 Node 那一側，不認 Chromium 的 `--host-resolver-rules`。
  const hash = (await page.evaluate(
    "fetch('/api/jobs?filter=all').then((r) => r.json()).then((body) => body.jobs[0].hash)",
  )) as string
  await page.goto(`/jobs/${hash}`)
  await page.getByRole('button', { name: '複製' }).first().click()
  await expect(page.getByRole('button', { name: '已複製' })).toBeVisible()
  await shot(page, 'copied')

  expect(crashes).toEqual([])
})
