import { expect, test, type Page } from '@playwright/test'

import { signIn } from './login.ts'

/**
 * 按「立刻對帳」並等那一輪跑完。POST 回 202 只說收下了，那一輪在背景跑（`api/issues.py`），
 * 所以照前端的做法輪詢 `GET /api/reconcile`，等 `last` 是這一輪、`current` 清空。
 */
async function reconcile(page: Page): Promise<void> {
  const started = page.waitForResponse(
    (response) =>
      response.url().endsWith('/api/reconcile') && response.request().method() === 'POST',
  )
  await page.getByRole('button', { name: '立刻對帳' }).click()
  const response = await started
  expect(response.status()).toBe(202)
  const { id } = (await response.json()) as { id: number }
  await expect
    .poll(async () => {
      const state = (await (await page.request.get('/api/reconcile')).json()) as {
        current: unknown
        last: { id: number } | null
      }
      return state.current === null && state.last?.id === id
    })
    .toBe(true)
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

// Jellyfin 回驗（M3 票 17）：第一集反查過了，替身 Jellyfin 把它認成 `S01E01-E02`（兩份不同範圍
// 的正片被併成一集）。對帳的 Jellyfin 那一方比到它，開出一件回驗不符，列上並排兩邊的讀法。
test('/issues 畫出 jellyfin_item_mismatch 並按得到重新反查', async ({ page }) => {
  await signIn(page, '/issues')

  const mismatch = page.getByRole('listitem').filter({ hasText: '回驗不符' })
  await reconcile(page)
  await expect(mismatch).toHaveCount(1)
  await mismatch.getByText('展開').click()
  await expect(mismatch.getByText('S01E01 · TMDB 120089')).toBeVisible()
  await expect(mismatch.getByText('S01E01-E02 · TMDB 120089')).toBeVisible()

  await mismatch.getByRole('button', { name: '重新反查' }).click()
  await expect(mismatch).toHaveCount(0)
})
