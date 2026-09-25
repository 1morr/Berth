import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Media } from '../api/media'
import type { Feed, FeedItem, RssSeries } from '../api/rss'
import { HEALTHY, stubApi, type StubRoute } from '../test/fetch'
import { renderApp } from '../test/render'

afterEach(() => {
  vi.unstubAllGlobals()
})

const TITLE =
  '[喵萌奶茶屋&LoliHouse] 与你相恋到生命尽头 / Kimi ga Shinu made Koi wo Shitai - 12 [WebRip 1080p HEVC-10bit AAC][简繁日内封字幕]'
const FEED_URL = 'https://mikanani.me/RSS/MyBangumi?token=secret-token-value'

function feed(overrides: Partial<Feed> = {}): Feed {
  return {
    id: 1,
    name: 'Mikan',
    url: FEED_URL,
    kind: 'mikan',
    interval_sec: 900,
    last_polled_at: '2026-09-25T12:00:00Z',
    last_error: '',
    items: 12,
    ...overrides,
  }
}

function series(overrides: Partial<RssSeries> = {}): RssSeries {
  return {
    id: 7,
    key: 'mikan:4009:370',
    title_raw: TITLE,
    mikan_bangumi_id: 4009,
    mikan_subgroup_id: 370,
    media_id: null,
    media_title: '',
    media_title_en: '',
    route_id: null,
    route_name: '',
    season: null,
    episode_offset: null,
    bound_by: '',
    waiting: 2,
    reasons: [],
    candidates: [],
    submitted: 0,
    ...overrides,
  }
}

function item(overrides: Partial<FeedItem> = {}): FeedItem {
  return {
    id: 1,
    feed_id: 1,
    title: TITLE,
    link: 'https://mikanani.me/Home/Episode/85c93c23143bbeb98f9c0895d31ab18ceeed4090',
    published_at: '2026-09-24T08:08:01Z',
    seen_at: '2026-09-25T12:00:00Z',
    series_id: 7,
    status: 'unbound',
    job_hash: '',
    error: '',
    ...overrides,
  }
}

/** 綁定時讀的那一份詳情：只有畫面用得到的幾格。 */
const KIMI = {
  id: 'tv:262000',
  kind: 'tv',
  folder_name: 'Kimi ga Shinu made Koi wo Shitai (2026) [tmdbid-262000]',
  folder_frozen: false,
  default_route_id: null,
  routes: [{ id: 3, name: 'Anime', slug: 'anime', collection_type: 'tvshows' }],
} as Media

const FOUND = {
  items: [
    {
      id: 'tv:262000',
      tmdb_id: 262000,
      kind: 'tv',
      title: '與妳相戀到生命盡頭',
      title_en: 'Kimi ga Shinu made Koi wo Shitai',
      year: 2026,
      poster_url: '',
      poster_url_en: '',
      tracked: false,
    },
  ],
  problem: null,
  detail: '',
}

function render(routes: Record<string, StubRoute | (() => StubRoute)> = {}) {
  return stubApi({
    'GET /api/health': { body: HEALTHY },
    'GET /api/auth/me': { body: { name: 'skipper', role: 'admin' } },
    'GET /api/rss/feeds': { body: [feed()] },
    'GET /api/rss/series': { body: [series()] },
    'GET /api/rss/items': { body: [item()] },
    ...routes,
  })
}

function sent(stub: ReturnType<typeof stubApi>, method: string, path: string) {
  return stub.mock.calls.filter(
    ([input, init]) => String(input) === path && (init?.method ?? 'GET') === method,
  )
}

