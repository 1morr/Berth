import { expect, test } from '@playwright/test'

import { ADMIN, signIn } from './login.ts'

// `bundled`：乾淨的 compose，三個服務都判為套件內（plan §9.3）。八步走完、中途回頭再往前、關掉精靈，
// 再以第 1 步那組帳密登入——那組帳密是精靈第 3 步替 Jellyfin 建的管理員。
test('精靈八步走完，之後以同一組帳密登入', async ({ page }) => {
  await page.goto('/')
  await expect(page).toHaveURL('/setup')

  // 1. 管理員
  await page.getByRole('textbox', { name: '帳號' }).fill(ADMIN.user)
  await page.getByRole('textbox', { name: '密碼' }).fill(ADMIN.password)
  await page.getByRole('button', { name: '建立管理員' }).click()

  // 2. 偵測服務：三個都是套件內，畫面停在第 2 步等人按「前往泊位 1」。
  await page.getByRole('button', { name: '開始探測' }).click()
  await page.getByRole('button', { name: '前往泊位 1' }).click()
  await expect(page.getByText('3 個服務已判定')).toBeVisible()

  // 3. Jellyfin 全自動接手。每一個泊位做完都停在結果上，按了才走（票 06d）。
  await expect(page.getByRole('heading', { name: '接手這台 Jellyfin' })).toBeVisible()
  await page.getByRole('button', { name: '開始靠泊' }).click()
  await page.getByRole('button', { name: '前往下一個泊位' }).click()

  // 4. qBittorrent
  await expect(page.getByRole('heading', { name: '套用建議的 qBittorrent 設定' })).toBeVisible()
  await page.getByRole('button', { name: /^套用這 \d+ 個鍵$/ }).click()
  await page.getByRole('button', { name: '前往下一個泊位' }).click()

  // 5. 媒體庫路徑：套件內走到就自動建三條 Route、跑五條檢查（票 06d），沒有要按的鍵。
  //    後端要每一條的五條纜繩都綠才把步驟推到 6（plan §9.3），所以「前往下一個泊位」出現就是全綠。
  await expect(page.getByRole('heading', { name: '媒體庫路徑' })).toBeVisible()
  await expect(page.getByRole('button', { name: '重新檢查 3 條 Route' })).toBeVisible()
  await page.getByRole('button', { name: '前往下一個泊位' }).click()

  // 6. 索引站（九個裡有四個連不上是常態）。加入 → 試搜 → 不要的移除（票 06e）；
  //    替身的 Mikan 演「搜尋時連不上」，其餘站照樣列出筆數。
  await expect(page.getByRole('heading', { name: '索引站', level: 2 })).toBeVisible()
  await page.getByRole('button', { name: '加入這 9 個站' }).click()
  await page.getByRole('button', { name: '試搜' }).click()
  const trial = page.getByTestId('trial')
  await expect(trial.getByText(/502 Bad Gateway/)).toBeVisible()
  const yts = trial.getByRole('listitem').filter({ hasText: 'YTS' }).first()
  await expect(yts.getByText(/\d+ 筆/)).toBeVisible()
  await yts.getByRole('button', { name: '移除' }).click()
  await yts.getByRole('button', { name: '確定移除' }).click()
  await expect(trial.getByText('YTS', { exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: '前往下一個泊位' }).click()

  // 7. TMDB（替身認得任何一把 key）
  await expect(page.getByRole('heading', { name: 'TMDB', level: 2 })).toBeVisible()
  await page.getByRole('textbox', { name: '你的 TMDB API key' }).fill('0'.repeat(31) + '1')
  await page.getByRole('button', { name: '測試 TMDB' }).click()
  await page.getByRole('button', { name: '前往下一個泊位' }).click()

  // 中途回頭再往前：板上點回泊位 1，一顆鍵回到目前這一步；上一個泊位、再前往下一個也回得來。
  await expect(page.getByRole('heading', { name: '完成設定' })).toBeVisible()
  const board = page.getByRole('region', { name: '泊位板' })
  await board.getByRole('button', { name: /BTH 1/ }).click()
  await expect(page.getByRole('heading', { name: '接手這台 Jellyfin' })).toBeVisible()
  await page.getByRole('button', { name: '回到目前這一步' }).click()
  await expect(page.getByRole('heading', { name: '完成設定' })).toBeVisible()
  await page.getByRole('button', { name: '上一個泊位' }).click()
  await expect(page.getByRole('heading', { name: 'TMDB', level: 2 })).toBeVisible()
  await page.getByRole('button', { name: '前往下一個泊位' }).click()

  // 8. 完成
  await expect(page.getByRole('heading', { name: '完成設定' })).toBeVisible()
  await expect(page.getByText('已繫上')).toHaveCount(3)
  await page.getByRole('button', { name: '完成設定' }).click()

  // 精靈關掉之後 `/` 要登入，不再導向精靈。
  await expect(page).toHaveURL(/\/login/)
  await signIn(page, '/jobs')
  await expect(page.getByRole('heading', { name: '下載', level: 1 })).toBeVisible()
  await page.goto('/')
  await expect(page).toHaveURL('/')
})
