import { expect, test } from '@playwright/test'

import { ADMIN, signIn } from './login.ts'
import { shot } from './shot.ts'

// `bundled`：乾淨的 compose，三個服務都判為套件內（plan §9.3）。八步走完、中途回頭再往前、關掉精靈，
// 再以第 1 步那組帳密登入——那組帳密是精靈第 3 步替 Jellyfin 建的管理員。
// 每一個泊位做完都停在結果上，按了才走（票 06d）；走的是 1280 與 390 兩種寬度（`playwright.config.ts`）。
test('精靈八步走完，之後以同一組帳密登入', async ({ page }) => {
  await page.goto('/')
  await expect(page).toHaveURL('/setup')

  // 1. 管理員
  await page.getByRole('textbox', { name: '帳號' }).fill(ADMIN.user)
  await page.getByRole('textbox', { name: '密碼' }).fill(ADMIN.password)
  await shot(page, '1-admin')
  await page.getByRole('button', { name: '建立管理員' }).click()

  // 2. 偵測服務：三個都是套件內，畫面停在第 2 步等人按「前往泊位 1」。
  await page.getByRole('button', { name: '開始探測' }).click()
  await expect(page.getByText('3 個服務已判定')).toBeVisible()
  await shot(page, '2-detect')
  await page.getByRole('button', { name: '前往泊位 1' }).click()

  // 3. Jellyfin 全自動接手。靠泊之前先改要建的媒體庫（票 06f）：Movies 改名、加一個、刪 Anime。
  await expect(page.getByRole('heading', { name: '接手這台 Jellyfin' })).toBeVisible()
  // 資料夾跟著名稱走，名稱不是英文字母時要自己填（票 06f）。
  await page
    .getByRole('group', { name: 'Movies' })
    .getByRole('textbox', { name: '名稱' })
    .fill('電影')
  const films = page.getByRole('group', { name: '電影' })
  await expect(films.getByRole('alert')).toHaveText(/資料夾要自己填/)
  await films.getByRole('textbox', { name: '資料夾' }).fill('movies')
  await expect(films.getByRole('alert')).toHaveCount(0)
  await page.getByRole('button', { name: '加一個媒體庫' }).click()
  // 那一列的名字就是它的組名，所以名稱最後填。
  const added = page.getByRole('group', { name: '第 4 個媒體庫' })
  await added.getByRole('combobox', { name: '內容類型' }).selectOption({ label: '電影' })
  await added.getByRole('textbox', { name: '資料夾' }).fill('documentaries')
  await added.getByRole('textbox', { name: '名稱' }).fill('紀錄片')
  await page.getByRole('button', { name: '移除「Anime」' }).click()
  await expect(page.getByRole('group', { name: 'Anime' })).toHaveCount(0)
  await shot(page, '3-libraries')
  await page.getByRole('button', { name: '開始靠泊' }).click()
  await expect(page.getByText(/3 個媒體庫/)).toBeVisible()
  await shot(page, '3-jellyfin')
  await page.getByRole('button', { name: '前往下一個泊位' }).click()

  // 4. qBittorrent
  await expect(page.getByRole('heading', { name: '套用建議的 qBittorrent 設定' })).toBeVisible()
  await page.getByRole('button', { name: /^套用這 \d+ 個鍵$/ }).click()
  await expect(page.getByRole('button', { name: '前往下一個泊位' })).toBeVisible()
  await shot(page, '4-qbittorrent')
  await page.getByRole('button', { name: '前往下一個泊位' }).click()

  // 5. 媒體庫路徑：套件內走到就自動建 Route、跑五條檢查（票 06d），沒有要按的鍵。一個媒體庫一條，
  //    清單上改過的名字就是 Route 的名字。後端要每一條的五條纜繩都綠才把步驟推到 6（plan §9.3），
  //    所以「前往下一個泊位」出現就是全綠。
  await expect(page.getByRole('heading', { name: '媒體庫路徑' })).toBeVisible()
  await expect(page.getByRole('button', { name: '重新檢查 3 條 Route' })).toBeVisible()
  await expect(page.getByText('berth-紀錄片', { exact: true })).toBeVisible()
  await shot(page, '5-routes')
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
  await shot(page, '6-indexers')
  await page.getByRole('button', { name: '前往下一個泊位' }).click()

  // 7. TMDB（替身認得任何一把 key）
  await expect(page.getByRole('heading', { name: 'TMDB', level: 2 })).toBeVisible()
  await page.getByRole('textbox', { name: '你的 TMDB API key' }).fill('0'.repeat(31) + '1')
  await page.getByRole('button', { name: '測試 TMDB' }).click()
  await expect(page.getByRole('button', { name: '前往下一個泊位' })).toBeVisible()
  await shot(page, '7-tmdb')
  await page.getByRole('button', { name: '前往下一個泊位' }).click()

  // 中途回頭再往前：板上點回泊位 1，一顆鍵回到目前這一步；上一個泊位、再前往下一個也回得來。
  await expect(page.getByRole('heading', { name: '完成設定' })).toBeVisible()
  const board = page.getByRole('region', { name: '泊位板' })
  await board.getByRole('button', { name: /BTH 1/ }).click()
  await expect(page.getByRole('heading', { name: '接手這台 Jellyfin' })).toBeVisible()
  // 建好的列鎖住，改名刪除去 Jellyfin（票 06f）。
  await expect(page.getByText('已建立', { exact: true })).toHaveCount(3)
  await page.getByRole('button', { name: '回到目前這一步' }).click()
  await expect(page.getByRole('heading', { name: '完成設定' })).toBeVisible()
  await page.getByRole('button', { name: '上一個泊位' }).click()
  await expect(page.getByRole('heading', { name: 'TMDB', level: 2 })).toBeVisible()
  await page.getByRole('button', { name: '前往下一個泊位' }).click()

  // 8. 完成
  await expect(page.getByRole('heading', { name: '完成設定' })).toBeVisible()
  await expect(page.getByText('已繫上')).toHaveCount(3)
  await expect(page.getByText(/剛才建立的 Jellyfin 管理員帳號/)).toBeVisible()
  await shot(page, '8-complete')
  await page.getByRole('button', { name: '完成設定' }).click()

  // 精靈關掉之後 `/` 要登入，不再導向精靈。
  await expect(page).toHaveURL(/\/login/)
  await signIn(page, '/jobs')
  await expect(page.getByRole('heading', { name: '下載', level: 1 })).toBeVisible()
  await page.goto('/')
  await expect(page).toHaveURL('/')
})
