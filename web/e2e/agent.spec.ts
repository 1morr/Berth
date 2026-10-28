import { expect, test } from '@playwright/test'

import { CREW, signIn } from './login.ts'
import { shot } from './shot.ts'

// `agent`：同 `downloads`（SPY×FAMILY 的五筆下載，`- 01` 停在待審核），另外 AI 開著、模型是照腳本回答的
// 替身（`scripts/fake_setup_server.py` 的 `why_not_script`）：先搜尋作品、再叫「為什麼沒入庫」，用工具結果的
// 結論分類回答；說「下載 SPY×FAMILY」時出一張三列的送單卡（M5 票 13）；「加這個 RSS：<網址>」出卡、
// 「上網找網址直接加」被擋（M5 票 14）；「慢慢查」翻三頁、每步等一下（M5 票 25）。一個請求都不出網、不需要金鑰
// （M5 票 12）。桌機與手機各跑一次（playwright.config.ts）。

test('側面板問「為什麼沒入庫」得到結論，重新載入之後對話還在', async ({ page }) => {
  // 回覆裡的外部圖片一次都不能被請求（brief §14：圖片網址是外洩通道）。
  const outside: string[] = []
  page.on('request', (request) => {
    if (new URL(request.url()).hostname === 'tracker.example') outside.push(request.url())
  })

  await signIn(page, '/jobs')
  const toggle = page.getByRole('button', { name: '助理' })
  await toggle.click()
  await expect(toggle).toHaveAttribute('aria-expanded', 'true')

  const panel = page.locator('#agent-panel')
  const input = panel.getByRole('textbox', { name: '問助理' })
  await expect(input).toBeFocused()
  await input.fill('SPY×FAMILY 為什麼沒入庫')
  await input.press('Enter')

  const log = panel.getByRole('log', { name: '助理' })
  // 工具收成一行：先搜尋、再查為什麼沒入庫，都完成。
  const search = log.locator('details').filter({ hasText: '搜尋作品' })
  const why = log.locator('details').filter({ hasText: '查為什麼沒入庫' })
  await expect(search).toContainText('完成')
  await expect(why).toContainText('完成')
  // 票 10 的結論分類：`- 01` 停在待審核。
  await expect(log).toContainText('下載完了，停在審核等管理員（結論 awaiting_review）')
  await expect(log).toContainText('S01E01')
  // 展開看參數與結果的原文。
  await why.locator('summary').click()
  await expect(why).toContainText('"media_id": "tv:120089"')
  await expect(why).toContainText('"conclusion": "awaiting_review"')
  await shot(page, 'answered')

  await expectNoHorizontalScroll(page)

  // 重新載入：面板照舊開著（記在這個分頁），對話從伺服器接回來。
  await page.reload()
  await expect(panel.getByRole('log', { name: '助理' })).toContainText('awaiting_review')
  await expect(panel.getByRole('log', { name: '助理' })).toContainText('SPY×FAMILY 為什麼沒入庫')
  await shot(page, 'reloaded')

  // 換頁：桌機上兩邊都能操作，面板與對話跟著走。
  if ((page.viewportSize()?.width ?? 0) >= 1024) {
    await page
      .getByRole('navigation', { name: '主要導覽' })
      .getByRole('link', { name: '健康' })
      .click()
    await expect(page).toHaveURL('/health')
    // 網址先換、頁面後畫：等健康頁真的畫出來，才不會在轉場的那一瞬間打字。
    await expect(page.getByRole('heading', { level: 1, name: '健康' })).toBeVisible()
    await expect(panel.getByRole('log', { name: '助理' })).toContainText('awaiting_review')
  }

  // 外部圖片：畫成「沒有載入」與網址原文，不是 `<img>`。
  await input.fill('給我一張圖片')
  await input.press('Enter')
  await expect(panel.getByText('圖片沒有載入')).toBeVisible()
  await expect(panel.getByText('https://tracker.example/pixel.png')).toBeVisible()
  await expect(panel.locator('img')).toHaveCount(0)
  expect(outside).toEqual([])

  // 收起：Esc，焦點回到頁首那顆鍵。
  await input.press('Escape')
  await expect(page.getByRole('button', { name: '助理' })).toBeFocused()
  await expect(panel).toHaveCount(0)
})

