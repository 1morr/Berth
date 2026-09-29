import { expect, test } from '@playwright/test'

import { ADMIN, signIn } from './login.ts'
import { shot } from './shot.ts'

// `bundled`：乾淨的 compose（plan §9.3）。三個服務頁都選「套件內」，六頁走完、中途回頭再往前、關掉
// 精靈，再以頁 1 那組帳密登入——那組帳密是頁 1 替 Jellyfin 建的管理員，也就是 Berth 的擁有者
// （M4 票 06）。每一頁做完都停在結果上，按了才走（票 06d）；走的是 1280 與 390 兩種寬度
// （`playwright.config.ts`）。**選之前一個服務請求都不發**（M4 票 15）。
test('精靈六頁走完，之後以同一組帳密登入', async ({ page }) => {
  const probed: string[] = []
  page.on('request', (request) => {
    const url = request.url()
    if (/\/api\/setup\/(services\/|qbittorrent\/diff)/.test(url)) probed.push(url)
  })
  await page.goto('/')
  await expect(page).toHaveURL('/setup')

  // 1. Jellyfin：不預選、選之前不連；選了套件內才測，連上之後建立管理員並登入 Berth。
  await expect(page.getByRole('heading', { name: '先選 Jellyfin 是哪一台' })).toBeVisible()
  await expect(page.getByText(/Berth 沒有自己的帳號/)).toBeVisible()
  await expect(page.getByRole('radio', { checked: true })).toHaveCount(0)
  expect(probed).toEqual([])
  // 泊位板五格、沒有前置列（M4 票 15）。
  const board = page.getByRole('region', { name: '泊位板' })
  await expect(board.getByText(/^BTH \d$/)).toHaveCount(5)
  await shot(page, '1-choose')
  await page.getByRole('radio', { name: /套件內/ }).click()
  await expect(page.getByRole('heading', { name: '建立 Jellyfin 管理員' })).toBeVisible()
  await page.getByRole('textbox', { name: 'Jellyfin 帳號' }).fill(ADMIN.user)
  await page.getByRole('textbox', { name: '密碼', exact: true }).fill(ADMIN.password)
  await page.getByRole('textbox', { name: '再輸入一次密碼' }).fill(ADMIN.password)
  await shot(page, '1-owner')
  await page.getByRole('button', { name: '建立管理員並登入' }).click()
  await expect(page.getByRole('heading', { name: '擁有者：skipper' })).toBeVisible()
  // 擁有者成立之後 Jellyfin 的來源鎖住：擁有者是那一台上的帳號（shape 時拍板）。
  await expect(page.getByRole('radio', { name: /既有/ })).toBeDisabled()
  await shot(page, '1-owned')
  await page.getByRole('button', { name: '前往下一個泊位' }).click()

  // 2. qBittorrent：選之前不讀差異；選了套件內，WebUI 登入預設「沿用 Jellyfin 帳密」，密碼打一次。
  await expect(page.getByRole('heading', { name: '先選 qBittorrent 是哪一台' })).toBeVisible()
  expect(probed.filter((url) => /qbittorrent/.test(url))).toEqual([])
  await page.getByRole('radio', { name: /套件內/ }).click()
  await expect(page.getByRole('heading', { name: '套用建議的 qBittorrent 設定' })).toBeVisible()
  const webUi = page.getByRole('group', { name: 'qBittorrent WebUI 登入' })
  await expect(webUi.getByRole('checkbox', { name: /沿用 Jellyfin 帳密/ })).toBeChecked()
  // 密碼打錯：Jellyfin 驗不過，什麼都沒寫。
  await webUi.getByLabel('skipper 的 Jellyfin 密碼').fill('not-the-password')
  await page.getByRole('button', { name: /^套用這 \d+ 個鍵$/ }).click()
  await expect(page.getByText(/這不是 skipper 的 Jellyfin 密碼/)).toBeVisible()
  await webUi.getByLabel('skipper 的 Jellyfin 密碼').fill(ADMIN.password)
  await shot(page, '2-qbittorrent-login')
  await page.getByRole('button', { name: /^套用這 \d+ 個鍵$/ }).click()
  await expect(page.getByText('qBittorrent WebUI 的帳號：')).toBeVisible()
  await expect(page.getByRole('button', { name: '前往下一個泊位' })).toBeVisible()
  await shot(page, '2-qbittorrent')
  await page.getByRole('button', { name: '前往下一個泊位' }).click()

  // 3. 媒體庫與路徑：套件內先建你列的媒體庫（票 06f；M4 票 15 從 Jellyfin 頁搬過來）。
  //    Movies 改名、加一個、刪 Anime；建完停在結果上，按了才去 Route。
  await expect(page.getByRole('heading', { name: '建立媒體庫' })).toBeVisible()
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
  // Route：一走到就自動建、跑五條檢查（票 06d），清單上改過的名字就是 Route 的名字。後端要每一條
  // 都綠才前進（plan §9.3），所以「前往下一個泊位」出現就是全綠。
  await page.getByRole('button', { name: '前往 Route 與檢查' }).click()
  await expect(page.getByRole('heading', { name: '媒體庫路徑' })).toBeVisible()
  await expect(page.getByRole('button', { name: '重新檢查 3 條 Route' })).toBeVisible()
  await expect(page.getByText('berth-紀錄片', { exact: true })).toBeVisible()
  await shot(page, '3-routes')
  await page.getByRole('button', { name: '前往下一個泊位' }).click()

  // 4. Prowlarr 與索引站（九個裡有四個連不上是常態）。選套件內 → 介面登入自己設一組（取消沿用）→
  //    加入 → 試搜 → 不要的移除（票 06e）；替身的 Mikan 演「搜尋時連不上」。
  await expect(page.getByRole('heading', { name: '索引站', level: 2 })).toBeVisible()
  await page.getByRole('radio', { name: /套件內/ }).click()
  const prowlarrUi = page.getByRole('group', { name: 'Prowlarr 介面登入' })
  await prowlarrUi.getByRole('checkbox', { name: /沿用 Jellyfin 帳密/ }).uncheck()
  await prowlarrUi.getByRole('textbox', { name: '帳號' }).fill('deck')
  await prowlarrUi.getByLabel('密碼', { exact: true }).fill('harbour-prowlarr')
  await prowlarrUi.getByLabel('再輸入一次密碼').fill('harbour-prowlarr')
  await shot(page, '4-indexers-login')
  await page.getByRole('button', { name: '加入這 9 個站' }).click()
  await expect(page.getByText('Prowlarr 介面的帳號：')).toBeVisible()
  await page.getByRole('button', { name: '試搜' }).click()
  const trial = page.getByTestId('trial')
  await expect(trial.getByText(/502 Bad Gateway/)).toBeVisible()
  const yts = trial.getByRole('listitem').filter({ hasText: 'YTS' }).first()
  await expect(yts.getByText(/\d+ 筆/)).toBeVisible()
  await yts.getByRole('button', { name: '移除' }).click()
  await yts.getByRole('button', { name: '確定移除' }).click()
  await expect(trial.getByText('YTS', { exact: true })).toHaveCount(0)
  await shot(page, '4-indexers')
  await page.getByRole('button', { name: '前往下一個泊位' }).click()

  // 5. TMDB（替身認得任何一把 key）
  await expect(page.getByRole('heading', { name: 'TMDB', level: 2 })).toBeVisible()
  await page.getByRole('textbox', { name: '你的 TMDB API key' }).fill('0'.repeat(31) + '1')
  await page.getByRole('button', { name: '測試 TMDB' }).click()
  await expect(page.getByRole('button', { name: '前往下一個泊位' })).toBeVisible()
  await shot(page, '5-tmdb')
  await page.getByRole('button', { name: '前往下一個泊位' }).click()

  // 中途回頭再往前：板上點回 BTH 3 看媒體庫清單，一顆鍵回到目前這一步；上一個泊位、再前往下一個也回得來。
  await expect(page.getByRole('heading', { name: '完成設定' })).toBeVisible()
  await board.getByRole('button', { name: /BTH 3/ }).click()
  await page.getByRole('button', { name: '媒體庫清單' }).click()
  // 建好的列鎖住，改名刪除去 Jellyfin（票 06f）。
  await expect(page.getByText('已建立', { exact: true })).toHaveCount(3)
  await page.getByRole('button', { name: '回到目前這一步' }).click()
  await expect(page.getByRole('heading', { name: '完成設定' })).toBeVisible()
  await page.getByRole('button', { name: '上一個泊位' }).click()
  await expect(page.getByRole('heading', { name: 'TMDB', level: 2 })).toBeVisible()
  await page.getByRole('button', { name: '前往下一個泊位' }).click()

  // 6. 完成
  await expect(page.getByRole('heading', { name: '完成設定' })).toBeVisible()
  await expect(page.getByText('已繫上')).toHaveCount(3)
  await expect(page.getByText(/你是 skipper/)).toBeVisible()
  await shot(page, '6-complete')
  await page.getByRole('button', { name: '完成設定' }).click()

  // 擁有者從頁 1 起就登入著：精靈關掉之後直接落在探索，不再導向精靈。
  await expect(page).toHaveURL('/')
  await expect(page.getByRole('heading', { name: '探索', level: 1 })).toBeAttached()

  // 同一組帳密就是登入 Berth 的那一組，而且是管理員（設定頁只有管理員進得去）。
  await page.context().clearCookies()
  await signIn(page, '/settings/jellyfin')
  await page.goto('/jobs')
  await expect(page.getByRole('heading', { name: '下載', level: 1 })).toBeVisible()
})
