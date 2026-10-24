import { copyFileSync, mkdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { expect, test } from '@playwright/test'

import { blankAndOverflow } from './layout.ts'
import { signIn } from './login.ts'
import { shot } from './shot.ts'

// `weekly`：產品自己的 `compose_weekly` 產生最近兩週（M4 票 131）。上一週入庫一部、什麼都沒修、
// 沒有等人的；最新一週入庫三部（芙莉蓮、一部作品名很長的、一部電影），修了九件，產生當下等著七件。
test('/weekly 從導覽進去，看最新一週三段、翻到上一週、找不到的那一週', async ({ page }) => {
  await signIn(page, '/health')
  await page
    .getByRole('navigation', { name: '主要導覽' })
    .getByRole('link', { name: '週報' })
    .click()
  await expect(page).toHaveURL('/weekly')
  await expect(page.getByRole('heading', { level: 1, name: '週報' })).toBeVisible()

  // 入庫：季集範圍與通知同一個寫法，電影是中性色塊，長作品名換行不撐開頁面。
  const imported = page.getByRole('region', { name: '入庫' })
  await expect(imported.getByText('3 部 · 7 集')).toBeVisible()
  await expect(imported.getByRole('link', { name: '葬送的芙莉蓮' })).toBeVisible()
  await expect(imported.getByText('S01E01–E03, E05, S02E01')).toBeVisible()
  await expect(imported.getByText('S01E01–E02', { exact: true })).toBeVisible()
  await expect(imported.getByText('電影')).toBeVisible()
  await expect(imported.getByRole('link', { name: /不太可能成為一部作品名這麼長/ })).toBeVisible()

  // 修了什麼：0 的不列。
  const fixed = page.getByRole('region', { name: '修了什麼' })
  await expect(fixed.getByText('9 件')).toBeVisible()
  await expect(fixed.getByText('缺集')).toHaveCount(0)
  await expect(fixed.getByText('檔案遺失 ×2、鏈接遺失')).toBeVisible()
  await expect(fixed.getByText('已被移除')).toBeVisible()

  // 還有什麼等人：每一種連到自己的頁面，巡檢開的另列。
  const waiting = page.getByRole('region', { name: '還有什麼等人' })
  await expect(waiting.getByText('7 件')).toBeVisible()
  await expect(waiting.getByText('巡檢開出的')).toBeVisible()
  await expect(waiting.getByRole('link', { name: '打開待審核' })).toHaveAttribute('href', '/review')
  await expect(waiting.getByRole('link', { name: '打開Issue' })).toHaveAttribute('href', '/issues')
  await expect(waiting.getByRole('link', { name: /^打開RSS/ })).toHaveAttribute('href', '/rss')

  // 歷史清單：最新這一週是目前這一頁，上一週是連結。
  const history = page.getByRole('navigation', { name: '歷來的週報' })
  await expect(history.locator('[aria-current="page"]')).toHaveCount(1)
  await expect(history.locator('[aria-current="page"]')).toContainText('入庫 3')
  await expect(history.getByRole('link')).toHaveCount(1)

  const layout = await blankAndOverflow(page)
  expect(layout.overflow).toBe(false)

  await shot(page, 'weekly')
  const width = page.viewportSize()?.width ?? 1280
  const target = fileURLToPath(
    new URL(`../../.scratch/m4/issues/131-weekly-report/weekly-${width}.png`, import.meta.url),
  )
  mkdirSync(
    fileURLToPath(new URL('../../.scratch/m4/issues/131-weekly-report/', import.meta.url)),
    {
      recursive: true,
    },
  )
  copyFileSync(test.info().outputPath('weekly.png'), target)

  // 翻到上一週：網址換成那一份的 id，內容也換了。
  await history.getByRole('link').click()
  await expect(page).toHaveURL('/weekly/1')
  await expect(imported.getByText('1 部 · 4 集')).toBeVisible()
  await expect(imported.getByText('S01E01–E04')).toBeVisible()
  await expect(imported.getByRole('link', { name: '葬送的芙莉蓮' })).toHaveCount(0)
  await expect(page.getByText('這一週沒有修正。')).toBeVisible()
  await expect(page.getByText('產生時沒有等你處理的事。')).toBeVisible()
  await expect(history.locator('[aria-current="page"]')).toContainText('入庫 1')

  // 沒有這一週。
  await page.goto('/weekly/999')
  await expect(page.getByText('沒有這一週的週報。')).toBeVisible()
  await page.getByRole('link', { name: '看最新一週' }).click()
  await expect(page).toHaveURL('/weekly')
})
