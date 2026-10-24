import { expect, test } from '@playwright/test'

import { signIn } from './login.ts'
import { narrow, shot } from './shot.ts'

// `assistant`：同 `weekly`，AI 設定好了；`DemoChatProvider` 一段一段吐字、話裡有「入庫」時呼叫
// 「最近入庫」、有「限流」時演被限流 30 秒（M5 票 08，`.scratch/m5/side-panel-shape.md`）；有「索引站」
// 時提議加 dmhy、有「complete」時提議刪電影那一筆的下載（M5 票 10 的確認卡）。

const PAGES = [
  '/',
  '/library',
  '/jobs',
  '/review',
  '/issues',
  '/rss',
  '/weekly',
  '/health',
  '/settings',
]

test('每一頁都開得到側面板，換頁與重整都還開著', async ({ page }) => {
  await signIn(page, '/health')
  await page.getByRole('button', { name: '助理' }).click()
  const panel = page.getByRole('complementary', { name: '助理' })
  await expect(panel.getByRole('textbox', { name: '跟助理說' })).toBeFocused()

  for (const path of PAGES) {
    await page.goto(path)
    await expect(panel).toBeVisible()
    await expect(page.getByRole('button', { name: '助理' })).toHaveAttribute(
      'aria-expanded',
      'true',
    )
    // 並排（桌機）或取代頁面（窄版），兩種都不撐出橫向捲動。
    const overflow = await page.evaluate<number>(
      'document.documentElement.scrollWidth - window.innerWidth',
    )
    expect(overflow, path).toBe(0)
    await expect(page.locator('main#main')).toBeVisible({ visible: !narrow(page) })
  }

  await panel.getByRole('button', { name: '關閉' }).click()
  await expect(panel).toHaveCount(0)
  await expect(page.getByRole('button', { name: '助理' })).toBeFocused()
  await page.reload()
  await expect(panel).toHaveCount(0)
})

