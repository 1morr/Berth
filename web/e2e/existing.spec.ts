import { expect, test } from '@playwright/test'

import { shot } from './shot.ts'

/** `mixed` 那台既有 Jellyfin 的管理員（`scripts/fake_setup_server.py` 的 `nas_jellyfin`）。 */
const OWNER = { user: 'owner', password: 's3cret' } as const

// `mixed`：NAS 的常見組合（plan §9.3）。既有 Jellyfin 跑過自己的精靈、兩個媒體庫；qBittorrent 設了
// 密碼；Prowlarr 已經有站。三個服務頁都選「既有」（M4 票 15），精靈不建也不改使用者的東西，只接上去：
// 以那台 Jellyfin 的管理員成為擁有者（同時換一把 API key）、填 qBittorrent 的帳密、替媒體庫加一條
// Berth 路徑並選它當寫入目標、貼 Prowlarr 的 key。
test('既有服務：三頁都選既有、選寫入目標，完成後用那台 Jellyfin 的帳號登入', async ({ page }) => {
  const writes: string[] = []
  page.on('request', (request) => {
    // 頁 3 進頁的重讀不算寫入（M4 票 19）：它只向 Jellyfin 讀、換 Berth 自己的媒體庫快照。
    const reread = request.url().endsWith('/api/setup/routes/libraries')
    if (request.method() !== 'GET' && request.url().includes('/api/setup/') && !reread) {
      writes.push(request.url())
    }
  })
  await page.goto('/')
  // 精靈的頁在網址上（M4 票 30）：讀回狀態之後補上 `?step=1`。
  await expect(page).toHaveURL(/\/setup(\?step=1)?$/)

  // 1. Jellyfin 選既有：說出同主機、同容器路徑的條件與要從 COMPOSE_PROFILES 拿掉哪一個；填位址才測。
  await page.getByRole('radio', { name: /既有/ }).click()
  await expect(page.getByText(/同一台主機/).first()).toBeVisible()
  await expect(page.getByText('COMPOSE_PROFILES=qbittorrent,prowlarr')).toBeVisible()
  await page.getByRole('textbox', { name: '位址' }).fill('http://nas:8096')
  await page.getByRole('button', { name: '測試連線' }).click()
  // 那一台跑過自己的精靈：用它的管理員登入。不是這組密碼被拒並說明原因（M4 票 06）。
  await expect(page.getByRole('heading', { name: '用你的 Jellyfin 管理員登入' })).toBeVisible()
  await expect(page.getByRole('textbox', { name: '再輸入一次密碼' })).toHaveCount(0)
  await page.getByRole('textbox', { name: 'Jellyfin 帳號' }).fill(OWNER.user)
  await page.getByRole('textbox', { name: '密碼', exact: true }).fill('not-the-password')
  await page.getByRole('button', { name: '登入', exact: true }).click()
  await expect(page.getByText('Jellyfin 不認這組帳號或密碼。')).toBeVisible()
  await page.getByRole('textbox', { name: '密碼', exact: true }).fill(OWNER.password)
  await shot(page, '1-owner')
  await page.getByRole('button', { name: '登入', exact: true }).click()
  await expect(page.getByRole('heading', { name: '擁有者：owner' })).toBeVisible()
  await page.getByRole('button', { name: '前往下一個泊位' }).click()

  // 2. qBittorrent 選既有：填位址與它的 WebUI 帳密。全域偏好與帳密都不動（M4 票 05），測試通過就做完
  //    （M4 票 38）：沒有確認鍵，也不送任何寫入。
  await page.getByRole('radio', { name: /既有/ }).click()
  const main = page.getByRole('main')
  await main.getByRole('textbox', { name: '位址' }).fill('http://nas:8080')
  await main.getByRole('textbox', { name: '帳號' }).fill('admin')
  await main.getByRole('textbox', { name: '密碼' }).fill('adminadmin')
  await main.getByRole('button', { name: '測試連線' }).click()
  await expect(page.getByRole('heading', { name: '確認你的 qBittorrent' })).toBeVisible()
  // 偏好表整張收起，也不警告未完成目錄：它的全域偏好沒有一個影響 Berth（M4 票 22）。
  await expect(page.getByRole('table')).toHaveCount(0)
  await expect(page.getByText(/沒有啟用未完成目錄/)).toHaveCount(0)
  // 既有的那一台沒有 WebUI 登入那一格（M4 票 07）。
  await expect(page.getByRole('group', { name: 'qBittorrent WebUI 登入' })).toHaveCount(0)
  await expect(page.getByText(/這個泊位的事做完了/)).toBeVisible()
  await expect(page.getByRole('button', { name: /確認|套用/ })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '前往下一個泊位' })).toBeVisible()
  expect(writes.filter((url) => url.endsWith('/api/setup/qbittorrent/apply'))).toEqual([])
  await shot(page, '2-qbittorrent')
  await page.getByRole('button', { name: '前往下一個泊位' }).click()

  // 3. 既有 Jellyfin 不建媒體庫：直接是 Route。進頁不送任何寫入（M4 票 08）。勾「電影」、選「新的 Berth
  //    路徑」當寫入目標——按下「建立並檢查」時才加到 Jellyfin；「Anime」不交給 Berth。
  const arrived = writes.length
  await expect(page.getByRole('heading', { name: '媒體庫路徑' })).toBeVisible()
  await page.waitForLoadState('networkidle')
  expect(writes.slice(arrived)).toEqual([])
  await expect(page.getByText('要建的媒體庫')).toHaveCount(0)
  await page.getByRole('checkbox', { name: '電影' }).check()
  await page.getByRole('radio', { name: /data\/library\/電影$/ }).check()
  await expect(
    page.getByRole('region', { name: '按下之後會' }).getByText(/在 Jellyfin 的「電影」加入路徑/),
  ).toBeVisible()
  expect(writes.slice(arrived)).toEqual([])
  await page.getByRole('button', { name: '建立並檢查' }).click()
  await expect(page.getByRole('button', { name: '前往下一個泊位' })).toBeVisible()
  await shot(page, '3-routes')
  await page.getByRole('button', { name: '前往下一個泊位' }).click()

  // 4. Prowlarr 選既有：貼它的 key，用它已經有的站，試搜；沒有介面登入那一格。
  await expect(page.getByRole('heading', { name: 'Prowlarr', level: 2 })).toBeVisible()
  await page.getByRole('radio', { name: /既有/ }).click()
  await main.getByRole('textbox', { name: '位址' }).fill('http://nas:9696')
  await main.getByRole('textbox', { name: 'API key' }).fill('0123456789abcdef0123456789abcdef')
  await main.getByRole('button', { name: '測試連線' }).click()
  // 它已有的站與站數；沒有移除（M4 票 09）。已經在的站不再列進加站（M4 票 20 起既有的也能加站）。
  const sites = page.getByTestId('added')
  await expect(sites.getByText('2 站')).toBeVisible()
  await expect(main.getByRole('checkbox', { name: 'Nyaa.si' })).toHaveCount(0)
  await expect(sites.getByRole('button', { name: '移除' })).toHaveCount(0)
  await sites.getByRole('button', { name: '搜尋全部' }).click()
  await expect(
    page
      .getByTestId('trial')
      .getByText(/\d+ 筆/)
      .first(),
  ).toBeVisible()
  await expect(page.getByRole('group', { name: 'Prowlarr 介面登入' })).toHaveCount(0)
  await shot(page, '4-indexers')
  await page.getByRole('button', { name: '前往下一個泊位' }).click()

  // 5. TMDB
  await page.getByRole('textbox', { name: '你的 TMDB API key' }).fill('0'.repeat(31) + '1')
  await page.getByRole('button', { name: '測試 TMDB' }).click()
  await page.getByRole('button', { name: '前往下一個泊位' }).click()

  // 6. 完成：之後登入用的是那台 Jellyfin 自己的帳號，擁有者就是它的管理員。
  await expect(page.getByRole('heading', { name: '完成設定' })).toBeVisible()
  await expect(page.getByText('已繫上')).toHaveCount(1)
  await expect(page.getByText(/你是 owner/)).toBeVisible()
  await shot(page, '6-complete')
  await page.getByRole('main').getByRole('button', { name: '完成設定' }).click()

  // Berth 還沒入庫過東西，媒體庫裡只有別人的片：第一件事是找片（M4 票 10，brief §19 2026-09-26）。
  await expect(page).toHaveURL('/')
  await expect(page.getByRole('heading', { name: '探索', level: 1 })).toBeAttached()

  // 登出再用那台 Jellyfin 的管理員登入：是 Berth 的管理員（設定頁進得去）。
  await page.context().clearCookies()
  await page.goto('/login?redirect=%2Fsettings%2Fjellyfin')
  await page.getByRole('textbox', { name: 'Jellyfin 帳號' }).fill(OWNER.user)
  await page.getByRole('textbox', { name: '密碼' }).fill(OWNER.password)
  await page.getByRole('button', { name: '登入' }).click()
  await expect(page).toHaveURL('/settings/jellyfin')
})
