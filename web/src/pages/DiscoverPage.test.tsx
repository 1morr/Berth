import { fireEvent, screen, waitFor, within } from '@testing-library/react'
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
    poster_url_en: 'https://image.tmdb.org/t/p/w342/lanterns-en.jpg',
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
  poster_url_en: 'https://image.tmdb.org/t/p/w342/moana-en.jpg',
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

  it('頁面結構說得出自己：一個 h1、主要導覽是 landmark、第一個 Tab 能跳過頁首（票 15 audit）', async () => {
    render()
    renderApp('/')
    await screen.findByRole('region', { name: '本週趨勢' })

    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    expect(screen.getByRole('navigation', { name: '主要導覽' })).toBeInTheDocument()
    const skip = screen.getByRole('link', { name: '跳到內容' })
    expect(skip).toHaveAttribute('href', '#main')
    expect(document.getElementById('main')?.tagName).toBe('MAIN')
  })

  it('牆上的筆數唸得出單位，數字本身不重複唸一次', async () => {
    render()
    renderApp('/')

    await screen.findByText('綠燈軍團')
    expect(section('本週趨勢').getByText('1 部作品')).toHaveClass('sr-only')
  })

  it('卡片顯示顯示用標題、英文標題、類型與年份', async () => {
    render()
    renderApp('/')
    await screen.findByText('綠燈軍團')

    const card = section('本週趨勢').getByRole('link')

    expect(within(card).getByText('綠燈軍團')).toBeInTheDocument()
    expect(within(card).getByText('Lanterns')).toBeInTheDocument()
    // 中點是 `Dot`（`aria-hidden`），所以類型與年份在同一個元素裡、中間隔著它。
    expect(within(card).getByText('TV', { exact: false })).toHaveTextContent('TV · 2026')
  })

  it('切到 EN 時卡片換成 en-US 那一輪的標題，不另印中文，也不重抓（brief §7.5）', async () => {
    const api = render()
    renderApp('/')
    const card = await screen.findByRole('link', { name: /綠燈軍團/ })
    const fetched = api.mock.calls.length

    await userEvent.click(screen.getByRole('button', { name: 'EN' }))

    expect(card).not.toHaveTextContent('綠燈軍團')
    expect(within(card).getAllByText('Lanterns')).toHaveLength(1)
    expect(api.mock.calls.length).toBe(fetched)
  })

  it('切到 EN 時海報也換成 en-US 那一張（TMDB 的海報分語言，票 11）', async () => {
    render()
    renderApp('/')
    const card = await screen.findByRole('link', { name: /綠燈軍團/ })
    const poster = () => within(card).getByRole('presentation', { hidden: true })
    expect(poster()).toHaveAttribute('src', 'https://image.tmdb.org/t/p/w342/lanterns.jpg')

    await userEvent.click(screen.getByRole('button', { name: 'EN' }))

    expect(poster()).toHaveAttribute('src', 'https://image.tmdb.org/t/p/w342/lanterns-en.jpg')
  })

  it('海報載不下來時換成「無海報」，不留瀏覽器的破圖示（票 11）', async () => {
    render()
    renderApp('/')
    const card = await screen.findByRole('link', { name: /綠燈軍團/ })

    // 這一格是 TMDB 的海報：那一端的圖不在時瀏覽器就會發 error。
    fireEvent.error(within(card).getByRole('presentation', { hidden: true }))

    expect(await within(card).findByText('無海報')).toBeVisible()
    expect(card.querySelector('img')).toBeNull()
  })

  it('顯示用標題與英文標題相同時不重複印一次', async () => {
    render({ [TRENDING]: wall([MOANA]), [POPULAR]: wall() })
    renderApp('/')

    await screen.findByText('Moana')

    expect(section('本週趨勢').getAllByText('Moana')).toHaveLength(1)
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

    const card = section('本週趨勢').getByRole('link')

    expect(within(card).getByRole('presentation')).toHaveAttribute('alt', '')
    expect(within(card).queryByRole('img')).not.toBeInTheDocument()
  })

  it('**整格是一個連結**，連到那部作品的詳情頁（票 04 接手票 03 留下的那條線）', async () => {
    render()
    renderApp('/')
    await screen.findByText('綠燈軍團')

    const card = section('本週趨勢').getByRole('link')

    expect(card).toHaveAttribute('href', '/media/tv%3A95350')
  })

  it('連結的名字是作品名，類型年份是描述；圖位的「無海報」不進名字（票 13）', async () => {
    render({ [TRENDING]: wall([item({ poster_url: '', poster_url_en: '' })]) })
    renderApp('/')
    await screen.findByText('綠燈軍團')

    const card = section('本週趨勢').getByRole('link')

    expect(card).toHaveAccessibleName('綠燈軍團')
    expect(card).toHaveAccessibleDescription(/^TV\s+2026/)
  })

  it('一面牆是一份清單，每一格的標題是 h3——與媒體庫牆、繼續觀看與下一集同一種語意（票 13）', async () => {
    render()
    renderApp('/')
    await screen.findByText('綠燈軍團')

    const list = section('本週趨勢').getByRole('list')

    expect(within(list).getAllByRole('listitem')).toHaveLength(1)
    expect(within(list).getByRole('heading', { level: 3 })).toHaveTextContent('綠燈軍團')
  })

  it('TMDB 的歸屬聲明與標誌永遠在頁面上（brief §20.3 的條款要求）', async () => {
    render()
    renderApp('/')

    // 標誌的替代文字走 i18n（票 13）：三頁原本各硬寫一次 `alt="TMDB"`。
    expect(await screen.findByRole('img', { name: 'TMDB 標誌' })).toBeInTheDocument()
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

  it('切到 EN 時搜尋結果的卡片也換成 en-US 那一輪的標題，不重搜（brief §7.5）', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    const api = render({
      'GET /api/discover/search?q=moana': wall([item({ title: '海洋奇緣2', title_en: 'Moana 2' })]),
    })
    renderApp('/')
    await screen.findByRole('region', { name: '本週趨勢' })
    await user.type(screen.getByLabelText('搜尋作品'), 'moana')
    await vi.advanceTimersByTimeAsync(500)
    const card = await screen.findByRole('link', { name: /海洋奇緣2/ })
    const fetched = api.mock.calls.length

    await user.click(screen.getByRole('button', { name: 'EN' }))

    expect(card).not.toHaveTextContent('海洋奇緣2')
    expect(within(card).getAllByText('Moana 2')).toHaveLength(1)
    expect(api.mock.calls.length).toBe(fetched)
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
    // 結果那一筆的標題**不能與牆上任何一格相同**：`MOANA` 也在熱門那面牆上，等它出現等到的
    // 會是還沒搜尋前就在畫面上的那一格，於是這條測試在機器忙的時候會偽陰性（實測 3/6 紅）。
    const fetchStub = render({
      'GET /api/discover/search?q=moana': wall([item({ title: '海洋奇緣2', title_en: 'Moana 2' })]),
    })
    renderApp('/')
    await screen.findByRole('region', { name: '本週趨勢' })

    await user.type(screen.getByLabelText('搜尋作品'), 'moana')
    await vi.advanceTimersByTimeAsync(500)
    await screen.findByText('海洋奇緣2')

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
      '/setup?berth=4',
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

// brief §19（M3 票 06）：探索頁只放 TMDB 牆，繼續觀看與下一集只在媒體庫頁。
describe('探索頁只放 TMDB 牆', () => {
  it('沒有繼續觀看與下一集，也不去問 Jellyfin', async () => {
    const api = render()
    renderApp('/')

    await screen.findByRole('region', { name: '本週趨勢' })

    expect(screen.queryByRole('region', { name: '繼續觀看' })).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: '下一集' })).not.toBeInTheDocument()
    expect(api.mock.calls.some(([url]) => String(url).includes('watching'))).toBe(false)
  })
})
