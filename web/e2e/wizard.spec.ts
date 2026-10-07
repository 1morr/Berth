import { expect, test } from '@playwright/test'

import { ADMIN, signIn } from './login.ts'
import { narrow, shot } from './shot.ts'

// `bundled`：乾淨的 compose（plan §9.3）。三個服務頁都選「套件內」，六頁走完、中途回頭再往前、關掉
// 精靈，再以頁 1 那組帳密登入——那組帳密是頁 1 替 Jellyfin 建的管理員，也就是 Berth 的擁有者
// （M4 票 06）。每一頁做完都停在結果上，按了才走（票 06d）；走的是 1280 與 390 兩種寬度
// （`playwright.config.ts`）。**選之前一個服務請求都不發**（M4 票 15）。**密碼只在頁 1 建立時打兩次**
// （M4 票 40，審計 S1）：頁 2、頁 4 的介面登入自動沿用那一組。
test('精靈六頁走完，之後以同一組帳密登入', async ({ page }) => {
  const probed: string[] = []
  // 精靈送出的寫入（非 GET），頁 3 用它證明進頁自動送的就是那一段（M4 票 43）。進頁的重讀不算（M4 票 19、24）：
  // 它只向 Jellyfin 讀、換 Berth 自己的媒體庫快照，與 `existing.spec.ts` 同一條。
  const writes: string[] = []
  page.on('request', (request) => {
    const url = request.url()
    if (/\/api\/setup\/(services\/|qbittorrent\/diff)/.test(url)) probed.push(url)
    const reread = url.endsWith('/api/setup/routes/libraries')
    if (request.method() !== 'GET' && url.includes('/api/setup/') && !reread) writes.push(url)
  })
  await page.goto('/')
  // 精靈的頁在網址上（M4 票 30）：讀回狀態之後補上 `?step=1`。
  await expect(page).toHaveURL(/\/setup(\?step=1)?$/)

  // 1. Jellyfin：不預選、選之前不連；選了套件內才測，連上之後建立管理員並登入 Berth。
  await expect(page.getByRole('heading', { name: '先選 Jellyfin 是哪一台' })).toBeVisible()
  await expect(page.getByText(/Berth 沒有自己的帳號/)).toBeVisible()
  await expect(page.getByRole('radio', { checked: true })).toHaveCount(0)
  expect(probed).toEqual([])
  // 泊位板五格、沒有前置列（M4 票 15）。
  const board = page.getByRole('region', { name: '泊位板' })
  await expect(board.locator('ul > li')).toHaveCount(5)
  // 390 寬時板收成一列摘要，首屏先看到這一頁要做的事（M4 票 30）；桌機一列五格、沒有摘要。
  const folded = board.getByRole('button', { expanded: false })
  if (narrow(page)) {
    await expect(folded).toHaveText(/BTH 1.*Jellyfin/)
    await expect(board.getByRole('list')).toHaveCount(0)
    await expect(page.getByRole('radio', { name: /套件內/ })).toBeInViewport()
  } else {
    await expect(folded).toHaveCount(0)
    await expect(board.getByRole('listitem')).toHaveCount(5)
  }
  await page.screenshot({ path: test.info().outputPath('1-first-viewport.png') })
  await shot(page, '1-choose')
  await page.getByRole('radio', { name: /套件內/ }).click()
  await expect(page.getByRole('heading', { name: '建立 Jellyfin 管理員' })).toBeVisible()
  await page.getByRole('textbox', { name: 'Jellyfin 帳號' }).fill(ADMIN.user)
  await page.getByRole('textbox', { name: '密碼', exact: true }).fill(ADMIN.password)
  await page.getByRole('textbox', { name: '再輸入一次密碼' }).fill(ADMIN.password)
  await expect(
    page.getByRole('checkbox', { name: '套件內 qBittorrent 與 Prowlarr 的介面也用這組' }),
  ).toBeChecked()
  await shot(page, '1-owner')
  await page.getByRole('button', { name: '建立管理員並登入' }).click()
  await expect(page.getByRole('heading', { name: '擁有者：skipper' })).toBeVisible()
  // 擁有者成立之後 Jellyfin 的來源鎖住：擁有者是那一台上的帳號（shape 時拍板）。
  await expect(page.getByRole('radio', { name: /既有/ })).toBeDisabled()
  await shot(page, '1-owned')
  await page.getByRole('button', { name: '前往下一個泊位' }).click()

  // 2. qBittorrent：選之前不讀差異；選了套件內，WebUI 登入自動沿用頁 1 那一組（M4 票 40），不問密碼。
  await expect(page.getByRole('heading', { name: '先選 qBittorrent 是哪一台' })).toBeVisible()
  expect(probed.filter((url) => /qbittorrent/.test(url))).toEqual([])
  await page.getByRole('radio', { name: /套件內/ }).click()
  await expect(page.getByRole('heading', { name: '設定 qBittorrent 的 WebUI 登入' })).toBeVisible()
  await expect(page.getByText('qBittorrent WebUI 的帳號：')).toBeVisible()
  await expect(page.getByLabel('skipper 的 Jellyfin 密碼')).toHaveCount(0)
  expect(writes.filter((url) => url.endsWith('/api/setup/qbittorrent/apply'))).toHaveLength(1)
  await expect(page.getByRole('button', { name: '前往下一個泊位' })).toBeVisible()
  await shot(page, '2-qbittorrent')
  await page.getByRole('button', { name: '前往下一個泊位' }).click()

  // 3. 媒體庫與路徑（M4 票 43）：套件內第一次來、清單沒改過，進頁就建媒體庫、建 Route、跑每一條檢查，
  //    不必按（票 08 的按鍵留給改過清單的、跑過一次之後與既有）。跑完再展開清單加一個，加了回到按鍵。
  const arrived = writes.length
  await expect(page.getByRole('heading', { name: '媒體庫路徑', level: 2 })).toBeVisible()
  const routes = page.getByRole('list', { name: '這一頁的 Route' })
  await expect(routes.getByText('6 / 6 通過')).toHaveCount(3)
  expect(writes.slice(arrived).map((url) => new URL(url).pathname)).toEqual([
    '/api/setup/jellyfin/bundled',
    '/api/setup/jellyfin/bootstrap',
    '/api/setup/routes',
  ])
  await expect(page.getByText(/預設清單沒改過/)).toBeVisible()
  await shot(page, '3-auto')
  // 清單收成一列；展開加一個媒體庫。資料夾跟著名稱走，名稱不是英文字母時要自己填（票 06f）。
  await page.getByText('媒體庫清單').click()
  await page.getByRole('button', { name: '加一個媒體庫' }).click()
  // 那一列的名字就是它的組名：名稱填了之後組名跟著換。
  const added = page.getByRole('group', { name: '第 4 個媒體庫' })
  await added.getByRole('combobox', { name: '內容類型' }).selectOption({ label: '電影' })
  await added.getByRole('textbox', { name: '名稱' }).fill('紀錄片')
  const documentaries = page.getByRole('group', { name: '紀錄片' })
  await expect(documentaries.getByRole('alert')).toHaveText(/資料夾要自己填/)
  await documentaries.getByRole('textbox', { name: '資料夾' }).fill('documentaries')
  await expect(documentaries.getByRole('alert')).toHaveCount(0)
  const preview = page.getByRole('region', { name: '按下之後會' })
  await expect(preview.getByText(/在 Jellyfin 建 1 個媒體庫：紀錄片/)).toBeVisible()
  await shot(page, '3-libraries')
  await page.getByRole('button', { name: '建立並檢查' }).click()
  // 後端要每一條都綠才前進（plan §9.3），所以「前往下一個泊位」出現就是全綠；四條各一列、收起。
  const next = page.getByRole('button', { name: '前往下一個泊位' })
  await expect(next).toBeVisible()
  await expect(routes.getByText('6 / 6 通過')).toHaveCount(4)
  // 分類名在 Route 列上，展開後「建立分類」那一條的行首也有一份（M4 票 21 的關鍵值）：看 Route 列那一個。
  // 套件內照清單上填的資料夾名，不是媒體庫名（M4 票 31）。
  await expect(routes.getByText('berth-documentaries', { exact: true }).first()).toBeVisible()
  // 不捲動就看得到下一步（票 08 驗收）：回到頁頂量。
  // 字串而不是函式：e2e 的 tsconfig 沒有 DOM 型別，這一行在瀏覽器裡跑。
  await page.evaluate('window.scrollTo(0, 0)')
  await expect(next).toBeInViewport()
  await page.screenshot({ path: test.info().outputPath('3-routes-viewport.png') })
  await shot(page, '3-routes')
  await next.click()

  // 4. Prowlarr 與索引站：進頁不送任何測試或寫入。套件內一顆主鍵測推薦站、把通過的加進去（M4 票 44）。
  //    九個裡有四個測試就沒過（替身的 `BLOCKED_SITES`），ACG.RIP 測過而加不進去（`FLAKY_SITES`，審計實測的
  //    Internet Archive）：結果逐站列出、兩種分開說。加入之後逐站 / 全部試搜，不要的移除；替身的 Mikan 演「搜尋時
  //    連不上」。再從「進階」的其他公開站加一個不在推薦清單上的。
  await expect(page.getByRole('heading', { name: 'Prowlarr', level: 2 })).toBeVisible()
  const atIndexers = writes.length
  await page.getByRole('radio', { name: /套件內/ }).click()
  const quick = page.getByTestId('recommended-sites')
  await expect(quick).toBeVisible()
  await page.waitForLoadState('networkidle')
  // 選套件內那一下與自動沿用的介面登入（M4 票 40）是僅有的寫入；清單出來之後一站都沒測、沒加。
  await expect(page.getByText('Prowlarr 介面的帳號：')).toBeVisible()
  expect(writes.slice(atIndexers).map((url) => new URL(url).pathname)).toEqual([
    '/api/setup/services/prowlarr',
    '/api/setup/indexers/login',
  ])
  // 逐站清單收在「進階」裡，預設收起。
  await expect(page.getByTestId('recommended')).toBeHidden()
  await shot(page, '4-indexers-one-key')
  await quick.getByRole('button', { name: '測試推薦站，加入通過的' }).click()
  const outcome = page.getByTestId('one-key-outcome')
  await expect(outcome.getByText('加入 4 站 · 1 站測過、加不進去 · 4 站沒通過測試')).toBeVisible()
  await expect(
    outcome.getByTestId('add-failed').getByText('ACG.RIP', { exact: true }),
  ).toBeVisible()
  await expect(outcome.getByTestId('test-failed').getByText('1337x', { exact: true })).toBeVisible()
  const addedSites = page.getByTestId('added')
  await expect(addedSites.getByText('4 站')).toBeVisible()
  await expect(quick.getByRole('button', { name: '測試推薦站，加入通過的' })).toHaveCount(0)
  await shot(page, '4-indexers-outcome')
  await page.getByText('進階：逐站測試與挑選、其他公開站').click()
  await expect(page.getByRole('checkbox', { name: '1337x' })).toBeDisabled()
  await page.getByLabel('搜尋名稱').fill('knab')
  await page.getByRole('button', { name: '測試 Knaben' }).click()
  await page.getByRole('checkbox', { name: 'Knaben' }).check()
  await page.getByRole('button', { name: '加入 1 個站' }).click()
  await expect(addedSites.getByText('5 站')).toBeVisible()
  await expect(page.getByLabel('skipper 的 Jellyfin 密碼')).toHaveCount(0)
  await shot(page, '4-indexers-login')
  await addedSites.getByRole('button', { name: '搜尋 YTS' }).click()
  const trial = page.getByTestId('trial')
  const yts = trial.getByRole('listitem').filter({ hasText: 'YTS' }).first()
  await expect(yts.getByText(/\d+ 筆/)).toBeVisible()
  await addedSites.getByRole('button', { name: '搜尋全部' }).click()
  await expect(trial.getByText('搜尋失敗')).toBeVisible()
  await yts.getByRole('button', { name: '移除' }).click()
  await yts.getByRole('button', { name: '確定移除' }).click()
  await expect(trial.getByText('YTS', { exact: true })).toHaveCount(0)
  // 結果出來之後不捲動就看得到下一步（M4 票 09 驗收）：回到頁頂量。
  const toTmdb = page.getByRole('button', { name: '前往下一個泊位' })
  await page.evaluate('window.scrollTo(0, 0)')
  await expect(toTmdb).toBeInViewport()
  await page.screenshot({ path: test.info().outputPath('4-indexers-viewport.png') })
  await shot(page, '4-indexers')
  await toTmdb.click()

  // 5. TMDB（替身認得任何一把 key）
  await expect(page.getByRole('heading', { name: 'TMDB', level: 2 })).toBeVisible()
  await page.getByRole('textbox', { name: '你的 TMDB API key' }).fill('0'.repeat(31) + '1')
  await page.getByRole('button', { name: '測試 TMDB' }).click()
  await expect(page.getByRole('button', { name: '前往下一個泊位' })).toBeVisible()
  await shot(page, '5-tmdb')
  await page.getByRole('button', { name: '前往下一個泊位' }).click()

  // 中途回頭再往前：板上點回 BTH 3 展開媒體庫清單，一顆鍵回到目前這一步；上一個泊位、再前往下一個也回得來。
  await expect(page.getByRole('heading', { name: '完成設定' })).toBeVisible()
  if (narrow(page)) await folded.click()
  await board.getByRole('button', { name: /BTH 3/ }).click()
  await expect(page.getByRole('heading', { name: '媒體庫路徑', level: 2 })).toBeVisible()
  await expect(page).toHaveURL(/\/setup\?step=3$/)
  // 重新整理留在這一頁；瀏覽器的上一頁回到上一個看過的頁、不離開精靈（M4 票 30）。
  await page.reload()
  await expect(page.getByRole('heading', { name: '媒體庫路徑', level: 2 })).toBeVisible()
  await page.goBack()
  await expect(page.getByRole('heading', { name: '完成設定' })).toBeVisible()
  await page.goForward()
  await expect(page.getByRole('heading', { name: '媒體庫路徑', level: 2 })).toBeVisible()
  await page.getByText('4 個已建立').click()
  // 建好的列鎖住，改名刪除去 Jellyfin（票 06f）。
  await expect(page.getByText('已建立', { exact: true })).toHaveCount(4)
  await page.getByRole('button', { name: '回到目前這一步' }).click()
  await expect(page.getByRole('heading', { name: '完成設定' })).toBeVisible()
  await page.getByRole('button', { name: '上一個泊位' }).click()
  await expect(page.getByRole('heading', { name: 'TMDB', level: 2 })).toBeVisible()
  await page.getByRole('button', { name: '前往下一個泊位' }).click()

  // 6. 完成
  await expect(page.getByRole('heading', { name: '完成設定' })).toBeVisible()
  await expect(page.getByText('已繫上')).toHaveCount(4)
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
