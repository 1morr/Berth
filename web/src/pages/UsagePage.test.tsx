import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { DayUsage, Usage } from '../api/usage'
import { HEALTHY, stubApi, type StubRoutes } from '../test/fetch'
import { renderApp } from '../test/render'

/**
 * AI 用量頁（M5 票 21，`.scratch/m5/usage-and-run-shape.md`）：不知道的不當 0、花費只提醒、
 * 每一輪連到步驟頁。只有管理員進得來由 `router.test.tsx` 守著。
 */

afterEach(() => {
  vi.unstubAllGlobals()
})

const READ = 'GET /api/settings/usage'
const SAVE = 'PUT /api/settings/usage/alert'

function day(overrides: Partial<DayUsage>): DayUsage {
  return {
    day: '2026-10-27',
    calls: 0,
    input_tokens: 0,
    new_input: 0,
    cache_read: { known: 0, counted: 0, unknown: 0 },
    cache_write: { known: 0, counted: 0, unknown: 0 },
    output_tokens: 0,
    hit_rate: null,
    cost: { known: 0, counted: 0, unknown: 0 },
    web_searches: 0,
    tavily_searches: 0,
    ...overrides,
  }
}

const TODAY = day({
  calls: 3,
  input_tokens: 11000,
  new_input: 1000,
  cache_read: { known: 9500, counted: 3, unknown: 0 },
  // 一次走 OpenAI 相容接口：快取寫沒報。
  cache_write: { known: 500, counted: 2, unknown: 1 },
  output_tokens: 500,
  hit_rate: 0.8636,
  // 一次查不到價目。
  cost: { known: 0.0312, counted: 2, unknown: 1 },
  web_searches: 2,
  tavily_searches: 1,
})

const OLD = day({
  day: '2026-10-24',
  calls: 1,
  input_tokens: 2000,
  new_input: 2000,
  output_tokens: 50,
  hit_rate: 0,
  // 全部不知道：寫「未知」，不是 $0。
  cost: { known: 0, counted: 0, unknown: 1 },
  cache_write: { known: 0, counted: 0, unknown: 1 },
})

const USAGE: Usage = {
  today: '2026-10-27',
  days: [TODAY, OLD],
  totals: { ...TODAY, calls: 4, cost: { known: 0.0312, counted: 2, unknown: 2 } },
  runs_count: 2,
  guards: {
    stops: {
      request_limit: 0,
      token_limit: 0,
      repeated_call: 1,
      ping_pong: 0,
      no_progress: 0,
      circuit_open: 0,
      error: 0,
      cancelled: 0,
    },
    blocked: 2,
    refused: 0,
    failed: 0,
    truncated: 1,
  },
  runs: [
    {
      id: 'run-1',
      started_at: '2026-10-27T02:00:00Z',
      user_name: 'deckhand',
      stop_reason: 'repeated_call',
      requests: 4,
      tool_calls: 4,
      input_tokens: 9000,
      output_tokens: 300,
      cost_usd: 0.0312,
    },
  ],
  prices: [
    {
      model: 'claude-sonnet-5-5',
      base_url: 'https://api.anthropic.com',
      price: {
        input: '2',
        output: '10',
        cache_read: '0.10',
        cache_write: '2.5',
        source: { table: 'genai_prices', version: '0.1.13', provider: 'Anthropic', verified: null },
      },
    },
    {
      model: 'deepseek-flash',
      base_url: null,
      price: {
        input: '0.3',
        output: '1.2',
        cache_read: '0.006',
        cache_write: '0.3',
        source: { table: 'berth', version: '', provider: '', verified: '2026-10-28' },
      },
    },
    { model: 'my-local-llm', base_url: 'https://llm.home.example/v1', price: null },
  ],
  daily_alert_usd: null,
  spend: { alerts: [], unknown_today: 0, unknown_before: 0 },
}

function render(routes: StubRoutes = {}, usage: Usage = USAGE) {
  return stubApi({
    'GET /api/health': { body: HEALTHY },
    'GET /api/auth/me': { body: { name: 'skipper', role: 'admin' } },
    [READ]: { body: usage },
    ...routes,
  })
}

