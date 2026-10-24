import { fireEvent, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { AiUsage, UsageTally } from '../api/ai'
import { HEALTHY, stubApi } from '../test/fetch'
import { renderApp } from '../test/render'

afterEach(() => {
  vi.unstubAllGlobals()
})

const EMPTY: UsageTally = {
  calls: 0,
  failed: 0,
  input_tokens: 0,
  output_tokens: 0,
  cache_write_tokens: 0,
  cache_read_tokens: 0,
  hit_rate: null,
  cache_unreported: 0,
}

const BUSY: UsageTally = {
  calls: 12,
  failed: 2,
  input_tokens: 40000,
  output_tokens: 1500,
  cache_write_tokens: 6000,
  cache_read_tokens: 18000,
  hit_rate: 0.45,
  cache_unreported: 3,
}

function week(last: UsageTally, first: UsageTally = EMPTY): AiUsage['days'] {
  return [18, 19, 20, 21, 22, 23, 24].map((day, index) => ({
    date: `2026-10-${day}`,
    tally: index === 6 ? last : index === 0 ? first : EMPTY,
  }))
}

const USED: AiUsage = {
  has_any: true,
  since: '2026-10-18',
  until: '2026-10-24',
  totals: BUSY,
  days: week(BUSY),
  by_origin: [{ origin: 'test', tally: BUSY }],
  by_model: [{ format: 'anthropic', host: 'openrouter.ai', model: 'claude-opus-5-5', tally: BUSY }],
  by_user: [{ user_id: null, name: null, tally: BUSY }],
  failures: [{ failure: 'rate_limited', calls: 2 }],
}

const NEVER: AiUsage = {
  ...USED,
  has_any: false,
  totals: EMPTY,
  days: week(EMPTY),
  by_origin: [],
  by_model: [],
  by_user: [],
  failures: [],
}

function render(byDays: Partial<Record<7 | 30 | 90, AiUsage>>) {
  return stubApi({
    'GET /api/health': { body: HEALTHY },
    'GET /api/auth/me': { body: { name: 'skipper', role: 'admin' } },
    ...Object.fromEntries(
      Object.entries(byDays).map(([days, body]) => [
        `GET /api/settings/ai/usage?days=${days}`,
        { body },
      ]),
    ),
  })
}

describe('設定 → 用量', () => {
  it('分頁列最後一格是用量，當前頁', async () => {
    render({ 30: USED })
    renderApp('/settings/usage')

    const tabs = within(await screen.findByRole('navigation', { name: '設定' }))
    expect(tabs.getAllByRole('link').at(-1)).toHaveTextContent('用量')
    expect(tabs.getByRole('link', { name: '用量' })).toHaveAttribute('data-status', 'active')
  })

  it('一筆都沒有：說怎麼開始，連到 AI 設定，不畫圖', async () => {
    render({ 30: NEVER })
    renderApp('/settings/usage')

    expect(await screen.findByText(/還沒有任何 AI 呼叫/)).toBeVisible()
    expect(screen.getByRole('link', { name: '前往 AI 設定' })).toHaveAttribute(
      'href',
      '/settings/ai',
    )
    expect(screen.queryByTestId('usage-bar')).toBeNull()
  })

  it('總量、命中率與沒回報的次數；讀數平常說最後一天', async () => {
    render({ 30: USED })
    renderApp('/settings/usage')

    const totals = within(await screen.findByRole('region', { name: '這段期間的總量' }))
    expect(totals.getByText('40,000')).toBeVisible()
    expect(totals.getByText('45%')).toBeVisible()
    expect(totals.getByText('3 次沒回報快取，不算在內。')).toBeVisible()
    expect(screen.getByTestId('usage-readout')).toHaveTextContent('2026-10-24')
    expect(screen.getByTestId('usage-readout')).toHaveTextContent('快取讀取 18,000')
    expect(screen.getByTestId('usage-readout')).toHaveTextContent('其他輸入 22,000')
  })

  it('滑過一根，讀數換成那一天', async () => {
    render({ 30: USED })
    renderApp('/settings/usage')

    const bars = await screen.findAllByTestId('usage-bar')
    fireEvent.pointerEnter(bars[2])

    expect(screen.getByTestId('usage-readout')).toHaveTextContent('2026-10-20')
    expect(screen.getByTestId('usage-readout')).toHaveTextContent('沒有呼叫')
  })

  it('明細：出處、模型帶主機、沒有人的那一列、失敗的原因', async () => {
    render({ 30: USED })
    renderApp('/settings/usage')

    expect(
      within(await screen.findByRole('table', { name: '依出處' })).getByText('設定頁的測試'),
    ).toBeVisible()
    expect(
      within(screen.getByRole('table', { name: '依格式與模型' })).getByText(
        'Anthropic · openrouter.ai',
      ),
    ).toBeVisible()
    expect(
      within(screen.getByRole('table', { name: '依人' })).getByText(
        '沒有人（背景任務或已刪除的使用者）',
      ),
    ).toBeVisible()
    expect(within(screen.getByRole('table', { name: '沒成的' })).getByText('被限流')).toBeVisible()
  })

  it('OpenAI 相容格式的那一列說出格式名，不是 i18n key', async () => {
    render({
      30: {
        ...USED,
        by_model: [{ format: 'openai', host: 'ollama:11434', model: 'qwen3', tally: BUSY }],
      },
    })
    renderApp('/settings/usage')

    expect(
      within(await screen.findByRole('table', { name: '依格式與模型' })).getByText(
        'OpenAI 相容 · ollama:11434',
      ),
    ).toBeVisible()
  })

  it('換期間：問 7 天那一段，網址帶 days', async () => {
    const stub = render({ 30: USED, 7: { ...USED, totals: { ...BUSY, input_tokens: 777 } } })
    const user = userEvent.setup()
    const { router } = renderApp('/settings/usage')

    await user.click(await screen.findByRole('link', { name: '7 天' }))

    expect(await screen.findByText('777')).toBeVisible()
    expect(router.state.location.search).toEqual({ days: 7 })
    expect(stub).toHaveBeenCalledWith('/api/settings/ai/usage?days=7', expect.anything())
  })

  it('這段期間沒有、之前有：總量照畫，給看 90 天的連結', async () => {
    render({ 30: { ...NEVER, has_any: true } })
    renderApp('/settings/usage')

    expect(await screen.findByText('這段期間沒有呼叫。')).toBeVisible()
    expect(screen.getByRole('link', { name: '看 90 天' })).toHaveAttribute(
      'href',
      '/settings/usage?days=90',
    )
    expect(screen.queryByRole('table', { name: '依出處' })).toBeNull()
  })
})