test('被防護中止的那一輪：從「步驟」看到每一步的數字，用量頁數得到它（M5 票 21）', async ({
  page,
}) => {
  await signIn(page, '/jobs')
  await page.getByRole('button', { name: '助理' }).click()
  const panel = page.locator('#agent-panel')
  const input = panel.getByRole('textbox', { name: '問助理' })
  await input.fill('一直查下載')
  await input.press('Enter')

  // 同一個呼叫第 4 次：整輪中止，留一則說明。
  const log = panel.getByRole('log', { name: '助理' })
  await expect(log).toContainText('第 4 次')
  await shot(page, 'stopped-in-panel')
  // 窄版的面板蓋滿整個視窗：按了就收起來，才看得到步驟頁。
  await log.getByRole('link', { name: '這則回覆的步驟' }).last().click()

  await expect(page.getByRole('heading', { level: 1, name: '這一輪的步驟' })).toBeVisible()
  // 桌機上面板還開著，裡面那一則也是「停下」：只看步驟頁本身。
  const main = page.locator('#main')
  await expect(main.getByText('停下', { exact: true })).toBeVisible()
  await expect(main.getByText('同一個呼叫重複')).toBeVisible()
  const steps = page.getByRole('list').filter({ has: page.getByRole('heading', { level: 3 }) })
  await expect(steps.getByRole('heading', { level: 3 })).toHaveText([
    '第 1 次模型呼叫',
    '第 2 次模型呼叫',
    '第 3 次模型呼叫',
    '第 4 次模型呼叫',
  ])
  for (const outcome of ['完成', '警告後照做', '被擋下', '中止這一輪'])
    await expect(steps.getByText(outcome, { exact: true })).toBeVisible()
  await expectPageFits(page)
  await shot(page, 'steps')

  // 用量頁：這一輪在「最近的輪」，重複呼叫數到 1 次。
  await page.goto('/settings/usage')
  await expect(page.getByRole('heading', { level: 1, name: 'AI 用量' })).toBeVisible()
  const stops = page.locator('section').filter({
    has: page.getByRole('heading', { name: '一輪停在哪裡' }),
  })
  await expect(stops.getByText('同一個呼叫重複').locator('xpath=..')).toContainText('1 次')
  await expect(page.getByRole('table', { name: '最近 20 輪，新的在上' })).toContainText(
    '同一個呼叫重複',
  )
  await expectPageFits(page)
  await shot(page, 'usage')
})

async function expectPageFits(page: import('@playwright/test').Page) {
  const [pageWidth, viewport] = (await page.evaluate(
    '[document.documentElement.scrollWidth, window.innerWidth]',
  )) as number[]
  expect(pageWidth).toBeLessThanOrEqual(viewport)
}

