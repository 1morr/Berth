import { expect, test } from '@playwright/test'

import { signIn } from './login.ts'
import { shot } from './shot.ts'

// `healthy`：精靈已跑完。設定 → 通知（M4 票 123）：演練後端的 Discord 替身（`FakeClientFactory._discord`）
// 拒絕 token `rejected`、到不了收件人 `1000000000000000404`，其餘一律送到。
test('通知設定：被拒的 token、接上 bot、到不了的收件人、再換成送得到的', async ({ page }) => {
  await signIn(page, '/settings/notifications')
  const main = page.getByRole('main')
  await expect(main.getByRole('heading', { level: 1, name: '通知設定' })).toBeVisible()
  const bot = main.getByRole('region', { name: 'Discord bot' })
  const me = main.getByRole('region', { name: '我的 Discord' })
  const test_ = main.getByRole('region', { name: '測試' })
  await expect(bot.getByText('還沒設定')).toBeVisible()
  await expect(test_.getByRole('button', { name: '送一則測試訊息給我' })).toHaveAttribute(
    'aria-disabled',
    'true',
  )
  await shot(page, '1-empty')

  // Discord 不接受的 token：就地標在欄位上，沒有存下。
  await bot.getByLabel('Bot token').fill('rejected')
  await bot.getByRole('button', { name: '儲存' }).click()
  await expect(bot.getByText('Discord 不接受這個 token。')).toBeVisible()
  await expect(bot.getByText('還沒設定')).toBeVisible()
  await shot(page, '2-token-rejected')

  // 正常的 token：存下，說出 bot 的名字與邀請連結；欄位清空。
  await bot.getByLabel('Bot token').fill('good-token')
  await bot.getByRole('button', { name: '儲存' }).click()
  await expect(bot.getByText('berth-demo')).toBeVisible()
  await expect(bot.getByText('已設定', { exact: true })).toBeVisible()
  await expect(bot.getByText(/discord\.com\/oauth2\/authorize/)).toBeVisible()
  await expect(bot.getByRole('link', { name: '開啟邀請連結' })).toHaveAttribute('target', '_blank')
  await expect(bot.getByLabel('Bot token')).toHaveValue('')
  await shot(page, '3-bot-set')

  // 還沒填 ID：測試鍵說缺什麼。
  await expect(
    test_.getByRole('button', { name: '送一則測試訊息給我' }),
  ).toHaveAccessibleDescription('要先填你的 Discord ID 並儲存。')

  // 收件人到不了：兩個補法一起說。
  await me.getByLabel('Discord 使用者 ID').fill('1000000000000000404')
  await me.getByRole('button', { name: '儲存' }).click()
  await expect(me.getByText('已儲存。')).toBeVisible()
  await test_.getByRole('button', { name: '送一則測試訊息給我' }).click()
  await expect(test_.getByText(/把 bot 加進你所在的伺服器/)).toBeVisible()
  await expect(test_.getByText(/打開「私人訊息」/)).toBeVisible()
  await shot(page, '4-recipient-unreachable')

  // 換成送得到的 ID，再測一次。
  await me.getByLabel('Discord 使用者 ID').fill('1000000000000000001')
  await me.getByRole('button', { name: '儲存' }).click()
  await expect(me.getByText('已儲存。')).toBeVisible()
  await test_.getByRole('button', { name: '送一則測試訊息給我' }).click()
  await expect(test_.getByText('已送出', { exact: true })).toBeVisible()
  await expect(test_.getByText('看看 Discord 的私訊。')).toBeVisible()
  await shot(page, '5-delivered')
})
