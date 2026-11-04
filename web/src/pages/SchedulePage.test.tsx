import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Schedule, ScheduleCard } from '../api/schedule'
import { HEALTHY, stubApi, type StubRoutes } from '../test/fetch'
import { renderApp } from '../test/render'

afterEach(() => {
  vi.unstubAllGlobals()
})

function card(overrides: Partial<ScheduleCard>): ScheduleCard {
  return {
    media_id: 'tv:1',
    tmdb_id: 1,
    title: '作品',
    title_en: 'Work',
    poster_url: '',
    poster_url_en: '',
    air_date: '2026-11-03',
    season: 1,
    episode: 1,
    status: 'unsubscribed',
    late_days: null,
    airs_at: null,
    score: null,
    votes: null,
    ...overrides,
  }
}

const WEEK: Schedule = {
  start: '2026-11-02',
  end: '2026-11-08',
  today: '2026-11-04',
  problem: null,
  detail: '',
  cards: [
    card({
      media_id: 'tv:220542',
      title: '藥師少女的獨語',
      title_en: 'The Apothecary Diaries',
      air_date: '2026-11-04',
      season: 2,
      episode: 5,
      status: 'subscribed',
    }),
    card({ media_id: 'tv:57775', title: '櫻桃小丸子', air_date: '2026-11-04', episode: 1500 }),
    card({
      media_id: 'tv:209867',
      title: '葬送的芙莉蓮',
      air_date: '2026-11-07',
      season: 2,
      airs_at: '2026-11-07T14:00:00Z',
      score: 8.1,
      votes: 900,
    }),
  ],
}

function render(routes: StubRoutes = {}, role: 'admin' | 'user' = 'admin') {
  return stubApi({
    'GET /api/health': { body: HEALTHY },
    'GET /api/auth/me': { body: { name: role === 'admin' ? 'skipper' : 'deckhand', role } },
    'GET /api/waiting': { body: { review: 0, issue: 0, rss: 2 } },
    'GET /api/schedule': { body: WEEK },
    ...routes,
  })
}

