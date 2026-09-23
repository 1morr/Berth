import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { Discover, DiscoverItem } from '../api/discover'
import type { Watching, WatchingCard } from '../api/watching'
import { HEALTHY, session, stubApi, type StubRoute } from '../test/fetch'
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
      // 首頁上方那兩列（票 07）不是這一條要驗的：沒有它們，畫面上就只有探索牆的那一顆「重試」。
      if (url.endsWith('/jellyfin/watching')) return new Response('{}', { status: 404 })
      return new Response(JSON.stringify({ items: [MOANA], problem: null, detail: '' }))
    })
    renderApp('/')

    await user.click(await screen.findByRole('button', { name: '重試' }))

    await waitFor(() => expect(attempts).toBeGreaterThan(1))
  })
})

describe('首頁上方的繼續觀看與下一集（M1.5 票 07）', () => {
  const WATCHING = 'GET /api/jellyfin/watching'

  function card(overrides: Partial<WatchingCard> = {}): WatchingCard {
    return {
      item_id: '99701a68c9a746b2f3a2d31d0b6c49f2',
      kind: 'tv',
      title: '葬送的芙莉蓮',
      episode_name: '冒險結束',
      season: 1,
      episode_start: 5,
      episode_end: null,
      year: null,
      progress: 42,
      image_url:
        '/api/jellyfin/items/02c06be72a8c11102b98e17665c9fef2/images/Backdrop?size=wide&tag=609790cd6a30bf8277a008ba2fecb77f',
      ...overrides,
    }
  }

  const FILM = card({
    item_id: 'aaad8034da2f8c4db82f7aa3e26a4e3e',
    kind: 'movie',
    title: 'Oppenheimer',
    episode_name: '',
    season: null,
    episode_start: null,
    year: 2023,
    progress: 18,
    image_url: '',
  })

  function watching(overrides: Partial<Watching> = {}): StubRoute {
    return {
      body: {
        // 套件內的 Jellyfin：主機名由瀏覽器補上（jsdom 是 `http://localhost`）。
        jellyfin: { public_url: '', url: '', port: 8096 },
        resume: [card(), FILM],
        next_up: [card({ item_id: 'cd2f059cd4fdef1da23617e86514232e', progress: null })],
        ...overrides,
      } satisfies Watching,
    }
  }

  describe('讀取中的佔位（票 13：CLS）', () => {
    const KEY = 'berth.watching.skipper.home'

    /** 繼續觀看與下一集那一支一直不回：畫面停在讀取中。其餘照 `render` 的替身。 */
    function stalled() {
      const api = render()
      vi.stubGlobal('fetch', (input: RequestInfo | URL, init?: RequestInit) =>
        String(input).endsWith('/jellyfin/watching') ? new Promise(() => {}) : api(input, init),
      )
    }

    function placeholders() {
      return document.querySelectorAll('[data-placeholder="watching"]')
    }

    afterEach(() => {
      localStorage.clear()
      vi.restoreAllMocks()
    })

    it('讀到之後記下這一次兩列各幾格', async () => {
      render({ [WATCHING]: watching() })
      renderApp('/')

      await screen.findByRole('region', { name: '繼續觀看' })

      await waitFor(() =>
        expect(JSON.parse(localStorage.getItem(KEY) ?? 'null')).toEqual({ resume: 2, nextUp: 1 }),
      )
    })

    it('下一次讀取中照上一次的形狀佔位，而且佔位不在無障礙樹上', async () => {
      localStorage.setItem(KEY, JSON.stringify({ resume: 2, nextUp: 1 }))
      stalled()
      renderApp('/')

      await screen.findByRole('region', { name: '本週趨勢' })

      expect(placeholders()).toHaveLength(2)
      expect(screen.queryByRole('region', { name: '繼續觀看' })).not.toBeInTheDocument()
      expect(screen.queryByRole('heading', { name: '繼續觀看' })).not.toBeInTheDocument()
    })

    it('上一次只有下一集就只佔那一列；兩列都空就不佔', async () => {
      localStorage.setItem(KEY, JSON.stringify({ resume: 0, nextUp: 3 }))
      stalled()
      const { unmount } = renderApp('/')
      await screen.findByRole('region', { name: '本週趨勢' })
      expect(placeholders()).toHaveLength(1)
      unmount()

      localStorage.setItem(KEY, JSON.stringify({ resume: 0, nextUp: 0 }))
      renderApp('/')
      await screen.findByRole('region', { name: '本週趨勢' })
      expect(placeholders()).toHaveLength(0)
    })

    it.each([
      ['第一次來（沒有紀錄）', () => {}],
      ['紀錄是壞的', () => localStorage.setItem(KEY, '{"resume":-1}')],
      [
        '別人的紀錄',
        () => localStorage.setItem('berth.watching.deckhand.home', '{"resume":1,"nextUp":1}'),
      ],
      [
        '瀏覽器不給讀',
        () =>
          vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
            throw new DOMException('denied', 'SecurityError')
          }),
      ],
    ])('%s時不佔位，頁面照畫', async (_, arrange) => {
      arrange()
      stalled()
      renderApp('/')

      await screen.findByRole('region', { name: '本週趨勢' })

      expect(placeholders()).toHaveLength(0)
    })
  })

  it('兩列在探索牆上方，卡片說得出作品、季集、集名與看到哪，點下去開 Jellyfin 的那一集', async () => {
    render({ [WATCHING]: watching() })
    renderApp('/')

    const resume = await screen.findByRole('region', { name: '繼續觀看' })
    const next = screen.getByRole('region', { name: '下一集' })
    // 首頁的兩列直接攤開（brief §11.2b 拍板過的位置）；收成「接著看 N 項」的只有媒體庫頁（M2 票 14）。
    expect(screen.queryByRole('button', { name: /^接著看/ })).not.toBeInTheDocument()
    // 探索牆照舊。
    expect(await screen.findByRole('region', { name: '本週趨勢' })).toBeInTheDocument()
    // 兩列在搜尋列之前：打字時輸入框不會因為兩列收起而往上跳。
    const search = screen.getByRole('searchbox', { name: '搜尋作品' })
    expect(resume.compareDocumentPosition(search) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(next.compareDocumentPosition(search) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()

    const episode = within(resume).getByRole('link', { name: /葬送的芙莉蓮/ })
    // 名字從作品名念起（票 13），看到幾 % 是描述。
    expect(episode).toHaveAccessibleName(/^葬送的芙莉蓮 S01E05 冒險結束.*（開新分頁）$/)
    expect(episode).toHaveAccessibleDescription('看到 42%')
    expect(episode).toHaveAttribute(
      'href',
      'http://localhost:8096/web/#/details?id=99701a68c9a746b2f3a2d31d0b6c49f2',
    )
    expect(episode).toHaveAttribute('target', '_blank')
    expect(episode.querySelector('img')).toHaveAttribute('src', card().image_url)
    // 下一集那一列沒有看到幾 %。
    expect(within(next).getByRole('link', { name: /葬送的芙莉蓮/ })).not.toHaveTextContent(/看到/)
  })

  it('電影說類型代號與年份，沒有橫圖時同一塊印「無圖」', async () => {
    render({ [WATCHING]: watching() })
    renderApp('/')

    const film = within(await screen.findByRole('region', { name: '繼續觀看' })).getByRole('link', {
      name: /Oppenheimer/,
    })

    expect(film).toHaveTextContent('MOVIE')
    expect(film).toHaveTextContent('2023')
    expect(film).toHaveTextContent('看到 18%')
    expect(within(film).getByText('無圖')).toBeInTheDocument()
    expect(film.querySelector('img')).toBeNull()
  })

  it('沒有內容的那一列整個不畫', async () => {
    render({ [WATCHING]: watching({ resume: [] }) })
    renderApp('/')

    expect(await screen.findByRole('region', { name: '下一集' })).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: '繼續觀看' })).not.toBeInTheDocument()
  })

  it('一行放不下時多的收起來，「全部 N 項」就地展開、再按收起', async () => {
    const many = Array.from({ length: 8 }, (_, index) =>
      card({ item_id: `${index}`.padStart(32, '0'), title: `劇 ${index + 1}`, progress: null }),
    )
    render({ [WATCHING]: watching({ resume: [], next_up: many }) })
    renderApp('/')

    const next = await screen.findByRole('region', { name: '下一集' })
    const toggle = within(next).getByRole('button', { name: '全部 8 項' })
    const rows = within(next).getAllByRole('listitem')

    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(toggle).toHaveAttribute('aria-controls', within(next).getByRole('list').id)
    // 收起時每一格帶著「哪個寬度以上才出現」：窄版 2、sm 3、lg 4、xl 6 格，與牆同一份欄數。
    expect(rows.map((row) => row.className)).toEqual([
      '',
      '',
      'hidden sm:block',
      'hidden lg:block',
      'hidden xl:block',
      'hidden xl:block',
      'hidden',
      'hidden',
    ])

    await userEvent.click(toggle)

    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(toggle).toHaveAccessibleName('收起')
    expect(toggle).toHaveFocus()
    expect(
      within(next)
        .getAllByRole('listitem')
        .every((row) => row.className === ''),
    ).toBe(true)
  })

  it.each([
    [2, null],
    [3, 'sm:hidden'],
    [4, 'lg:hidden'],
    [6, 'xl:hidden'],
    [7, ''],
  ])('%i 格時「全部」鍵只在一行放不下的寬度出現', async (count, shown) => {
    const cards = Array.from({ length: count }, (_, index) =>
      card({ item_id: `${index}`.padStart(32, '0'), title: `劇 ${index + 1}` }),
    )
    render({ [WATCHING]: watching({ resume: cards, next_up: [] }) })
    renderApp('/')

    const resume = await screen.findByRole('region', { name: '繼續觀看' })
    const toggle = within(resume).queryByRole('button', { name: `全部 ${count} 項` })

    if (shown === null) {
      expect(toggle).not.toBeInTheDocument()
    } else {
      expect(toggle?.className.split(' ').filter((name) => name.endsWith('hidden'))).toEqual(
        shown ? [shown] : [],
      )
    }
  })

  it('主機推不出來時卡片不是連結，說不知道 Jellyfin 開在哪裡', async () => {
    render({
      [WATCHING]: watching({ jellyfin: { public_url: '', url: '', port: null }, next_up: [] }),
    })
    renderApp('/')

    const resume = await screen.findByRole('region', { name: '繼續觀看' })

    expect(within(resume).queryByRole('link')).not.toBeInTheDocument()
    expect(within(resume).getAllByText('不知道 Jellyfin 開在哪裡')).toHaveLength(2)
  })

  it('Jellyfin 連不上時兩列的位置說一行原因、可以重試，探索牆照畫', async () => {
    let attempts = 0
    render({
      [WATCHING]: () => {
        attempts += 1
        return attempts === 1
          ? {
              status: 503,
              body: {
                detail: {
                  reason: 'jellyfin_unreachable',
                  detail: 'GET /UserViews: connection refused',
                },
              },
            }
          : watching()
      },
    })
    renderApp('/')

    expect(await screen.findByText(/問不到 Jellyfin，繼續觀看與下一集暫時看不到/)).toBeVisible()
    expect(screen.getByText('GET /UserViews: connection refused')).toBeVisible()
    expect(await screen.findByRole('region', { name: '本週趨勢' })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: '重試' }))

    expect(await screen.findByRole('region', { name: '繼續觀看' })).toBeInTheDocument()
    expect(attempts).toBe(2)
  })

  it('帳號在 Jellyfin 被停用：session 結束，人被送回登入頁', async () => {
    const account = session({ name: 'deckhand', role: 'user' })
    stubApi({
      'GET /api/health': { body: HEALTHY },
      'GET /api/auth/me': account.me,
      [TRENDING]: wall([item()]),
      [POPULAR]: wall([MOANA]),
      [WATCHING]: () => {
        account.signOut()
        return { status: 401, body: { detail: { reason: 'account_disabled', detail: '' } } }
      },
    })
    const { router } = renderApp('/')

    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    expect(router.state.location.search).toMatchObject({ expired: true })
  })

  it('後端的其他錯誤不畫兩列也不說話：探索牆自己會說 Berth 沒有回應', async () => {
    render({ [WATCHING]: { status: 500, body: { detail: 'boom' } } })
    renderApp('/')

    await screen.findByRole('region', { name: '本週趨勢' })

    expect(screen.queryByRole('region', { name: '繼續觀看' })).not.toBeInTheDocument()
    expect(screen.queryByText(/問不到 Jellyfin/)).not.toBeInTheDocument()
  })
})