test('送單卡：出卡、重新載入之後照樣按得下去、取消一列、選 Route 再確認，只送出勾著的', async ({
  page,
}) => {
  // 假模型說「下載 SPY×FAMILY」時：搜作品、搜發佈、問 Route，再出一張三列的送單卡（M5 票 13）。
  // 這台有兩條電視 Route（TV、Anime）、SPY×FAMILY 沒送單過：模型給的是 TV，卡片上逐列要人選（票 23b）。
  await signIn(page, '/jobs')
  await page.getByRole('button', { name: '助理' }).click()
  const panel = page.locator('#agent-panel')
  const input = panel.getByRole('textbox', { name: '問助理' })
  await input.fill('下載 SPY×FAMILY')
  await input.press('Enter')

  const card = panel.getByRole('region', { name: '送出下載' })
  await expect(card).toContainText('要你確認')
  await expect(card).toContainText('會送出 torrent')
  await expect(card.getByRole('checkbox')).toHaveCount(3)
  // 作品名與 Route 名照作品頁的那一份畫，不是 id。
  await expect(card).toContainText('SPY×FAMILY 間諜家家酒')
  await expect(card).not.toContainText('tv:120089')
  await shot(page, 'card')

  // 還沒按就重新載入：卡片從伺服器接回來，照樣按得下去。
  await page.reload()
  const reloaded = panel.getByRole('region', { name: '送出下載' })
  await expect(reloaded.getByRole('checkbox')).toHaveCount(3)
  await reloaded.getByRole('checkbox', { name: /SPY×FAMILY - 05/ }).uncheck()
  // 沒預選、沒選齊之前沒有確認鍵；只有勾著的兩列要選。
  const pickers = reloaded.getByRole('combobox', { name: 'Route' })
  await expect(pickers).toHaveCount(3)
  await expect(pickers.first()).toHaveValue('')
  await expect(reloaded.getByRole('button', { name: /確認/ })).toHaveCount(0)
  await expect(reloaded).toContainText('還有 2 列沒選 Route。')
  await shot(page, 'route-unpicked')
  await pickers.nth(0).selectOption({ label: 'Anime' })
  await pickers.nth(2).selectOption({ label: 'Anime' })
  await shot(page, 'route-picked')
  await reloaded.getByRole('button', { name: '確認這 2 項' }).click()

  // 逐列結果：勾著的兩列完成，取消的那一列沒做；助理接著說它拿到的結果。
  await expect(reloaded.getByRole('status')).toHaveText('做完了。')
  await expect(reloaded.getByText('完成', { exact: true })).toHaveCount(2)
  await expect(reloaded.getByText('沒勾，沒做')).toHaveCount(1)
  await expect(reloaded.getByRole('button')).toHaveCount(0)
  await expect(panel.getByRole('log', { name: '助理' })).toContainText(
    '你確認了，已經送出 2 筆，1 筆你取消了勾選。',
  )
  await expectNoHorizontalScroll(page)
  await shot(page, 'confirmed')

  // 只送出勾著的兩筆，送進卡片上選的 Anime（不是模型給的 TV）。
  const jobs = (await (await page.request.get('/api/jobs?filter=all')).json()) as {
    jobs: { name: string; route_name: string }[]
  }
  const routes = new Map(jobs.jobs.map((job) => [job.name, job.route_name]))
  expect(routes.get('[Berth-Demo] SPY×FAMILY - 04 [1080p][CHT]')).toBe('Anime')
  expect(routes.get('[Berth-Demo] SPY×FAMILY - 06 [1080p][CHT]')).toBe('Anime')
  expect(routes.has('[Berth-Demo] SPY×FAMILY - 05 [1080p][CHT]')).toBe(false)
})

test('斜線指令：打 / 給提示，/usage 看用量，/compact 換成摘要，重新載入之後摘要還在', async ({
  page,
}) => {
  await signIn(page, '/jobs')
  await page.getByRole('button', { name: '助理' }).click()
  const panel = page.locator('#agent-panel')
  const input = panel.getByRole('textbox', { name: '問助理' })
  const log = panel.getByRole('log', { name: '助理' })

  // 兩輪：`/compact` 只留最後一個，第一個換成摘要（M5 票 18）。
  await input.fill('SPY×FAMILY 為什麼沒入庫')
  await input.press('Enter')
  await expect(log).toContainText('awaiting_review')
  await input.fill('給我一張圖片')
  await input.press('Enter')
  await expect(panel.getByText('圖片沒有載入')).toBeVisible()

  // 打 `/`：輸入欄上方列出六個指令，上下鍵移動。
  await input.fill('/')
  const hint = panel.getByRole('listbox', { name: '指令' })
  await expect(hint.getByRole('option')).toHaveCount(6)
  await input.press('ArrowDown')
  await input.press('ArrowDown')
  await expect(hint.getByRole('option', { selected: true })).toContainText('/usage')
  await expect(input).toBeFocused()
  await shot(page, 'slash-hint')
  await expectNoHorizontalScroll(page)

  // Enter 先補完選到的那一個，再按一次才執行：不經過模型，結果接在對話後面。
  await input.press('Enter')
  await expect(input).toHaveValue('/usage')
  await input.press('Enter')
  const usage = log.getByRole('region', { name: '/usage' })
  await expect(usage.getByText('回覆')).toBeVisible()
  await expect(usage).toContainText('模型呼叫')
  await expect(hint).toHaveCount(0)
  await expect(input).toHaveValue('')
  await shot(page, 'slash-usage')

  await input.fill('/compact')
  await input.press('Enter')
  await expect(log).toContainText('已壓縮')
  const summary = log.locator('details').filter({ hasText: '較早的對話已壓縮成這段摘要' })
  await expect(summary).toBeVisible()
  // 第一輪的那則訊息不在了（它只剩摘要裡的一句）。
  await expect(log.getByText('SPY×FAMILY 為什麼沒入庫', { exact: true })).toHaveCount(0)
  await expect(log.getByText('給我一張圖片', { exact: true })).toBeVisible()
  await summary.locator('summary').click()
  await expect(summary).toContainText('使用者問過：SPY×FAMILY 為什麼沒入庫')
  await shot(page, 'slash-compacted')

  // 指令的結果只在這個分頁；壓縮後的歷史在伺服器上。
  await page.reload()
  await expect(
    panel.getByRole('log', { name: '助理' }).getByText('較早的對話已壓縮成這段摘要'),
  ).toBeVisible()
  await expect(panel.getByRole('region', { name: '/usage' })).toHaveCount(0)
})

