import { screen, waitFor, within } from '@testing-library/react'
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
    replannable: false,
    plan_id: null,
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

  describe('匯入計劃（票 11）', () => {
    const PLANNED = job({ state: 'review', replannable: true, plan_id: 7 })
    const PLAN = 'GET /api/plans/7'

    function plan() {
      return {
        body: {
          id: 7,
          job_hash: HASH,
          status: 'pending_review',
          engine: 'rules',
          engine_version: '0.1.0',
          created_at: '2026-09-11T12:00:00Z',
          summary: {
            files: 0,
            high: 0,
            medium: 0,
            low: 1,
            actions: { review: 1 },
            review_reason: 'low_confidence',
          },
          items: [
            {
              id: 1,
              rel_path: 'Disc 1/theme.mkv',
              action: 'review',
              media_id: 'tv:120089',
              season: null,
              episode_start: null,
              episode_end: null,
              target_path: '',
              confidence: 'low',
              reasons: ['no season and episode could be worked out'],
              audit: false,
              error: '',
            },
          ],
        },
      }
    }

    it('展開才去問那一份計劃——與時間線同一條規則', async () => {
      const stub = render({ [JOBS]: { body: [PLANNED] }, [PLAN]: plan() })
      renderApp('/jobs')
      await screen.findByText(/SPY×FAMILY - 13/)

      expect(stub.mock.calls.some(([url]) => String(url).includes('/plans/'))).toBe(false)

      await userEvent.click(screen.getByText(/SPY×FAMILY - 13/))

      expect(await screen.findByText('Disc 1/theme.mkv')).toBeInTheDocument()
      expect(screen.getByText('no season and episode could be worked out')).toBeInTheDocument()
      expect(screen.getByText(/M1 還沒有審核佇列/)).toBeInTheDocument()
    })

    it('還沒算過的那一筆連問都不問——`plan_id` 是空的就是答案', async () => {
      const stub = render()
      renderApp('/jobs')
      await userEvent.click(await screen.findByText(/SPY×FAMILY - 13/))
      // 時間線問到了（空的），所以展開真的發生過——計劃那一支仍然一個請求都沒發。
      await screen.findByText('這一筆還沒有任何事件。')

      expect(stub.mock.calls.some(([url]) => String(url).includes('/plans/'))).toBe(false)
      expect(screen.queryByText('匯入計劃')).not.toBeInTheDocument()
    })

    it('停在待審核的那一筆按得了重新規劃', async () => {
      const stub = render({
        [JOBS]: { body: [PLANNED] },
        [PLAN]: plan(),
        [`POST /api/jobs/${HASH}/replan`]: { body: { ...PLANNED, state: 'importing' } },
      })
      renderApp('/jobs')
      await userEvent.click(await screen.findByText(/SPY×FAMILY - 13/))

      await userEvent.click(await screen.findByRole('button', { name: '重新規劃' }))

      // 按下去之後那一列自己重問一次（`['jobs']` 失效），所以清單**至少**被要了兩次。
      // 比「剛好兩次」的話，任何一次額外的失效（視窗重新聚焦…）都會讓這條測試變成擲骰子。
      await waitFor(() => {
        expect(
          stub.mock.calls.filter(([url]) => String(url) === '/api/jobs').length,
        ).toBeGreaterThanOrEqual(2)
      })
      expect(stub.mock.calls.some(([url]) => String(url).endsWith('/replan'))).toBe(true)
    })

    it('重新規劃被擋下來時說的是那個理由', async () => {
      render({
        [JOBS]: { body: [PLANNED] },
        [PLAN]: plan(),
        [`POST /api/jobs/${HASH}/replan`]: {
          status: 409,
          body: { detail: { reason: 'not_replannable', detail: 'importing' } },
        },
      })
      renderApp('/jobs')
      await userEvent.click(await screen.findByText(/SPY×FAMILY - 13/))

      await userEvent.click(await screen.findByRole('button', { name: '重新規劃' }))

      expect(await screen.findByRole('alert')).toHaveTextContent(/不能重新規劃/)
    })

    it('已經在入庫的那一筆沒有那顆按鈕——規則在後端算', async () => {
      render({ [JOBS]: { body: [job({ state: 'importing', plan_id: 7 })] }, [PLAN]: plan() })
      renderApp('/jobs')
      await userEvent.click(await screen.findByText(/SPY×FAMILY - 13/))

      expect(screen.queryByRole('button', { name: '重新規劃' })).not.toBeInTheDocument()
    })
  })
})