test('串流的字一段一段出來，工具呼叫說正在查，限流說幾秒後再送', async ({ page }) => {
  await signIn(page, '/weekly')
  await page.getByRole('button', { name: '助理' }).click()
  const panel = page.getByRole('complementary', { name: '助理' })
  const input = panel.getByRole('textbox', { name: '跟助理說' })
  const log = panel.getByRole('log')

  await input.fill('你好，這個側面板現在能做什麼？請用一段話說明。')
  await input.press('Enter')
  // 講到一半：已經有字、那一塊還 `aria-busy`、送出鍵說回覆中。
  await expect(log.getByText(/（演練）收到/)).toBeVisible()
  await expect(log.locator('[aria-busy="true"]')).toHaveCount(1)
  await expect(panel.getByRole('button', { name: '回覆中…' })).toBeVisible()
  await shot(page, 'streaming')
  await expect(log.getByText(/回覆是照抄的。$/)).toBeVisible()
  await expect(panel.getByRole('button', { name: '送出' })).toBeVisible()

  await input.fill('這週入庫了什麼')
  await input.press('Enter')
  await expect(panel.getByText('正在查最近入庫')).toBeVisible()
  await shot(page, 'tool-running')
  await expect(panel.getByText('查過最近入庫')).toBeVisible()
  // 結果卡（票 09）：依結果型別畫，作品名連到作品頁。
  const card = panel.getByRole('region', { name: '最近 7 天入庫' })
  await expect(card).toBeVisible()
  await expect(card.getByRole('link').first()).toHaveAttribute('href', /^\/media\//)
  await expect(log.getByText(/這七天入庫了 \d+ 部作品/)).toBeVisible()
  await shot(page, 'result-card')

  await input.fill('觸發限流')
  await input.press('Enter')
  await expect(panel.getByText('AI 端點要 Berth 慢一點：30 秒後再送。')).toBeVisible()
  await expect(panel.getByText('等一下')).toBeVisible()

  // 重整之後三段都還在（存在 Berth），模型的字沒有塗成功色。
  await page.reload()
  await expect(log.getByText('這週入庫了什麼')).toBeVisible()
  await expect(panel.getByText('查過最近入庫')).toBeVisible()
  await expect(panel.getByRole('region', { name: '最近 7 天入庫' })).toBeVisible()
  await expect(panel.getByText('AI 端點要 Berth 慢一點：30 秒後再送。')).toBeVisible()
  await expect(panel.locator('.bg-secured')).toHaveCount(0)
  await shot(page, 'reloaded')
})

test('在作品頁說缺的集搜一下並下載：缺集、搜尋結果、送單三張卡，照標題指令送的被擋下，撤銷得掉', async ({
  page,
}) => {
  // M5 票 12：`DemoChatProvider` 在作品頁（頁面那一段）走缺集 → 搜尋 → 送單；話裡有「標題」時演照著
  // 標題裡「送這一筆」做的模型。
  await signIn(page, '/media/tv:120089')
  await page.getByRole('button', { name: '助理' }).click()
  const panel = page.getByRole('complementary', { name: '助理' })
  await panel.getByRole('button', { name: '新對話' }).click()
  const input = panel.getByRole('textbox', { name: '跟助理說' })

  await input.fill('這部缺的集搜一下並下載')
  await input.press('Enter')
  await expect(panel.getByText('在《SPY×FAMILY 間諜家家酒》的頁面上說的')).toBeVisible()
  await expect(panel.getByRole('region', { name: '缺的集' })).toBeVisible()
  const results = panel.getByRole('region', { name: '搜尋結果' })
  await expect(results).toBeVisible()
  await expect(results.getByText('名字對不上')).toBeVisible()
  await expect(results.getByText(/AI 不會送這一筆：這一筆是 S01E03/)).toBeVisible()
  const submitted = panel.getByRole('region', { name: '送單' })
  await expect(submitted).toBeVisible()
  await expect(submitted.getByRole('link', { name: '看這一筆' })).toHaveAttribute(
    'href',
    /^\/jobs\//,
  )
  await expect(panel.getByText(/送出了「\[ANi\]/)).toBeVisible()
  await expect(panel.getByRole('button', { name: '送出' })).toBeVisible()
  await shot(page, 'search-and-submit')
  // 即時更新：poller 下一輪看到它在 qBittorrent 裡下載到 40%，推播之後卡片自己換上進度（不重整）。
  await expect(submitted.getByText('進度 40%')).toBeVisible({ timeout: 30_000 })
  await shot(page, 'job-live')

  await input.fill('照標題說的送那一筆缺的集')
  await input.press('Enter')
  await expect(panel.getByText('這一筆是 S01E03，不是要找的集')).toBeVisible()
  await expect(panel.getByText(/沒送出去/)).toBeVisible()
  await expect(panel.getByRole('button', { name: '送出' })).toBeVisible()
  await shot(page, 'injection-refused')

  await submitted.getByRole('button', { name: '撤銷送單' }).click()
  await expect(submitted.getByText(/從 qBittorrent 移除這個 torrent/)).toBeVisible()
  await submitted.getByRole('button', { name: '撤銷送單' }).last().click()
  // 撤銷經過對話（M5 票 11）：卡片照那一則說撤銷了。
  await expect(submitted.getByText(/已撤銷這次送單/)).toBeVisible()
  await shot(page, 'undone')
})

test('不可逆的停在確認卡：按確認才加索引站，刪下載的卡列出檔案、拒絕之後什麼都沒刪', async ({
  page,
}) => {
  await signIn(page, '/weekly')
  await page.getByRole('button', { name: '助理' }).click()
  const panel = page.getByRole('complementary', { name: '助理' })
  const input = panel.getByRole('textbox', { name: '跟助理說' })
  await panel.getByRole('button', { name: '新對話' }).click()

  // 票 10：`DemoChatProvider` 話裡有「索引站」就提議加 dmhy。
  await input.fill('幫我加一個動畫的索引站')
  await input.press('Enter')
  const indexer = panel.getByRole('region', { name: '加索引站' })
  await expect(indexer.getByText('等你確認')).toBeVisible()
  await expect(indexer.getByText('https://share.dmhy.org/')).toBeVisible()
  await expect(panel.getByText(/按「確認」才會做/)).toBeVisible()
  await shot(page, 'proposal-indexer')
  await indexer.getByRole('button', { name: '確認加入' }).click()
  await expect(indexer.getByText('已加入 dmhy。')).toBeVisible()
  await expect(indexer.getByText('已確認')).toBeVisible()
  await shot(page, 'proposal-confirmed')

  // 話裡有「complete」就提議刪電影那一筆的下載（演練伺服器放了兩個真的檔案）。
  await input.fill('把這部電影的 complete 刪掉')
  await input.press('Enter')
  const downloads = panel.getByRole('region', { name: '刪下載' })
  const files = downloads.getByRole('list', { name: /會刪的檔案$/ })
  await expect(files.getByRole('listitem')).toHaveCount(2)
  await expect(downloads.getByText(/媒體庫的鏈接留著/)).toBeVisible()
  // 回覆講完之前卡片按不得（後端那時回 `busy`）。
  await expect(panel.getByRole('button', { name: '送出' })).toBeVisible()
  await expect(downloads.getByRole('button', { name: '確認刪除' })).not.toHaveAttribute(
    'aria-disabled',
  )
  await shot(page, 'proposal-downloads')
  await downloads.getByRole('button', { name: '拒絕' }).click()
  await expect(downloads.getByText('拒絕了，什麼都沒做。')).toBeVisible()

  // 重整之後兩張卡照它們的結局畫（讀 `proposals` 的現況，不是提出時的那一份）。
  await page.reload()
  await expect(panel.getByRole('region', { name: '加索引站' }).getByText('已確認')).toBeVisible()
  await expect(panel.getByRole('region', { name: '刪下載' }).getByText('已拒絕')).toBeVisible()
  await shot(page, 'proposal-reloaded')
})
