import { screen, within } from '@testing-library/react'
import i18next from 'i18next'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { HealthDetail } from '../api/health'
import { HEALTHY, stubApi } from '../test/fetch'
import { healthDetail, notifyChannel } from '../test/fixtures'
import { renderApp } from '../test/render'

afterEach(() => {
  vi.unstubAllGlobals()
})

/** 開健康頁，回「通知」那一塊（區塊本身，與裡面可查詢的範圍）。 */
async function renderCard(
  notify: Partial<HealthDetail['notify']>,
  role: 'admin' | 'user' = 'admin',
  name = '通知',
) {
  stubApi({
    'GET /api/health': { body: HEALTHY },
    'GET /api/auth/me': { body: { name: 'someone', role } },
    'GET /api/health/detail': { body: healthDetail({ notify: notifyChannel(notify) }) },
  })
  renderApp('/health')
  const section = await screen.findByRole('region', { name })
  return { section, card: within(section) }
}

const LINK = { name: '通知設定' }
const FUTURE = new Date(Date.now() + 5 * 60_000 + 5_000).toISOString()

describe('健康頁的通知卡', () => {
  it('沒設定：說不送通知；admin 有設定連結', async () => {
    const { card } = await renderCard({})

    expect(card.getByText('還沒設定 Discord bot，不送通知。')).toBeVisible()
    expect(await card.findByRole('link', LINK)).toHaveAttribute('href', '/settings/notifications')
    expect(card.queryByText('上次送出')).not.toBeInTheDocument()
    expect(card.queryByText(/最多留 24 小時/)).not.toBeInTheDocument()
  })

  it('沒設定：一般使用者沒有設定連結', async () => {
    const { card } = await renderCard({}, 'user')

    expect(card.getByText('還沒設定 Discord bot，不送通知。')).toBeVisible()
    expect(card.queryByRole('link', LINK)).not.toBeInTheDocument()
  })

  it('正常：上次送出、等著送幾則、放棄期限', async () => {
    const { card } = await renderCard({
      configured: true,
      last_sent_at: new Date(Date.now() - 3 * 60_000 - 5_000).toISOString(),
      pending: 2,
    })

    expect(card.getByText('上次送出')).toBeVisible()
    expect(card.getByText('3 分鐘前')).toBeVisible()
    expect(card.getByText('2 則')).toBeVisible()
    expect(card.getByText(/最多留 24 小時/)).toBeVisible()
    expect(card.queryByText('已暫停')).not.toBeInTheDocument()
    expect(card.queryByText('下次嘗試')).not.toBeInTheDocument()
  })

  it('正常但從沒送過：說沒有紀錄', async () => {
    const { card } = await renderCard({ configured: true })

    expect(card.getByText('沒有紀錄')).toBeVisible()
  })

  it('token 被拒：唯一變紅的狀態；admin 看到補法與連結，原文收進技術細節', async () => {
    const { section, card } = await renderCard({
      configured: true,
      token_rejected: true,
      error: '401 Unauthorized',
    })

    expect(card.getByText('已暫停')).toHaveClass('bg-blocked')
    // 外框換重線（出事的卡片），紅色只在暫停章上。
    expect(section).toHaveClass('border-rule-strong')
    expect(card.getByText(/Discord 不再接受這個 bot token/)).toBeVisible()
    expect(card.getByText(/到設定 → 通知貼上新的 token/)).toBeVisible()
    expect(card.queryByText(/請管理員/)).not.toBeInTheDocument()
    expect(await card.findByRole('link', LINK)).toBeVisible()
    expect(card.getByText('401 Unauthorized')).toBeInTheDocument()
    expect(card.getByTestId('technical-details')).not.toHaveAttribute('open')
  })

  it('token 被拒：一般使用者被指去找管理員，沒有連結', async () => {
    const { card } = await renderCard(
      { configured: true, token_rejected: true, error: '401 Unauthorized' },
      'user',
    )

    expect(card.getByText('請管理員到設定 → 通知換一個 bot token。')).toBeVisible()
    expect(card.queryByText(/到設定 → 通知貼上新的 token/)).not.toBeInTheDocument()
    expect(card.queryByRole('link', LINK)).not.toBeInTheDocument()
  })

  it('連不上：連續失敗、下次嘗試、原文；沒有紅色的暫停章，線變重', async () => {
    const { section, card } = await renderCard({
      configured: true,
      failures: 3,
      error: 'ConnectError: boom',
      failed_at: new Date().toISOString(),
      resume_at: FUTURE,
    })

    expect(card.getByText('連不上 Discord，Berth 會自己再試。')).toBeVisible()
    expect(card.getByText('下次嘗試')).toBeVisible()
    expect(card.getByText('5 分鐘後')).toBeVisible()
    expect(card.getByText('連續失敗')).toBeVisible()
    expect(card.getByText('3')).toHaveClass('text-blocked-ink')
    expect(card.getByText('ConnectError: boom')).toBeInTheDocument()
    expect(card.queryByText('已暫停')).not.toBeInTheDocument()
    expect(section).toHaveClass('border-rule-strong')
  })

  it('整個 bot 被限速：沒有連續失敗，說 Discord 要 Berth 先等', async () => {
    const { card } = await renderCard({
      configured: true,
      failures: 0,
      error: '429 Too Many Requests',
      resume_at: FUTURE,
    })

    expect(card.getByText(/Discord 要 Berth 先等一下/)).toBeVisible()
    expect(card.getByText('下次嘗試')).toBeVisible()
    expect(card.queryByText('連續失敗')).not.toBeInTheDocument()
    expect(card.queryByText('已暫停')).not.toBeInTheDocument()
  })

  it('英文介面：token 被拒', async () => {
    await i18next.changeLanguage('en')
    try {
      const { card } = await renderCard(
        { configured: true, token_rejected: true, error: '401' },
        'admin',
        'Notifications',
      )

      expect(card.getByText('Paused')).toBeVisible()
      expect(card.getByText(/Paste a new token under Settings → Notifications/)).toBeVisible()
      expect(await card.findByRole('link', { name: 'Notification settings' })).toBeVisible()
    } finally {
      await i18next.changeLanguage('zh-Hant')
    }
  })
})