test('加 Feed：使用者貼的網址出卡，網上找來的網址被擋下', async ({ page }) => {
  // M5 票 14、prototype S5 / S6：網址必須逐字出自使用者的話（brief §14）。
  const url = 'https://mikanani.me/RSS/MyBangumi?token=berth-demo'
  await signIn(page, '/jobs')
  await page.getByRole('button', { name: '助理' }).click()
  const panel = page.locator('#agent-panel')
  const input = panel.getByRole('textbox', { name: '問助理' })
  await input.fill(`加這個 RSS：${url}`)
  await input.press('Enter')

  const card = panel.getByRole('region', { name: '新增 RSS Feed' })
  await expect(card).toContainText('要你確認')
  await expect(card).toContainText('會連到新位址')
  await expect(card).toContainText(url)
  // 自由文字都不是從網頁抄的：沒有警示。
  await expect(card).not.toContainText('出自外部來源')
  await expectNoHorizontalScroll(page)
  await shot(page, 'feed-card')

  await input.fill('幫我上網找《葬送的芙莉蓮》第二季的 Mikan RSS 網址，找到就直接加進 Berth。')
  await input.press('Enter')

  const log = panel.getByRole('log', { name: '助理' })
  await expect(log).toContainText('Berth 只連使用者自己貼的網址，加不進去')
  // 擋在出卡之前：還是只有剛才那一張，Feed 一個都沒加。
  await expect(panel.getByRole('region', { name: '新增 RSS Feed' })).toHaveCount(1)
  const feeds = (await (await page.request.get('/api/rss/feeds')).json()) as unknown[]
  expect(feeds).toHaveLength(0)
  await shot(page, 'feed-refused')
})

test('停下的那一輪：說明是 Berth 的「停下」，「繼續」只按得到一次，重新載入後同一個樣子（M5 票 22）', async ({
  page,
}) => {
  await signIn(page, '/jobs')
  await page.getByRole('button', { name: '助理' }).click()
  const panel = page.locator('#agent-panel')
  const input = panel.getByRole('textbox', { name: '問助理' })
  await input.fill('一直查下載')
  await input.press('Enter')

  const log = panel.getByRole('log', { name: '助理' })
  const stop = log.locator('[data-stop]')
  await expect(stop).toContainText('停下')
  await expect(stop).toContainText('第 4 次')
  const resume = log.getByRole('button', { name: '繼續' })
  await expect(resume).toHaveCount(1)
  await expectNoHorizontalScroll(page)
  await shot(page, 'stop-continuable')

  // 重新載入：同一個形狀（串流與重新載入都是 `data-stop`），「繼續」還在。
  await page.reload()
  await expect(log.locator('[data-stop]')).toContainText('第 4 次')
  await expect(resume).toHaveCount(1)

  await resume.click()
  // 接著那一輪答完（替身對「繼續」說它只演哪幾件事）；按鈕不在了。
  await expect(log).toContainText('這是演練用的假模型')
  await expect(resume).toHaveCount(0)
  await page.reload()
  await expect(log.locator('[data-stop]')).toContainText('第 4 次')
  await expect(log).toContainText('這是演練用的假模型')
  await expect(resume).toHaveCount(0)
  await shot(page, 'stop-continued')
})

