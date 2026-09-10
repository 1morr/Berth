import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Job, JobEvent } from '../api/jobs'
import { HEALTHY, stubApi, type StubRoute } from '../test/fetch'
import { renderApp } from '../test/render'

afterEach(() => {
  vi.unstubAllGlobals()
})

const JOBS = 'GET /api/jobs'
const HASH = '4bd0f6ef1d3b1e3cbb1e1b6b6c2a9c7d8e5f0a1b'
const EVENTS = `GET /api/jobs/${HASH}/events`

function job(overrides: Partial<Job> = {}): Job {
  return {
    hash: HASH,
    name: '[ANi] SPY×FAMILY - 13 [1080P][WEB-DL][AAC AVC][CHT]',
    state: 'submitted',
    trigger: 'manual',
    trigger_ref: '',
    error: '',
    media_id: 'tv:120089',
    media_title: 'SPY x FAMILY',
    route_id: 2,
    route_name: 'Anime',
    route_slug: 'anime',
    user_id: 1,
    user_name: 'skipper',
    save_path: '',
    content_path: '',
    total_size: 0,
    progress: 0,
    client_state: '',
    added_at: '2026-09-10T12:00:00Z',
    completed_at: null,
    imported_at: null,
    retryable: false,
    ...overrides,
  }
}

const FAILED = job({
  hash: 'aa11bb22cc33dd44ee55ff66aa77bb88cc99dd00',
  name: 'Moana 2 (2024) 1080p WEBRip 5.1 x264 -YTS',
  state: 'submit_failed',
  error: 'torrents/add: connection refused',
  media_id: 'movie:1241982',
  media_title: 'Moana 2',
  route_name: 'Movies',
  route_slug: 'movies',
  retryable: true,
})

function events(rows: JobEvent[] = []): StubRoute {
  return { body: rows }
}

function event(overrides: Partial<JobEvent> = {}): JobEvent {
  return {
    id: 1,
    type: 'created',
    actor: '1',
    payload: { route: 'anime', trigger: 'manual' },
    created_at: '2026-09-10T12:00:00Z',
    ...overrides,
  }
}

function render(routes: Record<string, StubRoute | (() => StubRoute)> = {}) {
  return stubApi({
    'GET /api/health': { body: HEALTHY },
    'GET /api/auth/me': { body: { name: 'skipper', role: 'admin' } },
    [JOBS]: { body: [job()] },
    [EVENTS]: events(),
    ...routes,
  })
}

describe('下載列表頁', () => {
  it('列出每一筆 Job 的狀態、作品、Route 與 trigger（票 09 驗收）', async () => {
    render()
    renderApp('/jobs')

    const row = await screen.findByText(/SPY×FAMILY - 13/)
    const list = within(row.closest('details') as HTMLElement)
    expect(list.getByText('已送出')).toBeInTheDocument()
    expect(list.getByRole('link', { name: 'SPY x FAMILY' })).toBeInTheDocument()
    expect(list.getByText('Anime')).toBeInTheDocument()
    expect(list.getByText('手動')).toBeInTheDocument()
  })

  it('進度還沒有值時那一格是 `—` 而不是 0%', async () => {
    render()
    renderApp('/jobs')
    await screen.findByText(/SPY×FAMILY - 13/)

    expect(screen.getByText('進度 —')).toBeInTheDocument()
    // 大小同理：這一列沒有欄頭，光一條破折號說不出自己少了什麼。
    expect(screen.getByText('大小 —')).toBeInTheDocument()
  })

  it('poller 報回進度之後那一格就是百分比（票 10）', async () => {
    render({ [JOBS]: { body: [job({ state: 'downloading', progress: 0.42, total_size: 1400 })] } })
    renderApp('/jobs')
    await screen.findByText(/SPY×FAMILY - 13/)

    expect(screen.getByText('進度 42%')).toBeInTheDocument()
    expect(screen.getByText('下載中')).toBeInTheDocument()
  })

  it('最新的在前面', async () => {
    // 後端已經照 `added_at` 由新到舊排好；畫面照收，不重排（shape brief §3）。
    render({ [JOBS]: { body: [FAILED, job()] } })
    renderApp('/jobs')
    await screen.findByText(/Moana 2 \(2024\)/)

    const names = screen.getAllByRole('listitem').map((row) => row.textContent ?? '')
    expect(names[0]).toContain('Moana 2 (2024)')
    expect(names[1]).toContain('SPY×FAMILY')
  })

  it('一筆都沒有時說得出下一步，而不是一片空白', async () => {
    render({ [JOBS]: { body: [] } })
    renderApp('/jobs')

    expect(await screen.findByText(/還沒有送過任何下載/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '回探索頁' })).toBeInTheDocument()
  })

  it('後端不可達時說的是 Berth 自己，不是索引站', async () => {
    render({ [JOBS]: { status: 500, body: { detail: 'boom' } } })
    renderApp('/jobs')

    expect(await screen.findByText(/讀不到下載列表/)).toBeInTheDocument()
  })

  describe('就地展開', () => {
    it('展開才去問時間線——一份清單裡多數列不會被展開', async () => {
      const stub = render({
        [EVENTS]: events([event(), event({ id: 2, type: 'submitted' })]),
      })
      renderApp('/jobs')
      await screen.findByText(/SPY×FAMILY - 13/)

      expect(stub.mock.calls.some(([url]) => String(url).includes('/events'))).toBe(false)

      await userEvent.click(screen.getByText(/SPY×FAMILY - 13/))

      expect(await screen.findByText('route=anime')).toBeInTheDocument()
    })

    it('送單失敗那一筆展開後有原文與一顆重試', async () => {
      render({
        [JOBS]: { body: [FAILED] },
        [`GET /api/jobs/${FAILED.hash}/events`]: events([
          event({ type: 'submit_failed', payload: { error: 'torrents/add: connection refused' } }),
        ]),
      })
      renderApp('/jobs')
      await userEvent.click(await screen.findByText(/Moana 2 \(2024\)/))

      expect(await screen.findByText('torrents/add: connection refused')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: '重新送單' })).toBeInTheDocument()
    })

    it('沒有失敗的那一筆沒有重試鍵——重試是那一條轉換，不是「再送一次」', async () => {
      render()
      renderApp('/jobs')
      await userEvent.click(await screen.findByText(/SPY×FAMILY - 13/))

      expect(screen.queryByRole('button', { name: '重新送單' })).not.toBeInTheDocument()
    })

    it('重試被擋下來時說的是那個理由，不是一句通用的失敗', async () => {
      render({
        [JOBS]: { body: [FAILED] },
        [`GET /api/jobs/${FAILED.hash}/events`]: events([]),
        [`POST /api/jobs/${FAILED.hash}/retry`]: {
          status: 409,
          body: { detail: { reason: 'route_unhealthy', detail: 'movies' } },
        },
      })
      renderApp('/jobs')
      await userEvent.click(await screen.findByText(/Moana 2 \(2024\)/))

      await userEvent.click(screen.getByRole('button', { name: '重新送單' }))

      expect(await screen.findByRole('alert')).toHaveTextContent(/那條 Route 現在是紅的/)
    })
  })
})
