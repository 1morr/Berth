import { screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Run } from '../api/usage'
import { HEALTHY, stubApi, type StubRoutes } from '../test/fetch'
import { renderApp } from '../test/render'

/**
 * 每一輪的步驟頁（M5 票 21）：每一次模型呼叫與它叫的工具、被擋的理由、停止原因；被中止的那一輪也有數字；
 * 別人的與不存在的一樣是「找不到」。
 */

afterEach(() => {
  vi.unstubAllGlobals()
})

const STOPPED: Run = {
  id: 'run-1',
  user_name: 'deckhand',
  provider: 'anthropic',
  model: 'claude-sonnet-5-5',
  started_at: '2026-10-27T02:00:00Z',
  ended_at: '2026-10-27T02:00:12Z',
  stop_reason: 'repeated_call',
  error: '',
  continues: null,
  requests: 2,
  tool_calls: 3,
  input_tokens: 11000,
  output_tokens: 120,
  cache_read_tokens: 9000,
  cache_write_tokens: null,
  cost_usd: 0.0123,
  web_searches: 0,
  tavily_searches: 0,
  steps: [
    {
      step: 1,
      call: {
        model: 'claude-sonnet-5-5-20261001',
        input_tokens: 5000,
        output_tokens: 60,
        cache_read_tokens: 4000,
        cache_write_tokens: null,
        cost_usd: 0.006,
        web_searches: 0,
        finish_reason: 'tool_call',
        duration_ms: 1400,
        error: '',
        created_at: '2026-10-27T02:00:02Z',
      },
      tools: [
        {
          command: 'jobs.list_jobs',
          args_json: '{"page":1}',
          outcome: 'ok',
          detail: '',
          truncated: true,
          duration_ms: 35,
        },
      ],
    },
    {
      step: 2,
      call: {
        model: 'claude-sonnet-5-5-20261001',
        input_tokens: 6000,
        output_tokens: 60,
        cache_read_tokens: 5000,
        cache_write_tokens: null,
        cost_usd: null,
        web_searches: 0,
        finish_reason: 'tool_call',
        duration_ms: 900,
        error: '',
        created_at: '2026-10-27T02:00:05Z',
      },
      tools: [
        {
          command: 'jobs.list_jobs',
          args_json: '{"page":1}',
          outcome: 'blocked',
          detail: 'same call a third time; try something else',
          truncated: false,
          duration_ms: 0,
        },
        {
          command: 'skills.load_skill',
          args_json: '{"name":"why-not-imported"}',
          outcome: 'aborted',
          detail: '',
          truncated: false,
          duration_ms: 0,
        },
      ],
    },
  ],
}

function render(routes: StubRoutes) {
  return stubApi({
    'GET /api/health': { body: HEALTHY },
    'GET /api/auth/me': { body: { name: 'deckhand', role: 'user' } },
    ...routes,
  })
}

describe('一輪的步驟', () => {
  it('被中止的那一輪：停在哪、合計、每一步的數字與被擋的理由', async () => {
    render({ 'GET /api/agent/runs/run-1': { body: STOPPED } })
    renderApp('/agent/runs/run-1')

    expect(await screen.findByRole('heading', { level: 1, name: '這一輪的步驟' })).toBeVisible()
    expect(await screen.findByText('停下')).toBeVisible()
    expect(screen.getByText('同一個呼叫重複')).toBeVisible()
    const totals = screen.getByRole('heading', { name: '合計' }).closest('section')!
    expect(within(totals).getByText('11,000')).toBeVisible()
    // 快取寫接口沒報：「—」，不是 0。
    expect(within(totals).getByText('快取寫').nextSibling).toHaveTextContent('—')
    expect(within(totals).getByText('82%')).toBeVisible()
    expect(within(totals).getByText('12 s')).toBeVisible()

    const steps = screen.getAllByRole('listitem').filter((item) => item.querySelector('h3'))
    expect(steps.map((step) => within(step).getByRole('heading').textContent)).toEqual([
      '第 1 次模型呼叫',
      '第 2 次模型呼叫',
    ])
    expect(within(steps[0]).getByText('列出下載')).toBeVisible()
    expect(within(steps[0]).getByText('結果被截短')).toBeVisible()
    expect(within(steps[1]).getByText('被擋下')).toBeVisible()
    expect(within(steps[1]).getByText('same call a third time; try something else')).toBeVisible()
    expect(within(steps[1]).getByText('中止這一輪')).toBeVisible()
    // 認不得的工具照原文。
    expect(within(steps[1]).getByText('skills.load_skill')).toBeVisible()
    // 這一次的價錢不知道：未知，不是 $0。
    expect(within(steps[1]).getByText('未知')).toBeVisible()
  })

  it('出錯的一輪說出錯，原文收在技術細節', async () => {
    render({
      'GET /api/agent/runs/run-1': {
        body: { ...STOPPED, stop_reason: 'error', error: 'status_code: 429, rate limited' },
      },
    })
    renderApp('/agent/runs/run-1')

    expect(await screen.findByText('出錯')).toBeVisible()
    expect(screen.getByText('模型或 provider 出錯')).toBeVisible()
    expect(screen.getByText('status_code: 429, rate limited')).not.toBeVisible()
  })

  it('「繼續」來的一輪連回前一輪', async () => {
    render({
      'GET /api/agent/runs/run-2': { body: { ...STOPPED, id: 'run-2', continues: 'run-1' } },
    })
    renderApp('/agent/runs/run-2')

    expect(await screen.findByRole('link', { name: '看前一輪' })).toHaveAttribute(
      'href',
      '/agent/runs/run-1',
    )
  })

  it('還在跑的一輪說還在跑', async () => {
    render({
      'GET /api/agent/runs/run-1': {
        body: { ...STOPPED, stop_reason: null, ended_at: null },
      },
    })
    renderApp('/agent/runs/run-1')

    expect(await screen.findByText('進行中')).toBeVisible()
    expect(screen.getByText('還在跑')).toBeVisible()
  })

  it('別人的或不存在的：找不到', async () => {
    render({
      'GET /api/agent/runs/nope': {
        status: 404,
        body: { detail: { reason: 'run_missing', detail: 'nope' } },
      },
    })
    renderApp('/agent/runs/nope')

    expect(await screen.findByText('找不到這一輪：它不存在，或不是你的。')).toBeVisible()
  })
})
