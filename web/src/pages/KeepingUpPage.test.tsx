import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { KeepingUp, TrackedWork } from '../api/keepingUp'
import type { MyNotify } from '../api/notify'
import { HEALTHY, stubApi, type StubRoutes } from '../test/fetch'
import { renderApp } from '../test/render'

afterEach(() => {
  vi.unstubAllGlobals()
})

function work(overrides: Partial<TrackedWork>): TrackedWork {
  return {
    media_id: 'tv:1',
    title: '作品',
    title_en: 'Work',
    groups: ['LoliHouse'],
    aired: { season: 1, episode: 5, air_date: '2026-11-01' },
    imported: { season: 1, episode: 5, air_date: '2026-11-01' },
    conclusion: 'imported',
    stalled: false,
    section: 'on_time',
    reason: null,
    late_days: null,
    late: [],
    ...overrides,
  }
}

const TRACKING: KeepingUp = {
  today: '2026-11-04',
  works: [
    work({
      media_id: 'tv:220542',
      title: '藥師少女的獨語',
      section: 'action',
      conclusion: 'downloading',
      stalled: true,
      imported: { season: 2, episode: 4, air_date: '2026-10-25' },
      aired: { season: 2, episode: 5, air_date: '2026-11-01' },
      late_days: 3,
      reason: 'late',
      late: [
        {
          season: 2,
          episode: 5,
          air_date: '2026-11-01',
          stall: 'stalled',
          jobs: ['a'.repeat(40)],
        },
      ],
    }),
    work({ media_id: 'tv:2', title: '準時的作品', groups: ['ANi', 'Baha'] }),
    work({
      media_id: 'tv:3',
      title: '斷更的作品',
      section: 'dormant',
      conclusion: 'no_source',
    }),
  ],
}

const NOTIFIED: MyNotify = {
  bot_configured: true,
  bot_name: 'Berth',
  discord_user_id: '123456789012345678',
  language: 'zh-Hant',
  kinds: ['ready', 'waiting'],
  unreachable_at: null,
  unreachable_detail: '',
}

function render(routes: StubRoutes = {}, role: 'admin' | 'user' = 'admin') {
  return stubApi({
    'GET /api/health': { body: HEALTHY },
    'GET /api/auth/me': { body: { name: role === 'admin' ? 'skipper' : 'deckhand', role } },
    'GET /api/waiting': { body: { review: 0, issue: 0, rss: 2 } },
    'GET /api/schedule/tracking': { body: TRACKING },
    'GET /api/me/notifications': { body: NOTIFIED },
    ...routes,
  })
}