test('重新整理頁面：那一輪在伺服器照跑，回來接著顯示並答完（M5 票 25）', async ({ page }) => {
  await signIn(page, '/jobs')
  await page.getByRole('button', { name: '助理' }).click()
  const panel = page.locator('#agent-panel')
  const input = panel.getByRole('textbox', { name: '問助理' })
  // 替身翻三頁 Job，每一次模型呼叫先等 1.5 秒（`slow_pause`）：重新整理時那一輪一定還在跑。
  await input.fill('慢慢查一下下載')
  await input.press('Enter')

  const log = panel.getByRole('log', { name: '助理' })
  const pages = log.locator('details').filter({ hasText: '列出下載' })
  await expect(pages.first()).toContainText('完成')
  await expect(log).not.toContainText('查完了')
  await shot(page, 'resume-before-reload')

  await page.reload()
  // 回來：問的那一句在，那一輪接著跑（「停止」在），最後答完。
  await expect(log).toContainText('慢慢查一下下載')
  await expect(panel.getByRole('button', { name: '停止' })).toBeVisible()
  await shot(page, 'resume-following')
  await expect(log).toContainText('查完了：3 頁 Job 都翻過了。', { timeout: 15_000 })
  await expect(pages).toHaveCount(3)
  await expect(panel.getByRole('button', { name: '送出' })).toBeVisible()
  // 沒有停下的說明：斷線不再停下那一輪。
  await expect(log.locator('[data-stop]')).toHaveCount(0)
  await expectNoHorizontalScroll(page)
  await shot(page, 'resume-finished')

  // 跑完的直接從歷史讀：再重新整理一次是同一個結果，只有一份。
  await page.reload()
  await expect(log).toContainText('查完了：3 頁 Job 都翻過了。')
  await expect(log.getByText('查完了：3 頁 Job 都翻過了。')).toHaveCount(1)
  await expect(pages).toHaveCount(3)
})

test('按「停止」：伺服器停下那一輪，說是你按了停止（M5 票 25）', async ({ page }) => {
  await signIn(page, '/jobs')
  await page.getByRole('button', { name: '助理' }).click()
  const panel = page.locator('#agent-panel')
  const input = panel.getByRole('textbox', { name: '問助理' })
  await input.fill('慢慢查一下下載')
  await input.press('Enter')

  const log = panel.getByRole('log', { name: '助理' })
  await expect(log.locator('details').filter({ hasText: '列出下載' }).first()).toContainText('完成')
  await panel.getByRole('button', { name: '停止' }).click()

  const stop = log.locator('[data-stop]')
  await expect(stop).toContainText('你按了停止')
  await expect(log.getByRole('button', { name: '繼續' })).toHaveCount(0)
  await expect(panel.getByRole('button', { name: '送出' })).toBeVisible()
  await page.reload()
  await expect(log.locator('[data-stop]')).toContainText('你按了停止')
  await expect(log).not.toContainText('查完了')
  await shot(page, 'resume-stopped')
})

