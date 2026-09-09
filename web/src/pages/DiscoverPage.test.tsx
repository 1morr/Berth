import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { Discover, DiscoverItem } from '../api/discover'
import { HEALTHY, stubApi, type StubRoute } from '../test/fetch'
import { discoverWall as wall } from '../test/fixtures'
import { renderApp } from '../test/render'

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

const TRENDING = 'GET /api/discover/trending'
const POPULAR = 'GET /api/discover/popular'

function item(overrides: Partial<DiscoverItem> = {}): DiscoverItem {
  return {
    id: 'tv:95350',
    tmdb_id: 95350,
    kind: 'tv',
    title: '綠燈軍團',
    title_en: 'Lanterns',
    year: 2026,
    poster_url: 'https://image.tmdb.org/t/p/w342/lanterns.jpg',
    tracked: false,
    ...overrides,
  }
}

const MOANA = item({
  id: 'movie:1108427',
  tmdb_id: 1108427,
  kind: 'movie',
  title: 'Moana',
  title_en: 'Moana',
  poster_url: 'https://image.tmdb.org/t/p/w342/moana.jpg',
})

/** 走真正的 route tree：這一頁掛在 `/`，而憑證錯誤裡有一條連到精靈的站內連結。 */
function render(
  routes: Record<string, StubRoute | (() => StubRoute)> = {},
  role: 'admin' | 'user' = 'admin',
) {
  return stubApi({
    'GET /api/health': { body: HEALTHY },
    'GET /api/auth/me': { body: { name: 'skipper', role } },
    [TRENDING]: wall([item()]),
    [POPULAR]: wall([MOANA]),
    ...routes,
  })
}

function section(name: string) {
  return within(screen.getByRole('region', { name }))
}

describe('探索頁', () => {
  it('首頁不再導向健康頁，而是畫趨勢與熱門（票 03 驗收）', async () => {
    render()
    renderApp('/')

    expect(await screen.findByRole('region', { name: '本週趨勢' })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: '熱門' })).toBeInTheDocument()
  })

  it('卡片顯示顯示用標題、英文標題、類型與年份', async () => {
    render()
    renderApp('/')
    await screen.findByText('綠燈軍團')

    const card = section('本週趨勢').getByRole('article')

    expect(within(card).getByText('綠燈軍團')).toBeInTheDocument()
    expect(within(card).getByText('Lanterns')).toBeInTheDocument()
    expect(within(card).getByText('TV · 2026')).toBeInTheDocument()
  })

  it('顯示用標題與英文標題相同時不重複印一次', async () => {
    render({ [TRENDING]: wall([MOANA]), [POPULAR]: wall() })
    renderApp('/')

    await screen.findByText('Moana')

    expect(section('本週趨勢').getAllByText('Moana')).toHaveLength(1)
  })

  it('追蹤狀態畫在卡片上（M1 只有未追蹤 / 已追蹤）', async () => {
    render({ [TRENDING]: wall([item({ tracked: true }), MOANA]) })
    renderApp('/')

    await screen.findByText('已追蹤')

    expect(section('本週趨勢').getAllByText('已追蹤')).toHaveLength(1)
  })

  it('沒有海報的作品畫一格空位，不是破圖', async () => {
    render({ [TRENDING]: wall([item({ poster_url: '' })]) })
    renderApp('/')

    await screen.findByText('無海報')

    expect(section('本週趨勢').queryByRole('presentation')).not.toBeInTheDocument()
  })

  it('海報不進無障礙名稱——標題就在它下面，唸兩次只是噪音', async () => {
    render()
    renderApp('/')
    await screen.findByText('綠燈軍團')

    const card = section('本週趨勢').getByRole('article')

    expect(within(card).getByRole('presentation')).toHaveAttribute('alt', '')
    expect(within(card).queryByRole('img')).not.toBeInTheDocument()
  })

  it('TMDB 的歸屬聲明與標誌永遠在頁面上（brief §20.3 的條款要求）', async () => {
    render()
    renderApp('/')

    expect(await screen.findByAltText('TMDB')).toBeInTheDocument()
    expect(screen.getByText(/未經 TMDB 認可或認證/)).toBeInTheDocument()
  })
})

