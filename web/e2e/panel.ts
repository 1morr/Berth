import type { Page } from '@playwright/test'

import { narrow } from './shot.ts'

/**
 * 窄版的側面板不照記憶打開（M5 票 15）：換頁（`goto`）或重整之後，手機寬度要再按一次「助理」，
 * 桌機照記憶開著。
 */
export async function reopenOnNarrow(page: Page): Promise<void> {
  if (narrow(page)) await page.getByRole('button', { name: '助理' }).click()
}
