import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18next from 'i18next'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { WeeklyLine, WeeklyReport } from '../api/weekly'
import { HEALTHY, stubApi, type StubRoutes } from '../test/fetch'
import { renderApp } from '../test/render'

afterEach(() => {
  vi.unstubAllGlobals()
})

const LIST = 'GET /api/weekly'

const LINES: WeeklyLine[] = [
  {
    id: 2,
    first_day: '2026-10-19',
    last_day: '2026-10-25',
    works: 3,
    episodes: 6,
    fixed: 7,
    waiting: 7,
  },
  {
    id: 1,
    first_day: '2026-10-12',
    last_day: '2026-10-18',
    works: 0,
    episodes: 0,
    fixed: 0,
    waiting: 0,
  },
]

const REPORT: WeeklyReport = {
  id: 2,
  first_day: '2026-10-19',
  last_day: '2026-10-25',
  created_at: '2026-10-26T05:00:00Z',
  imported: [
    {
      media: 'tv-1',
      kind: 'tv',
      title: '葬送的芙莉蓮',
      title_en: 'Frieren: Beyond Journeys End',
      episodes: [
        [1, 1, 3],
        [1, 5, 5],
        [2, 1, 1],
      ],
    },
    { media: 'mv-1', kind: 'movie', title: '鈴芽之旅', title_en: 'Suzume', episodes: [] },
    { media: null, kind: null, title: '已刪的作品', title_en: 'Deleted', episodes: [[1, 1, 2]] },
  ],
  fixed: {
    approved: 2,
    rematched: 1,
    resolved: { series_episodes_missing: 2, orphan_complete: 1 },
    cleared: {},
  },
  waiting: {
    review: 2,
    issues: { series_episodes_missing: 2, first_batch_stuck: 1 },
    rss: 1,
    swept: { first_batch_stuck: 1 },
  },
}

const EMPTY_REPORT: WeeklyReport = {
  ...REPORT,
  imported: [],
  fixed: { approved: 0, rematched: 0, resolved: {}, cleared: {} },
  waiting: { review: 0, issues: {}, rss: 0, swept: {} },
}

const PREVIOUS: WeeklyReport = {
  ...EMPTY_REPORT,
  id: 1,
  first_day: '2026-10-12',
  last_day: '2026-10-18',
}

function render(routes: StubRoutes = {}, role: 'admin' | 'user' = 'admin') {
  return stubApi({
    'GET /api/health': { body: HEALTHY },
    'GET /api/auth/me': { body: { name: 'skipper', role } },
    [LIST]: { body: LINES },
    'GET /api/weekly/2': { body: REPORT },
    'GET /api/weekly/1': { body: PREVIOUS },
    ...routes,
  })
}

