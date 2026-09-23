import { expect, test } from '@playwright/test'

import { signIn } from './login.ts'

// `import`：精靈已跑完，TMDB、索引站、qBittorrent 都是替身，一個請求都不出網。替身
// qBittorrent 收下 torrent 就把檔案寫進 save path 並報成 100%，之後的 poller、規劃、
// 入庫、帳本全是產品自己的程式碼（plan §3.1）。
test('從作品頁送單，一路走到已入庫', async ({ page }) => {
  await signIn(page, '/media/tv:120089')

  const search = page.getByRole('region', { name: '搜尋 torrent' })
  await search.getByRole('combobox', { name: '入庫到' }).selectOption('Anime')
  await search.getByRole('button', { name: '搜尋' }).click()

  const release = search.getByRole('row').filter({ hasText: '[Berth-Demo] SPY×FAMILY S01' })
  await release.getByRole('button', { name: '送單' }).click()
  await search.getByRole('button', { name: '確認送單' }).click()
  await expect(release.getByRole('status')).toContainText('已送出')

  await release.getByRole('link', { name: '看下載列表' }).click()
  await expect(page).toHaveURL('/jobs')
  const job = page.getByRole('listitem').filter({ hasText: '[Berth-Demo] SPY×FAMILY S01' })
  // 下載完成 → 規劃 → 入庫靠 poller 的提示接力，實測幾秒；上限放寬到一輪規劃器的間隔。
  await expect(job).toContainText('已入庫', { timeout: 60_000 })

  // 作品頁的「檔案與版本」讀帳本：三集正片、一個特典、一條字幕都在，而且帳本對得上。
  await page.goto('/media/tv:120089')
  const files = page.getByRole('region', { name: '檔案與版本' })
  await expect(files).toContainText('共 5 個檔案')
  await expect(files.getByRole('group').filter({ hasText: '正片' })).toContainText('E01–E03')
  await expect(files.getByRole('group').filter({ hasText: '帳本對得上' })).toHaveCount(3)
})