describe('RSS 頁', () => {
  it('待綁定排在最上面，塗一塊說出有幾個', async () => {
    render()
    renderApp('/rss')

    const [first] = await screen.findAllByRole('region')
    expect(within(first).getByRole('heading', { level: 2 })).toHaveTextContent('待綁定')
    expect(within(first).getByText('1 個待綁定')).toBeInTheDocument()
    expect(within(first).getByText(/留著 2 集，綁定之後送出/)).toBeInTheDocument()
  })

  it('沒有待綁定的就沒有那一段', async () => {
    render({ 'GET /api/rss/series': { body: [] } })
    renderApp('/rss')

    await screen.findByRole('heading', { name: 'Feed' })
    expect(screen.queryByRole('heading', { name: '待綁定' })).not.toBeInTheDocument()
  })

  it('綁定：搜尋預填作品名、選作品與 Route，確認時說出資料夾名與集數', async () => {
    let pending = [series()]
    const stub = render({
      'GET /api/rss/series': () => ({ body: pending }),
      'GET /api/discover/search?q=Kimi%20ga%20Shinu%20made%20Koi%20wo%20Shitai': { body: FOUND },
      'GET /api/media/tv%3A262000': { body: KIMI },
      'PUT /api/rss/series/7/binding': () => {
        pending = [series({ media_id: 'tv:262000', route_id: 3, route_name: 'Anime' })]
        return { body: { ...pending[0], submitted: 2 } }
      },
    })
    renderApp('/rss')
    const row = await screen.findByRole('article', { name: TITLE })

    await userEvent.click(within(row).getByRole('button', { name: '綁定' }))
    expect(within(row).getByRole('searchbox')).toHaveValue('Kimi ga Shinu made Koi wo Shitai')
    await userEvent.click(await within(row).findByRole('button', { name: /與妳相戀到生命盡頭/ }))

    // 唯一的那一條 Route 預選好；資料夾名是機器字串，原樣印出來。
    expect(await within(row).findByText(KIMI.folder_name)).toBeInTheDocument()
    expect(within(row).getByRole('combobox')).toHaveValue('3')
    await userEvent.click(within(row).getByRole('button', { name: '綁定並送出 2 集' }))

    await waitFor(() => expect(sent(stub, 'PUT', '/api/rss/series/7/binding')).toHaveLength(1))
    const [[, init]] = sent(stub, 'PUT', '/api/rss/series/7/binding')
    expect(JSON.parse(String(init?.body))).toEqual({ media: 'tv:262000', route: 3 })
    await waitFor(() =>
      expect(screen.queryByRole('heading', { name: '待綁定' })).not.toBeInTheDocument(),
    )
  })

  it('自動綁定沒綁上的那一列說出為什麼，候選一鍵選定就走同一支綁定', async () => {
    const TWO_ROUTES = {
      ...KIMI,
      routes: [
        { id: 3, name: 'Anime', slug: 'anime', collection_type: 'tvshows' },
        { id: 4, name: 'TV', slug: 'tv', collection_type: 'tvshows' },
      ],
    } as Media
    const stub = render({
      'GET /api/rss/series': {
        body: [
          series({
            reasons: [
              {
                code: 'title_equal',
                params: { clue: '与你相恋到生命尽头', title: '与你相恋到生命尽头' },
              },
              {
                code: 'premiere_near',
                params: { premiere: '2026-07-07', season: 1, aired: '2026-07-08' },
              },
              { code: 'route_ambiguous', params: { routes: 'Anime, TV' } },
            ],
            candidates: [
              {
                id: 'tv:262000',
                kind: 'tv',
                title: '與妳相戀到生命盡頭',
                title_en: 'Kimishinu',
                year: 2026,
              },
            ],
          }),
        ],
      },
      'GET /api/discover/search?q=Kimi%20ga%20Shinu%20made%20Koi%20wo%20Shitai': { body: FOUND },
      'GET /api/media/tv%3A262000': { body: TWO_ROUTES },
      'PUT /api/rss/series/7/binding': { body: { ...series(), submitted: 2 } },
    })
    renderApp('/rss')
    const row = await screen.findByRole('article', { name: TITLE })

    expect(within(row).getByText('沒有自動綁定：')).toBeInTheDocument()
    expect(within(row).getByText('作品認出來了，但 Anime, TV 都收得下它')).toBeInTheDocument()
    expect(
      within(row).getByText('Mikan 寫 2026-07-07 開播，TMDB 第 1 季 2026-07-08 首播'),
    ).toBeInTheDocument()

    await userEvent.click(within(row).getByRole('button', { name: /選《與妳相戀到生命盡頭》/ }))

    // 候選是按下的樣子；兩條 Route 不預選，選了才出現確認鍵。
    const choices = within(row).getByRole('list', { name: '候選' })
    expect(within(choices).getByRole('button', { name: /與妳相戀到生命盡頭/ })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(await within(row).findByText(KIMI.folder_name)).toBeInTheDocument()
    // 搜尋回的就是候選那一部：不再列一次，也不說「沒有找到」。
    expect(within(row).queryByRole('list', { name: '搜尋結果' })).not.toBeInTheDocument()
    expect(within(row).queryByText(/沒有找到/)).not.toBeInTheDocument()
    expect(within(row).queryByRole('button', { name: '綁定並送出 2 集' })).not.toBeInTheDocument()
    await userEvent.selectOptions(within(row).getByRole('combobox'), '3')
    await userEvent.click(within(row).getByRole('button', { name: '綁定並送出 2 集' }))

    await waitFor(() => expect(sent(stub, 'PUT', '/api/rss/series/7/binding')).toHaveLength(1))
    const [[, init]] = sent(stub, 'PUT', '/api/rss/series/7/binding')
    expect(JSON.parse(String(init?.body))).toEqual({ media: 'tv:262000', route: 3 })
  })

  it('自動綁好的那一列說出依據', async () => {
    render({
      'GET /api/rss/series': {
        body: [
          series({
            media_id: 'tv:262000',
            media_title: '與妳相戀到生命盡頭',
            route_id: 3,
            route_name: 'Anime',
            bound_by: 'system',
            waiting: 0,
            reasons: [
              {
                code: 'title_equal',
                params: { clue: '与你相恋到生命尽头', title: '与你相恋到生命尽头' },
              },
              { code: 'only_route', params: { route: 'Anime' } },
            ],
          }),
        ],
      },
    })
    renderApp('/rss')

    const row = await screen.findByRole('article', { name: '與妳相戀到生命盡頭' })
    expect(within(row).getByText(/自動綁定/)).toBeInTheDocument()
    expect(within(row).getByText('依據：')).toBeInTheDocument()
    expect(within(row).getByText('收得下它的 Route 只有 Anime')).toBeInTheDocument()
  })

  it('人綁的那一列不說依據', async () => {
    render({
      'GET /api/rss/series': {
        body: [
          series({
            media_id: 'tv:262000',
            media_title: '與妳相戀到生命盡頭',
            route_id: 3,
            route_name: 'Anime',
            bound_by: '1',
            waiting: 0,
            reasons: [{ code: 'several_candidates', params: { number: 2 } }],
          }),
        ],
      },
    })
    renderApp('/rss')

    const row = await screen.findByRole('article', { name: '與妳相戀到生命盡頭' })
    expect(within(row).queryByText('依據：')).not.toBeInTheDocument()
    expect(within(row).queryByText(/自動綁定/)).not.toBeInTheDocument()
  })

  it('聚合 feed 的 token 不整串印出來', async () => {
    render()
    renderApp('/rss')

    await screen.findByRole('heading', { name: 'Mikan' })
    expect(screen.queryByText(FEED_URL)).not.toBeInTheDocument()
    expect(screen.getByText('https://mikanani.me/RSS/MyBangumi?token=secr…')).toBeInTheDocument()
  })

  it('加 Feed 被拒時在欄位下說出為什麼', async () => {
    render({
      'POST /api/rss/feeds': {
        status: 422,
        body: {
          detail: { reason: 'feed_unsupported', detail: 'https://example.com/rss' },
        },
      },
    })
    renderApp('/rss')

    await userEvent.type(await screen.findByLabelText(/RSS 網址/), 'https://example.com/rss')
    await userEvent.click(screen.getByRole('button', { name: '加入' }))

    expect(await screen.findByText(/這一版只收 Mikan/)).toBeInTheDocument()
  })

  it('送不出去的那一筆塗阻擋色，帶著原文', async () => {
    render({
      'GET /api/rss/series': { body: [] },
      'GET /api/rss/items': {
        body: [item({ status: 'matched', error: 'low_disk_space: /data: 2.0 GiB free' })],
      },
    })
    renderApp('/rss')

    expect(await screen.findByText('送不出去')).toBeInTheDocument()
    expect(screen.getByText('low_disk_space: /data: 2.0 GiB free')).toBeInTheDocument()
  })
})