describe('時間表', () => {
  it('週一到週日七欄，今天那一欄標出來，卡片放在 TMDB 說的那一天', async () => {
    render()
    renderApp('/schedule')

    const week = await screen.findByTestId('schedule-week')
    const days = within(week).getAllByRole('region')
    expect(days).toHaveLength(7)
    const today = days[2]!
    expect(today).toHaveAttribute('aria-current', 'date')
    expect(within(today).getByText('今天')).toBeInTheDocument()
    expect(
      within(today)
        .getAllByRole('link')
        .map((link) => link.getAttribute('aria-label')),
    ).toEqual(['藥師少女的獨語', '櫻桃小丸子'])
    expect(within(today).getByRole('link', { name: '藥師少女的獨語' })).toHaveAttribute(
      'href',
      '/media/tv%3A220542',
    )
    expect(within(days[0]!).getByText('這天沒有')).toBeInTheDocument()
    expect(within(days[5]!).getByRole('link', { name: '葬送的芙莉蓮' })).toBeInTheDocument()
  })

  it('卡片說第幾集與狀態；未訂閱不畫色塊', async () => {
    render()
    renderApp('/schedule')

    const week = await screen.findByTestId('schedule-week')
    const subscribed = within(week).getByRole('link', { name: '藥師少女的獨語' })
    expect(subscribed).toHaveAccessibleDescription('S02E05 已訂閱')
    expect(within(week).getByRole('link', { name: '櫻桃小丸子' })).toHaveAccessibleDescription(
      'S01E1500',
    )
  })

  it('對得上的卡片寫放送時刻與 Bangumi 評分（M5.5 票 14），對不上的不寫', async () => {
    render()
    renderApp('/schedule')

    const week = await screen.findByTestId('schedule-week')
    const frieren = within(week).getByRole('link', { name: '葬送的芙莉蓮' })
    const time = within(frieren).getByRole('time')
    expect(time).toHaveAttribute('datetime', '2026-11-07T14:00:00Z')
    expect(within(frieren).getByText('Bangumi 8.1')).toHaveAttribute('title', '900 人打分')
    expect(frieren).toHaveAccessibleDescription(
      expect.stringMatching(/^S02E01 \S*\s?\d{2}:\d{2}\s+Bangumi 評分 8\.1，900 人打分$/),
    )

    const maruko = within(week).getByRole('link', { name: '櫻桃小丸子' })
    expect(within(maruko).queryByRole('time')).not.toBeInTheDocument()
    expect(within(maruko).queryByText(/Bangumi/)).not.toBeInTheDocument()
  })

  it('窄版一次一天，預設今天，換一天就換清單', async () => {
    render()
    renderApp('/schedule')
    const user = userEvent.setup()

    const narrow = await screen.findByTestId('schedule-day')
    expect(within(narrow).getAllByRole('link')).toHaveLength(2)
    const picker = screen.getByRole('group', { name: '選一天' })
    const keys = within(picker).getAllByRole('button')
    expect(keys).toHaveLength(7)
    expect(keys[2]).toHaveAttribute('aria-pressed', 'true')
    expect(keys[2]).toHaveTextContent('今天')

    await user.click(keys[5]!)

    expect(keys[5]).toHaveAttribute('aria-pressed', 'true')
    expect(
      within(narrow)
        .getAllByRole('link')
        .map((link) => link.textContent),
    ).toEqual([expect.stringContaining('葬送的芙莉蓮')])
  })

  it('選的那一天與「只看已訂閱」記在網址：點進作品頁再回上一頁還在', async () => {
    render({
      'GET /api/media/tv:209867': { status: 404, body: { detail: 'not found' } },
    })
    const { router } = renderApp('/schedule')
    const user = userEvent.setup()
    await screen.findByTestId('schedule-day')

    await user.click(
      within(screen.getByRole('group', { name: '選一天' })).getAllByRole('button')[5]!,
    )
    await user.click(screen.getByRole('button', { name: '只看已訂閱' }))
    expect(router.state.location.search).toEqual({ day: '2026-11-07', subscribed: true })

    await router.navigate({ to: '/media/$mediaId', params: { mediaId: 'tv:209867' } })
    router.history.back()

    const keys = within(await screen.findByRole('group', { name: '選一天' })).getAllByRole('button')
    expect(keys[5]).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: '只看已訂閱' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })

  it('網址上的日子不在這一週時退回今天', async () => {
    render()
    renderApp('/schedule?day=2025-01-01')

    const keys = within(await screen.findByRole('group', { name: '選一天' })).getAllByRole('button')
    expect(keys[2]).toHaveAttribute('aria-pressed', 'true')
  })

  it('只看已訂閱', async () => {
    render()
    renderApp('/schedule')
    const user = userEvent.setup()
    await screen.findByTestId('schedule-week')

    await user.click(screen.getByRole('button', { name: '只看已訂閱' }))

    expect(screen.getByRole('button', { name: '只看已訂閱' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(
      within(screen.getByTestId('schedule-week'))
        .getAllByRole('link')
        .map((link) => link.getAttribute('aria-label')),
    ).toEqual(['藥師少女的獨語'])
  })

  it('只看已訂閱而這週一部都沒有：說訂閱從作品頁開始', async () => {
    render({ 'GET /api/schedule': { body: { ...WEEK, cards: [WEEK.cards[1]!] } } })
    renderApp('/schedule')
    const user = userEvent.setup()
    await screen.findByTestId('schedule-week')

    await user.click(screen.getByRole('button', { name: '只看已訂閱' }))

    expect(screen.getByText(/這一週沒有已訂閱的作品在播/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '到探索找作品' })).toHaveAttribute('href', '/')
  })

  it('拿不到 TMDB 時說下一步', async () => {
    render({
      'GET /api/schedule': {
        body: { ...WEEK, cards: [], problem: 'unreachable', detail: 'TMDB is down' },
      },
    })
    renderApp('/schedule')

    expect(await screen.findByText('TMDB is down')).toBeInTheDocument()
    expect(screen.queryByTestId('schedule-week')).not.toBeInTheDocument()
  })
})

describe('新番的分頁', () => {
  it('管理員：時間表與訂閱（帶待綁定的件數）', async () => {
    render()
    renderApp('/schedule')

    const tabs = await screen.findByRole('navigation', { name: '新番' })
    expect(await within(tabs).findByRole('link', { name: '訂閱 2 件' })).toHaveAttribute(
      'href',
      '/rss',
    )
    expect(within(tabs).getByRole('link', { name: '時間表' })).toHaveAttribute(
      'aria-current',
      'page',
    )
  })

  it('一般使用者：只有時間表，不問件數', async () => {
    const api = render({}, 'user')
    renderApp('/schedule')

    const tabs = await screen.findByRole('navigation', { name: '新番' })
    await screen.findByTestId('schedule-week')
    expect(
      within(tabs)
        .getAllByRole('link')
        .map((link) => link.textContent),
    ).toEqual(['時間表'])
    expect(api.mock.calls.some(([url]) => url === '/api/waiting')).toBe(false)
  })
})
