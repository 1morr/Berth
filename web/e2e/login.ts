import { expect, type Page } from '@playwright/test'

/** 演練情境的管理員（`scripts/fake_setup_server.py` 的 `healthy` 以降，精靈走完後也是這一組）。 */
export const ADMIN = { user: 'skipper', password: 'harbour' } as const

/** 同一份替身 Jellyfin 上的一般使用者（`healthy` 以降）。 */
export const CREW = { user: 'deckhand', password: 'rope' } as const

/** 從登入頁登入，落在 `path`。預設是管理員。 */
export async function signIn(
  page: Page,
  path: string,
  who: { user: string; password: string } = ADMIN,
): Promise<void> {
  await page.goto(`/login?redirect=${encodeURIComponent(path)}`)
  await page.getByRole('textbox', { name: 'Jellyfin 帳號' }).fill(who.user)
  await page.getByRole('textbox', { name: '密碼' }).fill(who.password)
  await page.getByRole('button', { name: '登入' }).click()
  await expect(page).toHaveURL(path)
}
