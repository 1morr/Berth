import { test, type Page } from '@playwright/test'

/**
 * 走到哪裡留一張整頁截圖（票 06h：精靈的驗收截圖）。檔案在 `test-results/<這一條>/<name>.png`，
 * 通過的那一輪也留著（`preserveOutput` 預設 `always`），1280 與 390 各在自己那一條的目錄。
 */
export async function shot(page: Page, name: string): Promise<void> {
  await page.screenshot({ path: test.info().outputPath(`${name}.png`), fullPage: true })
}