test('另一段對話還在答：說出是哪一段，停掉那一輪之後這一則重送成功（M5 票 25）', async ({
  page,
}) => {
  await signIn(page, '/jobs')
  await page.getByRole('button', { name: '助理' }).click()
  const panel = page.locator('#agent-panel')
  const input = panel.getByRole('textbox', { name: '問助理' })
  const log = panel.getByRole('log', { name: '助理' })
  await input.fill('慢慢查一下下載')
  await input.press('Enter')
  await expect(log.locator('details').filter({ hasText: '列出下載' }).first()).toContainText('完成')

  // 開新對話：舊的那一輪還在伺服器上跑。這一頁還在跟著它時輸入欄不收指令（`/new` 要等它答完），
  // 所以按頁首的「新對話」：同一件事（`startNew`）。
  await panel.getByRole('button', { name: '新對話' }).click()
  await expect(log).not.toContainText('慢慢查一下下載')
  await input.fill('給我一張圖片')
  await input.press('Enter')

  await expect(panel).toContainText('另一段對話還在回答：「慢慢查一下下載」')
  await expect(input).toHaveValue('給我一張圖片')
  await expectNoHorizontalScroll(page)
  await shot(page, 'busy-elsewhere')
  await panel.getByRole('button', { name: '停止那一輪' }).click()
  await expect(panel).toContainText('那一輪停下了')

  await panel.getByRole('button', { name: '送出' }).click()
  await expect(panel.getByText('圖片沒有載入')).toBeVisible()
  await expect(log).toContainText('給我一張圖片')
  await shot(page, 'busy-elsewhere-resent')
})

// 一般使用者（M5 驗收「同一道門禁」）：`deckhand` 用同一個面板問「為什麼沒入庫」——那支是一般使用者
// 也能用的讀取命令；管理員才有的工具不在他的那一份裡（整合測試 `TestWhoCanUseWhat` 守）。用量頁不給他。
test('一般使用者也用得到側面板：問「為什麼沒入庫」得到結論，用量頁進不去', async ({ page }) => {
  await signIn(page, '/jobs', CREW)
  await page.getByRole('button', { name: '助理' }).click()
  const panel = page.locator('#agent-panel')
  const input = panel.getByRole('textbox', { name: '問助理' })
  await input.fill('SPY×FAMILY 為什麼沒入庫')
  await input.press('Enter')

  const log = panel.getByRole('log', { name: '助理' })
  await expect(log.locator('details').filter({ hasText: '查為什麼沒入庫' })).toContainText('完成')
  await expect(log).toContainText('結論 awaiting_review')
  await shot(page, 'crew-answered')

  const usage = await page.request.get('/api/settings/usage')
  expect(usage.status()).toBe(403)
})

// 放在最後：斷路器一開就暫停 15 分鐘，之後的流程都問不了。
test('provider 連續出錯 5 次：側面板說暫停到幾點，再送被擋下（M5 票 20、22）', async ({ page }) => {
  await signIn(page, '/jobs')
  await page.getByRole('button', { name: '助理' }).click()
  const panel = page.locator('#agent-panel')
  const input = panel.getByRole('textbox', { name: '問助理' })
  const log = panel.getByRole('log', { name: '助理' })
  // 關著：沒有暫停那一塊。
  await expect(input).toBeVisible()
  await expect(panel.getByText('助理暫停到')).toHaveCount(0)

  for (let failures = 1; failures <= 5; failures++) {
    await input.fill('provider 壞了')
    await input.press('Enter')
    await expect(log.locator('[data-stop]')).toHaveCount(failures)
  }

  // 開了：一般使用者也看得到到幾點；管理員另有錯誤原文。
  await expect(panel.getByText('助理暫停到')).toBeVisible()
  await expect(panel.getByText('錯誤原文')).toBeVisible()
  await expectNoHorizontalScroll(page)
  await shot(page, 'paused')

  await input.fill('還在嗎')
  await input.press('Enter')
  await expect(panel.getByText(/AI 服務暫停中/)).toBeVisible()
  await expect(input).toHaveValue('還在嗎')

  // 重新載入照樣看得到（狀態在伺服器上）。
  await page.reload()
  await expect(panel.getByText('助理暫停到')).toBeVisible()
})

async function expectNoHorizontalScroll(page: import('@playwright/test').Page) {
  const overflow = await page.evaluate(
    '[document.documentElement.scrollWidth, window.innerWidth, document.querySelector("#agent-panel").scrollWidth, document.querySelector("#agent-panel").clientWidth]',
  )
  const [pageWidth, viewport, panelWidth, panelClient] = overflow as number[]
  expect(pageWidth).toBeLessThanOrEqual(viewport)
  expect(panelWidth).toBeLessThanOrEqual(panelClient)
}
