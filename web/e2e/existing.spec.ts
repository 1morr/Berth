import { expect, test } from '@playwright/test'

import { ADMIN } from './login.ts'
import { shot } from './shot.ts'

/** `mixed` 那台既有 Jellyfin 的管理員（`scripts/fake_setup_server.py` 的 `nas_jellyfin`）。 */
const OWNER = { user: 'owner', password: 's3cret' } as const

// `mixed`：NAS 的常見組合（plan §9.3）。既有 Jellyfin 跑過自己的精靈、兩個媒體庫；qBittorrent 設了
// 密碼；Prowlarr 已經有站。精靈不建也不改使用者的東西，只接上去：填 qBittorrent 的帳密、登入
// Jellyfin 換一把 API key、替媒體庫加一條 Berth 路徑並選它當寫入目標、貼 Prowlarr 的 key。
test('既有服務：接上三個服務、選寫入目標，完成後用那台 Jellyfin 的帳號登入', async ({ page }) => {
  await page.goto('/')
  await expect(page).toHaveURL('/setup')

  // 1. 管理員：帳號之後交給 Jellyfin（票 06c），剖面說三個服務都不建立、不寫入要等第 2 步判定。
  await page.getByRole('textbox', { name: '帳號' }).fill(ADMIN.user)
  await page.getByRole('textbox', { name: '密碼' }).fill(ADMIN.password)
  await page.getByRole('button', { name: '建立管理員' }).click()

  // 2. 偵測：三個都是既有。qBittorrent 要帳密，填了才判定完成。
  await page.getByRole('button', { name: '開始探測' }).click()
  const qbittorrent = page
    .getByRole('listitem')
    .filter({ has: page.getByText('qBittorrent', { exact: true }) })
  await expect(qbittorrent.getByText('要求帳密')).toBeVisible()
  await qbittorrent.getByRole('textbox', { name: '帳號' }).fill('admin')
  await qbittorrent.getByRole('textbox', { name: '密碼' }).fill('adminadmin')
  await qbittorrent.getByRole('button', { name: '測試連線' }).click()
  await expect(qbittorrent.getByText('連線測試通過')).toBeVisible()
  await expect(page.getByText('3 個服務已判定')).toBeVisible()
  await shot(page, '2-detect')
  await page.getByRole('button', { name: '前往泊位 1' }).click()

  // 3. 既有 Jellyfin：用那台的管理員換一把 API key，替「電影」加一條 Berth 路徑（就地確認）。
  await expect(page.getByRole('heading', { name: '接入你的 Jellyfin' })).toBeVisible()
  await page.getByRole('textbox', { name: 'Jellyfin 管理員帳號' }).fill(OWNER.user)
  await page.getByRole('textbox', { name: 'Jellyfin 管理員密碼' }).fill(OWNER.password)
  await page.getByRole('button', { name: '登入並建立 API key' }).click()
  const film = page.getByRole('listitem').filter({ hasText: '/nas/movies' })
  await film.getByRole('button', { name: '加入 Berth 路徑' }).click()
  await film.getByRole('button', { name: '確認加入' }).click()
  await expect(film.getByRole('button', { name: '加入 Berth 路徑' })).toHaveCount(0)
  await shot(page, '3-jellyfin')
  await page.getByRole('button', { name: '前往下一個泊位' }).click()

  // 4. 既有 qBittorrent：只寫那五個鍵，WebUI 帳密不動。
  await expect(page.getByRole('heading', { name: '套用建議的 qBittorrent 設定' })).toBeVisible()
  await page.getByRole('button', { name: '套用這 5 個鍵' }).click()
  await expect(page.getByRole('button', { name: '前往下一個泊位' })).toBeVisible()
  await shot(page, '4-qbittorrent')
  await page.getByRole('button', { name: '前往下一個泊位' }).click()

  // 5. 勾「電影」、選剛加的 Berth 路徑當寫入目標；「Anime」不交給 Berth。
  await expect(page.getByRole('heading', { name: '媒體庫路徑' })).toBeVisible()
  await page.getByRole('checkbox', { name: '電影' }).check()
  await page.getByRole('radio', { name: /data\/library\/電影$/ }).check()
  await page.getByRole('button', { name: '建立 1 條 Route 並檢查' }).click()
  await expect(page.getByRole('button', { name: '前往下一個泊位' })).toBeVisible()
  await shot(page, '5-routes')
  await page.getByRole('button', { name: '前往下一個泊位' }).click()

  // 6. 既有 Prowlarr：貼它的 key，列出它已經有的站，試搜。
  await expect(page.getByRole('heading', { name: '索引站', level: 2 })).toBeVisible()
  const main = page.getByRole('main')
  await main.getByRole('textbox', { name: '位址' }).fill('http://prowlarr:9696')
  await main.getByRole('textbox', { name: 'API key' }).fill('0123456789abcdef0123456789abcdef')
  await main.getByRole('button', { name: '測試連線' }).click()
  await main.getByRole('button', { name: '試搜' }).click()
  await expect(page.getByTestId('trial').getByText(/\d+ 筆/)).toBeVisible()
  await shot(page, '6-indexers')
  await page.getByRole('button', { name: '前往下一個泊位' }).click()

  // 7. TMDB
  await page.getByRole('textbox', { name: '你的 TMDB API key' }).fill('0'.repeat(31) + '1')
  await page.getByRole('button', { name: '測試 TMDB' }).click()
  await page.getByRole('button', { name: '前往下一個泊位' }).click()

  // 8. 完成：管理員不是精靈建的，登入提示說的是那台 Jellyfin 自己的帳號。
  await expect(page.getByRole('heading', { name: '完成設定' })).toBeVisible()
  await expect(page.getByText('已繫上')).toHaveCount(1)
  await expect(page.getByText(/你那台 Jellyfin 的帳號/)).toBeVisible()
  await shot(page, '8-complete')
  await page.getByRole('main').getByRole('button', { name: '完成設定' }).click()

  await expect(page).toHaveURL(/\/login/)
  await page.getByRole('textbox', { name: '帳號' }).fill(OWNER.user)
  await page.getByRole('textbox', { name: '密碼' }).fill(OWNER.password)
  await page.getByRole('button', { name: '登入' }).click()
  await expect(page.getByRole('heading', { name: '媒體庫', level: 1 })).toBeVisible()
})