describe('探索頁的搜尋', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
  })

  it('鍵入即搜，結果接管整面牆', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    render({ 'GET /api/discover/search?q=moana': wall([MOANA]) })
    renderApp('/')
    await screen.findByRole('region', { name: '本週趨勢' })

    await user.type(screen.getByLabelText('搜尋作品'), 'moana')
    await vi.advanceTimersByTimeAsync(500)

    expect(await screen.findByRole('region', { name: '「moana」的結果' })).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: '本週趨勢' })).not.toBeInTheDocument()
  })

  it('一個字不發搜尋——那一輪結果沒有意義，卻要花掉使用者自備的額度', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    const fetchStub = render()
    renderApp('/')
    await screen.findByRole('region', { name: '本週趨勢' })

    await user.type(screen.getByLabelText('搜尋作品'), 'm')
    await vi.advanceTimersByTimeAsync(1000)

    expect(fetchStub.mock.calls.filter(([url]) => String(url).includes('/search'))).toHaveLength(0)
    expect(screen.getByText('再打 2 個字以上就開始搜尋。')).toBeInTheDocument()
  })

  it('防抖：連打一個詞不會每個按鍵都送一次', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    const fetchStub = render({ 'GET /api/discover/search?q=moana': wall([MOANA]) })
    renderApp('/')
    await screen.findByRole('region', { name: '本週趨勢' })

    await user.type(screen.getByLabelText('搜尋作品'), 'moana')
    await vi.advanceTimersByTimeAsync(500)
    await screen.findByText('Moana')

    expect(fetchStub.mock.calls.filter(([url]) => String(url).includes('/search'))).toHaveLength(1)
  })

  it('清空搜尋框回到趨勢與熱門', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    render({ 'GET /api/discover/search?q=moana': wall([MOANA]) })
    renderApp('/')
    await screen.findByRole('region', { name: '本週趨勢' })

    await user.type(screen.getByLabelText('搜尋作品'), 'moana')
    await vi.advanceTimersByTimeAsync(500)
    await screen.findByRole('region', { name: '「moana」的結果' })
    await user.clear(screen.getByLabelText('搜尋作品'))
    await vi.advanceTimersByTimeAsync(500)

    expect(await screen.findByRole('region', { name: '本週趨勢' })).toBeInTheDocument()
  })

  it('搜不到時說得出查的是什麼，並給得出下一步', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    render({ 'GET /api/discover/search?q=zzzz': wall() })
    renderApp('/')
    await screen.findByRole('region', { name: '本週趨勢' })

    await user.type(screen.getByLabelText('搜尋作品'), 'zzzz')
    await vi.advanceTimersByTimeAsync(500)

    expect(await screen.findByText(/沒有作品叫「zzzz」/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '回到趨勢' }))
    await vi.advanceTimersByTimeAsync(500)
    expect(await screen.findByRole('region', { name: '本週趨勢' })).toBeInTheDocument()
  })

  it('換一個詞的時候不把上一輪結果換成一整片空格', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    render({
      'GET /api/discover/search?q=moana': wall([MOANA]),
      'GET /api/discover/search?q=moanaa': wall([MOANA]),
    })
    renderApp('/')
    await screen.findByRole('region', { name: '本週趨勢' })
    await user.type(screen.getByLabelText('搜尋作品'), 'moana')
    await vi.advanceTimersByTimeAsync(500)
    await screen.findByText('Moana')

    await user.type(screen.getByLabelText('搜尋作品'), 'a')
    await vi.advanceTimersByTimeAsync(500)

    // 上一輪的卡片還在，而標題說的仍然是它屬於的那個詞。
    expect(screen.getByText('Moana')).toBeInTheDocument()
    expect(screen.getByRole('region', { name: /「moana」?的結果/ })).toBeInTheDocument()
  })
})

describe('探索頁拿不到 TMDB 時', () => {
  const missing: StubRoute = {
    body: { items: [], problem: 'credential_missing', detail: '' } satisfies Discover,
  }

  it('憑證缺失時說出下一步，而不是留一片空白', async () => {
    render({ [TRENDING]: missing })
    renderApp('/')

    expect(await screen.findByText(/Berth 還沒有 TMDB 憑證/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '前往設定精靈' })).toHaveAttribute(
      'href',
      '/setup?berth=3',
    )
  })

  it('一般使用者拿到的是「去找管理員」，不是一條會把他彈回來的連結', async () => {
    render({ [TRENDING]: missing }, 'user')
    renderApp('/')

    expect(await screen.findByText(/請管理員到設定精靈補上/)).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: '前往設定精靈' })).not.toBeInTheDocument()
  })

  it('連不上 TMDB 是另一種：附原文與重試，不連到精靈', async () => {
    render({
      [TRENDING]: {
        body: {
          items: [],
          problem: 'unreachable',
          detail: 'GET /trending/tv/week: connection refused',
        } satisfies Discover,
      },
    })
    renderApp('/')

    expect(await screen.findByText(/連不上 TMDB/)).toBeInTheDocument()
    expect(screen.getByText('GET /trending/tv/week: connection refused')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '重試' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: '前往設定精靈' })).not.toBeInTheDocument()
  })

  it('兩個 feed 同一個理由時整頁只說一次，不是逐個 feed 各說一次', async () => {
    render({ [TRENDING]: missing, [POPULAR]: missing })
    renderApp('/')

    expect(await screen.findAllByText(/Berth 還沒有 TMDB 憑證/)).toHaveLength(1)
    expect(screen.queryByRole('region', { name: '本週趨勢' })).not.toBeInTheDocument()
  })

  it('一個 feed 壞掉時另一個照樣畫得出來', async () => {
    render({ [TRENDING]: missing })
    renderApp('/')

    await screen.findByText(/Berth 還沒有 TMDB 憑證/)

    expect(section('熱門').getByText('Moana')).toBeInTheDocument()
  })

  it('按重試會重新問後端', async () => {
    const user = userEvent.setup()
    const fetchStub = render({ [TRENDING]: wall() })
    let attempts = 0
    fetchStub.mockImplementation(async (input) => {
      const url = String(input)
      if (url.endsWith('/discover/trending')) {
        attempts += 1
        return new Response(
          JSON.stringify({
            items: [],
            problem: attempts === 1 ? 'unreachable' : null,
            detail: 'GET /trending/tv/week: connection refused',
          }),
        )
      }
      if (url.endsWith('/auth/me')) {
        return new Response(JSON.stringify({ name: 'skipper', role: 'admin' }))
      }
      if (url.endsWith('/health')) return new Response(JSON.stringify(HEALTHY))
      return new Response(JSON.stringify({ items: [MOANA], problem: null, detail: '' }))
    })
    renderApp('/')

    await user.click(await screen.findByRole('button', { name: '重試' }))

    await waitFor(() => expect(attempts).toBeGreaterThan(1))
  })
})