describe('追更', () => {
  it('分三段，下載停滯說成「下載停滯」不是「下載中」，晚的那一部寫晚幾天與哪一集', async () => {
    render()
    renderApp('/schedule/tracking')

    const action = await screen.findByRole('region', { name: '要你動手' })
    const table = within(action).getByRole('table', { name: '要你動手' })
    const row = within(table).getByRole('row', { name: /藥師少女的獨語/ })
    expect(within(row).getByText('晚 3 天')).toBeInTheDocument()
    expect(within(row).getByText('S02 E05')).toBeInTheDocument()
    expect(within(row).getByText('下載停滯')).toBeInTheDocument()
    expect(within(row).queryByText('下載中')).not.toBeInTheDocument()
    expect(within(row).getByRole('link', { name: '看這筆下載' })).toHaveAttribute(
      'href',
      `/jobs/${'a'.repeat(40)}`,
    )
    expect(within(row).getByRole('link', { name: '藥師少女的獨語' })).toHaveAttribute(
      'href',
      '/media/tv%3A220542',
    )

    const onTime = screen.getByRole('region', { name: '準時' })
    expect(within(onTime).getByRole('table', { name: '準時' })).toHaveTextContent('ANi、Baha')
    expect(within(onTime).getAllByText('跟上了').length).toBeGreaterThan(0)
  })

  it('斷更很久預設收起，展開看得到', async () => {
    const user = userEvent.setup()
    render()
    renderApp('/schedule/tracking')

    const dormant = await screen.findByRole('region', { name: '斷更很久' })
    expect(within(dormant).queryByText('斷更的作品')).not.toBeInTheDocument()
    await user.click(within(dormant).getByText('斷更很久'))
    expect(within(dormant).getAllByRole('link', { name: '斷更的作品' }).length).toBeGreaterThan(0)
  })

  it('收得到通知的管理員看不到提示', async () => {
    render()
    renderApp('/schedule/tracking')

    await screen.findByRole('region', { name: '要你動手' })
    expect(screen.queryByText('遲到只會顯示在這裡，不會通知你。')).not.toBeInTheDocument()
  })

  it('沒接 Discord 時頁首說遲到只在這裡，連到通知設定', async () => {
    render({
      'GET /api/me/notifications': { body: { ...NOTIFIED, discord_user_id: '' } },
    })
    renderApp('/schedule/tracking')

    const hint = await screen.findByText('遲到只會顯示在這裡，不會通知你。')
    expect(within(hint.parentElement!).getByRole('link', { name: '到通知設定' })).toHaveAttribute(
      'href',
      '/settings/notifications',
    )
  })

  it('全部準時時說一句，不畫要你動手那一段', async () => {
    render({
      'GET /api/schedule/tracking': {
        body: { ...TRACKING, works: TRACKING.works.filter((one) => one.section !== 'action') },
      },
    })
    renderApp('/schedule/tracking')

    expect(await screen.findByText('訂閱的作品都按時。')).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: '要你動手' })).not.toBeInTheDocument()
  })

  it('一部訂閱都沒有時連到時間表', async () => {
    render({ 'GET /api/schedule/tracking': { body: { ...TRACKING, works: [] } } })
    renderApp('/schedule/tracking')

    expect(await screen.findByRole('link', { name: '到時間表找新番' })).toHaveAttribute(
      'href',
      '/schedule',
    )
  })

  it('分頁列：管理員是時間表、追更、訂閱，追更是當前那一格', async () => {
    render()
    renderApp('/schedule/tracking')

    const tabs = await screen.findByRole('navigation', { name: '新番' })
    await within(tabs).findByRole('link', { name: '訂閱 2 件' })
    expect(
      within(tabs)
        .getAllByRole('link')
        .map((link) => link.getAttribute('aria-label')),
    ).toEqual(['時間表', '追更', '訂閱 2 件'])
    expect(within(tabs).getByRole('link', { name: '追更' })).toHaveAttribute('aria-current', 'page')
    expect(within(tabs).getByRole('link', { name: '時間表' })).not.toHaveAttribute('aria-current')
    // 頁首的「新番」在區塊的別頁上是 `true`，不是 `page`。
    const main = screen.getByRole('navigation', { name: '主要導覽' })
    expect(within(main).getByRole('link', { name: /新番/ })).toHaveAttribute('aria-current', 'true')
  })

  it('一般使用者打開追更被導走', async () => {
    render({}, 'user')
    const { router } = renderApp('/schedule/tracking')

    await vi.waitFor(() => expect(router.state.location.pathname).toBe('/health'))
  })
})

describe('時間表的晚 N 天', () => {
  it('晚了的卡片寫「晚 N 天」', async () => {
    const card = {
      media_id: 'tv:220542',
      tmdb_id: 220542,
      title: '藥師少女的獨語',
      title_en: 'The Apothecary Diaries',
      poster_url: '',
      poster_url_en: '',
      air_date: '2026-11-03',
      season: 2,
      episode: 5,
      status: 'late' as const,
      late_days: 1,
      airs_at: null,
      score: null,
      votes: null,
    }
    render({
      'GET /api/schedule': {
        body: {
          start: '2026-11-02',
          end: '2026-11-08',
          today: '2026-11-04',
          problem: null,
          detail: '',
          cards: [card],
        },
      },
    })
    renderApp('/schedule')

    const week = await screen.findByTestId('schedule-week')
    expect(within(week).getByRole('link', { name: '藥師少女的獨語' })).toHaveAccessibleDescription(
      'S02E05 晚 1 天',
    )
  })
})
