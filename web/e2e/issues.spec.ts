import { expect, test, type Page } from '@playwright/test'

import { signIn } from './login.ts'

/** 按「立刻對帳」並等那一輪跑完（`POST /api/reconcile` 回來時四方已比完、Issue 已寫下）。 */
async function reconcile(page: Page): Promise<void> {
  const done = page.waitForResponse(
    (response) =>
      response.url().endsWith('/api/reconcile') && response.request().method() === 'POST',
  )
  await page.getByRole('button', { name: '立刻對帳' }).click()
  expect((await done).ok()).toBe(true)
}

// `issues`：一包真的入庫完的三集，第二集的媒體庫檔案被刪掉了（M2 票 05）。對帳開出
// `library_link_missing`，「重新鏈接」真的 `os.link` 接回來——所以再對一次帳它不會再開。
test('/issues 修一條 library_link_missing', async ({ page }) => {
  await signIn(page, '/issues')

  const missing = page
    .getByRole('listitem')
    .filter({ hasText: '鏈接遺失' })
    .filter({ has: page.getByRole('heading', { name: /S01E02/ }) })
  await expect(page.getByRole('button', { name: '立刻對帳' })).toBeVisible()
  await expect(missing).toHaveCount(0)

  await reconcile(page)
  await expect(missing).toHaveCount(1)
  await missing.getByRole('button', { name: '重新鏈接' }).click()
  await expect(missing).toHaveCount(0)

  // 再對一次帳：檔案真的回到媒體庫，這一輪偵測不到它了。
  await reconcile(page)
  await page.reload()
  await expect(page.getByRole('heading', { name: /S01E03/ })).toBeVisible()
  await expect(missing).toHaveCount(0)
})