describe('週報頁', () => {
  it('/weekly 是最新一週：抬頭、入庫、修了什麼、還有什麼等人', async () => {
    render()
    renderApp('/weekly')

    expect(await screen.findByRole('heading', { level: 1, name: '週報' })).toBeVisible()
    // 抬頭與歷史清單都寫這一週的日期範圍。
    expect((await screen.findAllByText('2026-10-19 – 10-25')).length).toBeGreaterThan(0)
    expect(await screen.findByText(/產生於 \d\d-\d\d \d\d:\d\d/)).toBeVisible()

    const imported = within(await screen.findByRole('region', { name: '入庫' }))
    expect(imported.getByText('3 部 · 7 集')).toBeVisible()
    // 同一季接著寫集，換季才寫季；與通知同一個寫法。
    expect(imported.getByText('S01E01–E03, E05, S02E01')).toBeVisible()
    expect(imported.getByText('S01E01–E02')).toBeVisible()

    const fixed = within(screen.getByRole('region', { name: '修了什麼' }))
    expect(fixed.getByText('6 件')).toBeVisible()
    expect(fixed.getByText('核准的計劃').nextElementSibling).toHaveTextContent('2')
    expect(fixed.getByText('你們解決的 Issue').nextElementSibling).toHaveTextContent(
      '缺集 ×2、無主目錄',
    )
    // 0 的不列。
    expect(fixed.queryByText('系統收掉的 Issue')).not.toBeInTheDocument()

    const waiting = within(screen.getByRole('region', { name: '還有什麼等人' }))
    expect(waiting.getByText('6 件')).toBeVisible()
    expect(waiting.getByText('待審核').nextElementSibling).toHaveTextContent('2')
    expect(waiting.getByText('Issue').nextElementSibling).toHaveTextContent('缺集 ×2、第一批卡住')
    expect(waiting.getByText('巡檢開出的').nextElementSibling).toHaveTextContent('第一批卡住')
    expect(waiting.getByText(/這是產生那一刻的數字/)).toBeVisible()
    expect(waiting.getByRole('link', { name: '打開待審核' })).toHaveAttribute('href', '/review')
    expect(waiting.getByRole('link', { name: '打開Issue' })).toHaveAttribute('href', '/issues')
    expect(waiting.getByRole('link', { name: '打開RSS Series 待綁定' })).toHaveAttribute(
      'href',
      '/rss',
    )
  })

  it('作品名連到作品頁，已刪的作品不連；電影是中性色塊', async () => {
    render()
    renderApp('/weekly')

    const imported = within(await screen.findByRole('region', { name: '入庫' }))
    expect(imported.getByRole('link', { name: '葬送的芙莉蓮' })).toHaveAttribute(
      'href',
      '/media/tv-1',
    )
    expect(imported.getByRole('link', { name: '鈴芽之旅' })).toHaveAttribute('href', '/media/mv-1')
    expect(imported.getByText('電影')).toBeVisible()
    expect(imported.getByText('已刪的作品')).toBeVisible()
    expect(imported.queryByRole('link', { name: '已刪的作品' })).not.toBeInTheDocument()
  })

  it('介面是英文時用英文作品名', async () => {
    render()
    await i18next.changeLanguage('en')
    try {
      renderApp('/weekly')
      const imported = within(await screen.findByRole('region', { name: 'Imported' }))
      expect(imported.getByRole('link', { name: 'Frieren: Beyond Journeys End' })).toBeVisible()
      expect(imported.getByText('Movie')).toBeVisible()
    } finally {
      await i18next.changeLanguage('zh-Hant')
    }
  })

  it('三段各自的空：說的是這一週沒有，不是沒有資料', async () => {
    render({ 'GET /api/weekly/2': { body: EMPTY_REPORT } })
    renderApp('/weekly')

    expect(await screen.findByText('這一週沒有入庫。')).toBeVisible()
    expect(screen.getByText('這一週沒有修正。')).toBeVisible()
    expect(screen.getByText('產生時沒有等你處理的事。')).toBeVisible()
  })

  it('歷史清單：目前這一週是 aria-current，點到別週換網址與內容', async () => {
    render()
    const user = userEvent.setup()
    const { router } = renderApp('/weekly')

    const history = within(await screen.findByRole('navigation', { name: '歷來的週報' }))
    const current = history.getByText('2026-10-19 – 10-25').closest('[aria-current]')
    expect(current).toHaveAttribute('aria-current', 'page')
    expect(current).toHaveTextContent('入庫 3')
    expect(current).toHaveTextContent('修 7')
    expect(current).toHaveTextContent('等 7')
    expect(history.getAllByRole('link')).toHaveLength(1)

    await user.click(history.getByRole('link', { name: /2026-10-12 – 10-18/ }))

    expect(await screen.findByText('2026-10-12 – 10-18', { selector: 'p' })).toBeVisible()
    expect(router.state.location.pathname).toBe('/weekly/1')
    const next = within(screen.getByRole('navigation', { name: '歷來的週報' }))
    expect(next.getByText('2026-10-12 – 10-18').closest('[aria-current]')).not.toBeNull()
  })

  it('/weekly/$reportId 讀那一週', async () => {
    render()
    renderApp('/weekly/1')

    expect(await screen.findByText('2026-10-12 – 10-18', { selector: 'p' })).toBeVisible()
    expect(screen.getByText('這一週沒有入庫。')).toBeVisible()
  })

  it('後端說沒有這一週：一句話加一條回最新一週的路，歷史清單還在', async () => {
    render({ 'GET /api/weekly/999': { status: 404, body: { detail: 'no such weekly report' } } })
    renderApp('/weekly/999')

    expect(await screen.findByText(/沒有這一週的週報/)).toBeVisible()
    expect(screen.getByRole('link', { name: '看最新一週' })).toHaveAttribute('href', '/weekly')
    expect(screen.getByRole('navigation', { name: '歷來的週報' })).toBeVisible()
  })

  it('網址不是正整數的當作沒有這一週，不打後端', async () => {
    const stub = render()
    renderApp('/weekly/abc')

    expect(await screen.findByText(/沒有這一週的週報/)).toBeVisible()
    const asked = stub.mock.calls.map(([input]) => String(input))
    expect(asked.filter((path) => path.startsWith('/api/weekly/'))).toEqual([])
  })

  it('一份都沒有：第一份在週一 05:00 產生，沒有歷史清單', async () => {
    render({ [LIST]: { body: [] } })
    renderApp('/weekly')

    expect(await screen.findByText('第一份週報在週一 05:00 產生。')).toBeVisible()
    expect(screen.queryByRole('navigation', { name: '歷來的週報' })).not.toBeInTheDocument()
  })

  it('讀不到清單時說讀不到', async () => {
    render({ [LIST]: { status: 500, body: { detail: 'Internal Server Error' } } })
    renderApp('/weekly')

    expect(await screen.findByText(/讀不到週報/)).toBeVisible()
  })

  it('一般使用者：導覽沒有週報，直接打網址被導走', async () => {
    render({}, 'user')
    const { router } = renderApp('/weekly')

    expect(await screen.findByRole('navigation', { name: '主要導覽' })).toBeVisible()
    expect(screen.queryByRole('link', { name: '週報' })).not.toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/health')
  })

  it('管理員的導覽有週報，排在 RSS 之後、健康之前', async () => {
    render()
    renderApp('/health')

    const nav = await screen.findByRole('navigation', { name: '主要導覽' })
    const names = within(nav)
      .getAllByRole('link')
      .map((link) => link.textContent)
    expect(names.indexOf('週報')).toBe(names.indexOf('RSS') + 1)
    expect(names.indexOf('健康')).toBe(names.indexOf('週報') + 1)
  })
})