describe('設定 → 用量', () => {
  it('分頁列：用量在 AI 之後，是當前頁', async () => {
    render()
    renderApp('/settings/usage')

    const tabs = within(await screen.findByRole('navigation', { name: '設定' }))
    const names = tabs.getAllByRole('link').map((link) => link.textContent)
    expect(names.slice(-3)).toEqual(['通知', 'AI', '用量'])
    expect(tabs.getByRole('link', { name: '用量' })).toHaveAttribute('data-status', 'active')
  })

  it('逐日表：不知道的寫「—」與「+未知」，全部不知道寫「未知」，不當 0', async () => {
    render()
    renderApp('/settings/usage')

    const table = await screen.findByRole('table', { name: '近 30 天每天的用量，新的在上' })
    const [, today, old] = within(table).getAllByRole('row')
    expect(within(today).getByRole('rowheader')).toHaveTextContent('2026-10-27 · 今天')
    expect(within(today).getAllByText('$0.0312 +未知')[0]).toHaveAttribute(
      'title',
      '1 次呼叫的費用算不進去',
    )
    expect(within(today).getAllByText('500 +未知').length).toBeGreaterThan(0)
    expect(within(today).getAllByText('86%').length).toBeGreaterThan(0)
    expect(within(today).getAllByText('2 · Tavily 1').length).toBeGreaterThan(0)
    expect(within(old).getAllByText('未知').length).toBeGreaterThan(0)
    expect(within(old).getAllByText('—').length).toBeGreaterThan(0)
    expect(within(old).queryByText('$0.00')).not.toBeInTheDocument()
  })

  it('防護的計數 0 的也列；最近的輪連到步驟頁', async () => {
    render()
    renderApp('/settings/usage')

    const stops = (await screen.findByRole('heading', { name: '一輪停在哪裡' })).closest('section')!
    expect(within(stops).getByText('同一個呼叫重複').nextSibling).toHaveTextContent('1 次')
    expect(within(stops).getByText('兩個呼叫來回打轉').nextSibling).toHaveTextContent('0 次')
    expect(screen.getByText('被擋下（重複第 3 次、第 4 次）').nextSibling).toHaveTextContent('2 次')
    const runs = screen.getByRole('table', { name: '最近 20 輪，新的在上' })
    expect(within(runs).getByRole('link')).toHaveAttribute('href', '/agent/runs/run-1')
  })

  it('費用怎麼算：每組端點與模型附價目來源，查不到的寫未知，網搜與 Tavily 另外說', async () => {
    render()
    renderApp('/settings/usage')

    expect(
      await screen.findByText(
        /^api\.anthropic\.com · claude-sonnet-5-5：輸入 \$2、.*價目來源：genai-prices 0\.1\.13（Anthropic）。$/,
      ),
    ).toBeVisible()
    expect(
      screen.getByText(
        /^deepseek-flash（舊紀錄，沒記端點）：.*價目來源：Berth 補位表（2026-10-28 查證）。$/,
      ),
    ).toBeVisible()
    expect(
      screen.getByText('llm.home.example/v1 · my-local-llm：這個端點查不到價目，費用未知。'),
    ).toBeVisible()
    expect(screen.getByText(/先照端點的網址認出服務商/)).toBeVisible()
    expect(screen.getByText(/上面列的是現在這個時段的價/)).toBeVisible()
    expect(screen.getByText(/每次 \$0\.01，已算進估計費用/)).toBeVisible()
    expect(screen.getByText(/Tavily 花的是你 Tavily 帳號的 credit/)).toBeVisible()
  })

  it('提醒只是一句話：今天超過提醒值、異常各一則', async () => {
    render(
      {},
      {
        ...USAGE,
        daily_alert_usd: 0.02,
        spend: {
          alerts: [
            { kind: 'threshold', today: '0.0312', against: '0.02' },
            { kind: 'anomaly', today: '0.0312', against: '0.002' },
          ],
          unknown_today: 0,
          unknown_before: 0,
        },
      },
    )
    renderApp('/settings/usage')

    expect(
      await screen.findByText('今天估計花了 $0.0312，超過你設的提醒值 $0.0200。AI 照常可用。'),
    ).toBeVisible()
    expect(screen.getByText(/近 14 天有用量那幾天的中位數 \$0\.0020 的 16 倍/)).toBeVisible()
    expect(screen.getByLabelText('每日提醒值（美元）')).toHaveValue(0.02)
  })

  it('提醒沒算進費用未知的呼叫時明說幾次，不讓「沒有提醒」像沒事', async () => {
    render({}, { ...USAGE, spend: { alerts: [], unknown_today: 1, unknown_before: 3 } })
    renderApp('/settings/usage')

    expect(
      await screen.findByText(
        '有 4 次呼叫的費用未知（今天 1 次、前 14 天 3 次），提醒沒算進它們：那幾次查不到價目。',
      ),
    ).toBeVisible()
    expect(screen.getByText('費用未知')).toBeVisible()
  })

  it('費用都知道時不多說', async () => {
    render()
    renderApp('/settings/usage')

    await screen.findByRole('table', { name: '近 30 天每天的用量，新的在上' })
    expect(screen.queryByText('費用未知')).not.toBeInTheDocument()
  })

  it('存提醒值；空著存是不提醒；負數不送', async () => {
    const stub = render({ [SAVE]: { body: { daily_usd: 1.5 } } })
    const user = userEvent.setup()
    renderApp('/settings/usage')

    const field = await screen.findByLabelText('每日提醒值（美元）')
    await user.type(field, '-1')
    await user.click(screen.getByRole('button', { name: '儲存' }))
    expect(screen.getByText('要是 0 以上的數字。')).toBeVisible()
    expect(stub.mock.calls.some(([, init]) => init?.method === 'PUT')).toBe(false)

    await user.clear(field)
    await user.type(field, '1.5')
    await user.click(screen.getByRole('button', { name: '儲存' }))
    expect(await screen.findByText('存好了：每天到 $1.50 提醒你。')).toBeVisible()
    const put = stub.mock.calls.findLast(([, init]) => init?.method === 'PUT')
    expect(JSON.parse(String(put?.[1]?.body))).toEqual({ daily_usd: 1.5 })

    await user.clear(field)
    await user.click(screen.getByRole('button', { name: '儲存' }))
    const cleared = stub.mock.calls.findLast(([, init]) => init?.method === 'PUT')
    expect(JSON.parse(String(cleared?.[1]?.body))).toEqual({ daily_usd: null })
  })
})
