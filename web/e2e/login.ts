import { expect, type Page } from '@playwright/test'

/** 演練情境的管理員（`scripts/fake_setup_server.py` 的 `healthy` 以降，精靈走完後也是這一組）。 */
export const ADMIN = { user: 'skipper', password: 'harbour' } as const

/** 從登入頁登入，落在 `path`。 */
export async function signIn(page: Page, path: string): Promise<void> {
  await page.goto(`/login?redirect=${encodeURIComponent(path)}`)
  await page.getByRole('textbox', { name: '帳號' }).fill(ADMIN.user)
  await page.getByRole('textbox', { name: '密碼' }).fill(ADMIN.password)
  await page.getByRole('button', { name: '登入' }).click()
  await expect(page).toHaveURL(path)
}
