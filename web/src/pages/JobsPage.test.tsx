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
    media_title: 'SPY×FAMILY 間諜家家酒',
    media_title_en: 'SPY x FAMILY',
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
    reimportable: false,
    plan_id: null,
    audits: 0,
    ...overrides,
  }
}

const FAILED = job({
  hash: 'aa11bb22cc33dd44ee55ff66aa77bb88cc99dd00',
  name: 'Moana 2 (2024) 1080p WEBRip 5.1 x264 -YTS',
  state: 'submit_failed',
  error: 'torrents/add: connection refused',
  media_id: 'movie:1241982',
  media_title: '海洋奇緣2',
  media_title_en: 'Moana 2',
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
    expect(list.getByText('SPY×FAMILY 間諜家家酒')).toBeInTheDocument()
    expect(list.getByText('Anime')).toBeInTheDocument()
    expect(list.getByText('手動')).toBeInTheDocument()
  })

  it('摘要列裡沒有連結，作品連結在展開區（票 15 critique）', async () => {
    // `<summary>` 本身就是一顆按鈕；按鈕裡再包一條連結，鍵盤與螢幕閱讀器都分不清按下去是哪一個。
    render()
    renderApp('/jobs')
    const row = await screen.findByText(/SPY×FAMILY - 13/)

    expect(within(row.closest('summary') as HTMLElement).queryByRole('link')).toBeNull()

    await userEvent.click(row)
    const link = await screen.findByRole('link', { name: 'SPY×FAMILY 間諜家家酒' })
    expect(decodeURIComponent(link.getAttribute('href') ?? '')).toBe('/media/tv:120089')
  })

  it('切到 EN 時作品名換成 en-US 那一輪，摘要列與展開區的連結都換，也不重抓（brief §7.5）', async () => {
    const api = render()
    renderApp('/jobs')
    const row = await screen.findByText(/SPY×FAMILY - 13/)
    await userEvent.click(row)
    await screen.findByRole('link', { name: 'SPY×FAMILY 間諜家家酒' })
    const fetched = api.mock.calls.length

    await userEvent.click(screen.getByRole('button', { name: 'EN' }))

    const details = within(row.closest('details') as HTMLElement)
    expect(await details.findByRole('link', { name: 'SPY x FAMILY' })).toBeInTheDocument()
    expect(details.getAllByText('SPY x FAMILY')).toHaveLength(2)
    expect(details.queryByText('SPY×FAMILY 間諜家家酒')).toBeNull()
    expect(api.mock.calls.length).toBe(fetched)
  })

  it('列上說得出能展開，展開之後說得出能收起', async () => {
    render()
    renderApp('/jobs')
    const row = await screen.findByText(/SPY×FAMILY - 13/)
    const summary = within(row.closest('summary') as HTMLElement)

    expect(summary.getByText('展開')).toBeInTheDocument()
    await userEvent.click(row)
    expect(summary.getByText('收起')).toBeInTheDocument()
  })

  it('medium 自動入庫、還要人看一眼的檔案數在列上就看得到（brief §6.5、PRODUCT 原則 3）', async () => {
    render({ [JOBS]: { body: [job({ state: 'imported', plan_id: 7, audits: 11 })] } })
    renderApp('/jobs')
    const row = await screen.findByText(/SPY×FAMILY - 13/)

    expect(
      within(row.closest('summary') as HTMLElement).getByText('11 個待確認'),
    ).toBeInTheDocument()
  })

  it('沒有待確認的檔案時什麼都不說', async () => {
    render({ [JOBS]: { body: [job({ state: 'imported', plan_id: 7 })] } })
    renderApp('/jobs')
    await screen.findByText(/SPY×FAMILY - 13/)

    expect(screen.queryByText(/待確認/)).toBeNull()
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

  describe('就地展開只剩狀態與時間線摘要（M2 票 12）', () => {
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

    it('展開區有一條到詳情頁的路', async () => {
      render()
      renderApp('/jobs')

      await userEvent.click(await screen.findByText(/SPY×FAMILY - 13/))

      expect(await screen.findByRole('link', { name: '下載詳情' })).toHaveAttribute(
        'href',
        `/jobs/${HASH}`,
      )
    })

    it('計劃與每一顆動作都只在詳情頁：展開區不問計劃，也沒有任何按鈕', async () => {
      // 旗標全開、又是 admin：這一列若還有任何一顆動作，這裡一定看得到。
      const stub = render({
        [JOBS]: {
          body: [
            job({
              state: 'review',
              retryable: true,
              replannable: true,
              reimportable: true,
              plan_id: 7,
            }),
          ],
        },
      })
      renderApp('/jobs')

      await userEvent.click(await screen.findByText(/SPY×FAMILY - 13/))
      await screen.findByText('這一筆還沒有任何事件。')

      expect(stub.mock.calls.some(([url]) => String(url).includes('/plans/'))).toBe(false)
      expect(screen.queryByText('匯入計劃')).toBeNull()
      for (const name of ['重新送單', '重新規劃', '重新入庫', '刪除']) {
        expect(screen.queryByRole('button', { name })).toBeNull()
      }
      expect(screen.queryByRole('link', { name: '到審核佇列處理' })).toBeNull()
    })

    it('時間線摘要只畫最近三段，說得出較早的還有幾筆', async () => {
      render({
        [EVENTS]: events([
          event({ id: 1, type: 'created' }),
          event({ id: 2, type: 'submitted', payload: {} }),
          event({ id: 3, type: 'metadata_received', payload: {} }),
          event({ id: 4, type: 'completed', payload: {} }),
          event({ id: 5, type: 'plan_generated', payload: {} }),
        ]),
      })
      renderApp('/jobs')

      await userEvent.click(await screen.findByText(/SPY×FAMILY - 13/))

      expect(await screen.findByText('計劃')).toBeInTheDocument()
      expect(screen.getByText('下載完成')).toBeInTheDocument()
      expect(screen.getByText('檔案清單')).toBeInTheDocument()
      expect(screen.queryByText('已建立')).toBeNull()
      expect(screen.getByText('較早的 2 筆事件在詳情頁。')).toBeInTheDocument()
    })
  })
})

describe('停在待審核的那一筆（M2 票 06）', () => {
  it('一般使用者看得到「等管理員審核」——他按不了審核，只能等', async () => {
    render({
      'GET /api/auth/me': { body: { name: 'deckhand', role: 'user' } },
      [JOBS]: { body: [job({ state: 'review' })] },
    })
    renderApp('/jobs')

    expect(await screen.findByText('等管理員審核')).toBeInTheDocument()
  })

  it('admin 不看到那一句：審核是他自己的事', async () => {
    render({ [JOBS]: { body: [job({ state: 'review' })] } })
    renderApp('/jobs')

    await screen.findByText(/SPY×FAMILY - 13/)
    expect(screen.queryByText('等管理員審核')).not.toBeInTheDocument()
  })

  it('不是待審核的那一筆什麼都不說', async () => {
    render({
      'GET /api/auth/me': { body: { name: 'deckhand', role: 'user' } },
      [JOBS]: { body: [job({ state: 'imported' })] },
    })
    renderApp('/jobs')

    await screen.findByText(/SPY×FAMILY - 13/)
    expect(screen.queryByText('等管理員審核')).not.toBeInTheDocument()
  })
})
