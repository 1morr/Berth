import type { Page } from '@playwright/test'

/**
 * 在 `/rss` 的新增表單加一個 Feed（M4 票 105）。演練情境的 TV 與 Anime 兩條都收劇集，所以劇集那一格
 * 一定要選（沒有「不指定」）；電影只有 Movies，表單預填它。
 */
export async function addFeed(
  page: Page,
  url: string,
  { name = '', series = 'Anime' }: { name?: string; series?: string } = {},
): Promise<void> {
  await page.getByLabel(/RSS 網址/).fill(url)
  if (name) await page.getByLabel(/名稱/).fill(name)
  await page.getByRole('combobox', { name: '劇集送進' }).selectOption(series)
  await page.getByRole('button', { name: '加入', exact: true }).click()
}
