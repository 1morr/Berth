import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18next from 'i18next'
import { afterEach, describe, expect, it, onTestFinished, vi } from 'vitest'

import type { Media } from '../api/media'
import type { Feed, FeedItem, OneshotItem, RssSeries } from '../api/rss'
import type { ManagedRoute } from '../api/routes'
import { relativePast } from '../components/relativeTime'
import { HEALTHY, REQUEST_FAILURES, stubApi, type StubRoute } from '../test/fetch'
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
    exclusions: [],
    primed_at: '2026-09-25T11:00:00Z',
    tv_route_id: null,
    movie_route_id: null,
    route_kinds: ['tv', 'movie'],
    ever_read: true,
    awaiting_route: { tv: 0, movie: 0 },
    ...overrides,
  }
}

function managed(
  id: number,
  name: string,
  collection_type: 'tvshows' | 'movies',
  enabled = true,
): ManagedRoute {
  return {
    route: { id, name, enabled, collection_type },
    jobs: 0,
    ledger_entries: 0,
    rss_feeds: 0,
    rss_series: 0,
    in_use: false,
  } as ManagedRoute
}

/** 預設安裝的三條（TV 與 Anime 都收劇集），加一條停用的。 */
const ROUTES = [
  managed(3, 'Anime', 'tvshows'),
  managed(4, 'TV', 'tvshows'),
  managed(5, 'Movies', 'movies'),
  managed(6, 'Old', 'tvshows', false),
]

/** 票 105 之前加的 Feed：劇集 Route 不只一條，migration 推不出來；它長出的一部停在待綁定。 */
const OLD = feed({ tv_route_id: null, movie_route_id: 5, awaiting_route: { tv: 1, movie: 0 } })

function series(overrides: Partial<RssSeries> = {}): RssSeries {
  return {
    id: 7,
    key: 'mikan:4009:370',
    title_raw: TITLE,
    mikan_bangumi_id: 4009,
    mikan_subgroup_id: 370,
    mikan_bangumi_name: '',
    mikan_subgroup_name: '',
    media_id: null,
    media_title: '',
    media_title_en: '',
    route_id: null,
    route_name: '',
    feed_routes: { tv: null, movie: null },
    season: null,
    episode_offset: null,
    bound_by: '',
    waiting: 2,
    reasons: [],
    candidates: [],
    exclusions: [],
    confirmed: false,
    search_term: 'Kimi ga Shinu made Koi wo Shitai',
    source: 'mikan',
    group: '喵萌奶茶屋&LoliHouse',
    latest_title: TITLE,
    latest_at: '2026-09-24T12:00:00Z',
    latest_episode: 12,
    imported: 0,
    active: 0,
    excluded: 0,
    finished: false,
    backfilled_at: null,
    submitted: 0,
    ask: null,
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
    series_id: 7,
    status: 'unbound',
    job_hash: '',
    error: '',
    skip: null,
    size: null,
    episode: 12,
    // 後端只對 `excluded` 判斷放不放得行；其他狀態一律 `item_not_excluded`（M4 票 111）。
    release_blocked: overrides.status === 'excluded' ? null : 'item_not_excluded',
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

function render(routes: Record<string, StubRoute | (() => StubRoute | Promise<StubRoute>)> = {}) {
  return stubApi({
    'GET /api/health': { body: HEALTHY },
    'GET /api/auth/me': { body: { name: 'skipper', role: 'admin' } },
    'GET /api/rss/feeds': { body: [feed()] },
    'GET /api/rss/series': { body: [series()] },
    'GET /api/rss/items': { body: [item()] },
    'GET /api/rss/exclusions': { body: { not_single: true, rules: [] } },
    'GET /api/routes': { body: [] },
    ...routes,
  })
}

function sent(stub: ReturnType<typeof stubApi>, method: string, path: string) {
  return stub.mock.calls.filter(
    ([input, init]) => String(input) === path && (init?.method ?? 'GET') === method,
  )
}

const ACGRIP = feed({
  id: 2,
  name: 'acg.rip',
  url: 'https://acg.rip/.xml?term=Kamiina+Botan',
  kind: 'acgrip',
  items: 4,
  primed_at: null,
})

/** 還沒選第一輪的 acg.rip feed 的預覽：綁好一筆、待綁定一筆、一個合集、一筆重複。 */
const PREVIEW: FeedItem[] = [
  item({
    id: 11,
    feed_id: 2,
    title: '[喵萌奶茶屋&LoliHouse] Kamiina - 12',
    status: 'matched',
    size: 500_000_000,
  }),
  item({ id: 12, feed_id: 2, title: '[北宇治字幕组] Kamiina [12]', status: 'unbound' }),
  item({
    id: 13,
    feed_id: 2,
    title: '[千夏字幕組][Kamiina][第01-12話][合集]',
    status: 'excluded',
    skip: { code: 'not_single', params: {} },
  }),
  item({
    id: 14,
    feed_id: 2,
    title: '[ANi] Kamiina - 11',
    status: 'duplicate',
    skip: { code: 'same_torrent', params: {} },
    job_hash: 'a'.repeat(40),
  }),
]

/** 頁首那一段裡的 acg.rip 那一塊（Feed 段也有一個同名的 `article`）。 */
async function firstRound() {
  const region = await screen.findByRole('region', { name: /等你決定/ })
  return within(region).getByRole('article', { name: 'acg.rip' })
}

describe('RSS 頁：新 Feed 的第一輪（票 11）', () => {
  it('還沒選的 Feed 浮到最上面，摘要與分組說出全部下載會下什麼', async () => {
    render({
      'GET /api/rss/feeds': { body: [feed(), ACGRIP] },
      'GET /api/rss/feeds/2/preview': { body: PREVIEW },
    })
    renderApp('/rss')

    const [first] = await screen.findAllByRole('region')
    expect(within(first).getByRole('heading', { level: 2 })).toHaveTextContent('等你決定')
    expect(within(first).getByText('1 個等你決定')).toBeInTheDocument()
    const block = within(first).getByRole('article', { name: 'acg.rip' })
    await waitFor(() => expect(block).toHaveTextContent(/會送出 1.*綁定之後送 1.*排除 1.*重複 1/))
    // 會下載的兩組攤開，不會下載的兩組收起。
    expect(within(block).getByText('[喵萌奶茶屋&LoliHouse] Kamiina - 12')).toBeInTheDocument()
    expect(within(block).getByText('[北宇治字幕组] Kamiina [12]')).toBeInTheDocument()
    expect(
      within(block).queryByText('[千夏字幕組][Kamiina][第01-12話][合集]'),
    ).not.toBeInTheDocument()
    await userEvent.click(within(block).getByRole('button', { name: '看排除（1 筆）' }))
    expect(within(block).getByText('[千夏字幕組][Kamiina][第01-12話][合集]')).toBeInTheDocument()
    expect(within(block).getByText(/不是單集/)).toBeInTheDocument()
  })

  it('只追之後的：送出選擇，那一塊消失，說出略過幾筆', async () => {
    let feeds = [feed(), ACGRIP]
    const stub = render({
      'GET /api/rss/feeds': () => ({ body: feeds }),
      'GET /api/rss/feeds/2/preview': { body: PREVIEW },
      'POST /api/rss/feeds/2/prime': () => {
        feeds = [feed(), { ...ACGRIP, primed_at: '2026-09-25T12:00:00Z' }]
        return { body: { feed: feeds[1], submitted: 0, passed: 3, excluded: 1 } }
      },
    })
    renderApp('/rss')
    const block = await firstRound()

    await userEvent.click(await within(block).findByRole('button', { name: '只追之後的' }))

    await waitFor(() => expect(sent(stub, 'POST', '/api/rss/feeds/2/prime')).toHaveLength(1))
    const [[, init]] = sent(stub, 'POST', '/api/rss/feeds/2/prime')
    expect(JSON.parse(String(init?.body))).toEqual({ mode: 'later' })
    await waitFor(() =>
      expect(screen.queryByRole('heading', { name: /等你決定/ })).not.toBeInTheDocument(),
    )
    expect(screen.getByText('《acg.rip》：只追之後的，略過 3 筆。')).toBeInTheDocument()
  })

  // DESIGN.md：送出中用 `busy` 不用 `disabled`——`disabled` 接不住焦點，按下去的那一刻鍵盤使用者
  // 就掉回 `body`（M1.5 票 05 先踩到，這裡是同一顆鍵重犯）。
  it('送出中焦點留在「只追之後的」上，不會掉回 body', async () => {
    let answer: (route: StubRoute) => void = () => {}
    render({
      'GET /api/rss/feeds': { body: [feed(), ACGRIP] },
      'GET /api/rss/feeds/2/preview': { body: PREVIEW },
      'POST /api/rss/feeds/2/prime': () => new Promise((resolve) => (answer = resolve)),
    })
    renderApp('/rss')
    const block = await firstRound()

    await userEvent.click(await within(block).findByRole('button', { name: '只追之後的' }))

    const pending = await within(block).findByRole('button', { name: '決定中…' })
    expect(pending).toHaveAttribute('aria-disabled', 'true')
    expect(pending).not.toBeDisabled()
    expect(pending).toHaveFocus()

    answer({ body: { feed: ACGRIP, submitted: 0, passed: 3, excluded: 1 } })
  })

  it('全部下載要就地確認，確認區塊說出送幾筆、幾筆等綁定', async () => {
    const stub = render({
      'GET /api/rss/feeds': { body: [feed(), ACGRIP] },
      'GET /api/rss/feeds/2/preview': { body: PREVIEW },
      'POST /api/rss/feeds/2/prime': {
        body: { feed: ACGRIP, submitted: 1, passed: 0, excluded: 1 },
      },
    })
    renderApp('/rss')
    const block = await firstRound()

    await userEvent.click(await within(block).findByRole('button', { name: '全部下載' }))
    expect(within(block).getByText(/會送出 1 筆到 qBittorrent，另外 1 筆/)).toBeInTheDocument()
    expect(sent(stub, 'POST', '/api/rss/feeds/2/prime')).toHaveLength(0)
    await userEvent.click(within(block).getByRole('button', { name: '全部下載' }))

    await waitFor(() => expect(sent(stub, 'POST', '/api/rss/feeds/2/prime')).toHaveLength(1))
    const [[, init]] = sent(stub, 'POST', '/api/rss/feeds/2/prime')
    expect(JSON.parse(String(init?.body))).toEqual({ mode: 'all' })
  })

  it('讀不到 feed 時說出原文，什麼都沒改', async () => {
    render({
      'GET /api/rss/feeds': { body: [feed(), ACGRIP] },
      'GET /api/rss/feeds/2/preview': { body: PREVIEW },
      'POST /api/rss/feeds/2/prime': {
        status: 502,
        body: { detail: { reason: 'feed_unreachable', detail: 'acg.rip: connection refused' } },
      },
    })
    renderApp('/rss')
    const block = await firstRound()

    await userEvent.click(await within(block).findByRole('button', { name: '只追之後的' }))

    expect(await within(block).findByText('acg.rip: connection refused')).toBeInTheDocument()
    expect(within(block).getByRole('alert')).toHaveTextContent(/不知道「之前」是哪幾筆/)
  })

  it('還沒讀過的 Feed 不給選', async () => {
    const stub = render({
      'GET /api/rss/feeds': {
        body: [feed(), { ...ACGRIP, last_polled_at: null, items: 0, ever_read: false }],
      },
    })
    renderApp('/rss')
    const block = await firstRound()

    expect(within(block).getByText(/第一輪還沒輪到/)).toBeInTheDocument()
    expect(within(block).queryByRole('button', { name: '只追之後的' })).not.toBeInTheDocument()
    expect(sent(stub, 'GET', '/api/rss/feeds/2/preview')).toHaveLength(0)
  })

  it('輪過但一次都沒讀到的 Feed 也不給選，說出上一次為什麼沒讀到', async () => {
    const stub = render({
      'GET /api/rss/feeds': {
        body: [
          feed(),
          { ...ACGRIP, items: 0, last_error: 'acg.rip: connection refused', ever_read: false },
        ],
      },
    })
    renderApp('/rss')
    const block = await firstRound()

    expect(within(block).getByText(/還沒讀到過，選不了/)).toBeInTheDocument()
    expect(within(block).getByText('acg.rip: connection refused')).toBeInTheDocument()
    expect(within(block).queryByRole('button', { name: '全部下載' })).not.toBeInTheDocument()
    expect(sent(stub, 'GET', '/api/rss/feeds/2/preview')).toHaveLength(0)
  })

  it('Feed 段那一列說一聲第一輪還沒決定', async () => {
    render({
      'GET /api/rss/feeds': { body: [ACGRIP] },
      'GET /api/rss/feeds/2/preview': { body: PREVIEW },
    })
    renderApp('/rss')

    const feeds = await screen.findByRole('region', { name: /^Feed/ })
    expect(within(feeds).getByText(/第一輪還沒決定，一筆都不送/)).toBeInTheDocument()
  })
})

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
    // Mikan 的 RSS Series 一律補舊集（票 12、M4 票 78）：沒有勾選；幾集要讀了才知道，鍵上不說總數。
    expect(within(row).queryByRole('checkbox')).not.toBeInTheDocument()
    // 每日補漏與 RSS Series 段落的說明同一句（M4 票 108）。
    expect(within(row).getByText(/讀這個字幕組在 Mikan 上的整季/)).toHaveTextContent(BACKFILL_LEDE)
    await userEvent.click(within(row).getByRole('button', { name: '綁定並送出' }))

    await waitFor(() => expect(sent(stub, 'PUT', '/api/rss/series/7/binding')).toHaveLength(1))
    const [[, init]] = sent(stub, 'PUT', '/api/rss/series/7/binding')
    expect(JSON.parse(String(init?.body))).toEqual({
      media: 'tv:262000',
      route: 3,
    })
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
    expect(within(row).queryByRole('button', { name: '綁定並送出' })).not.toBeInTheDocument()
    await userEvent.selectOptions(within(row).getByRole('combobox'), '3')
    await userEvent.click(within(row).getByRole('button', { name: '綁定並送出' }))

    await waitFor(() => expect(sent(stub, 'PUT', '/api/rss/series/7/binding')).toHaveLength(1))
    const [[, init]] = sent(stub, 'PUT', '/api/rss/series/7/binding')
    expect(JSON.parse(String(init?.body))).toEqual({
      media: 'tv:262000',
      route: 3,
    })
  })

  it('不是 Mikan 的 RSS Series 沒有整季可補：鍵說送出幾集', async () => {
    const stub = render({
      'GET /api/rss/series': {
        body: [
          series({ key: 'title:kimi:lolihouse', mikan_bangumi_id: null, mikan_subgroup_id: null }),
        ],
      },
      'GET /api/discover/search?q=Kimi%20ga%20Shinu%20made%20Koi%20wo%20Shitai': { body: FOUND },
      'GET /api/media/tv%3A262000': { body: KIMI },
      'PUT /api/rss/series/7/binding': { body: { ...series(), submitted: 2 } },
    })
    renderApp('/rss')
    const row = await screen.findByRole('article', { name: TITLE })
    await userEvent.click(within(row).getByRole('button', { name: '綁定' }))
    await userEvent.click(await within(row).findByRole('button', { name: /與妳相戀到生命盡頭/ }))

    await userEvent.click(await within(row).findByRole('button', { name: '綁定並送出 2 集' }))

    expect(within(row).queryByText(/讀這個字幕組在 Mikan 上的整季/)).not.toBeInTheDocument()
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

  it('這一輪沒讀到 Feed 時不說「新 0 筆」', async () => {
    render({
      'GET /api/rss/feeds': () => ({
        body: [feed({ last_error: 'mikanani.me: connection refused' })],
      }),
      'POST /api/rss/feeds/1/poll': {
        body: {
          items: 0,
          series: 0,
          bound: 0,
          submitted: 0,
          failed: 'mikanani.me: connection refused',
        },
      },
    })
    renderApp('/rss')

    const row = await screen.findByRole('article', { name: 'Mikan' })
    await userEvent.click(within(row).getByRole('button', { name: '立即輪詢' }))

    expect(await within(row).findByText(/這一輪沒讀到這個 Feed/)).toBeInTheDocument()
    expect(within(row).queryByText(/這一輪：新/)).not.toBeInTheDocument()
  })

  it('輪詢長出的待綁定把這一列推出畫面時，重畫之後捲回來', async () => {
    let polled = false
    render({
      'GET /api/rss/series': () => ({ body: polled ? [series()] : [] }),
      'POST /api/rss/feeds/1/poll': () => {
        polled = true
        return { body: { items: 12, series: 11, bound: 0, submitted: 0, failed: '' } }
      },
    })
    const scrolled = vi.fn()
    const original = Element.prototype.scrollIntoView
    Element.prototype.scrollIntoView = scrolled
    onTestFinished(() => {
      Element.prototype.scrollIntoView = original
    })
    renderApp('/rss')
    const row = await screen.findByRole('article', { name: 'Mikan' })
    // jsdom 沒有版面：這一列「被推到」視窗底下。
    vi.spyOn(row, 'getBoundingClientRect').mockReturnValue({
      top: 3000,
      bottom: 3200,
    } as DOMRect)

    await userEvent.click(within(row).getByRole('button', { name: '立即輪詢' }))

    await waitFor(() => expect(scrolled).toHaveBeenCalledWith({ block: 'nearest' }))
    expect(scrolled.mock.contexts).toContain(row)
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

    expect(await screen.findByText(/這一版收 Mikan/)).toBeInTheDocument()
  })

  it('加 Feed：劇集兩條要選、電影一條就預填，沒有「不指定」，Feed 那一列說出兩條（M4 票 105）', async () => {
    const stub = render({
      'GET /api/routes': { body: ROUTES },
      'GET /api/rss/feeds': { body: [feed({ tv_route_id: 3, movie_route_id: 5 })] },
      'POST /api/rss/feeds': { status: 201, body: feed({ id: 2, tv_route_id: 4 }) },
    })
    renderApp('/rss')

    const row = await screen.findByRole('article', { name: 'Mikan' })
    expect(await within(row).findByText('Anime')).toBeInTheDocument()
    expect(within(row).getByText('Movies')).toBeInTheDocument()
    expect(within(row).queryByText('要選 Route')).not.toBeInTheDocument()
    const series = screen.getByRole('combobox', { name: '劇集送進' })
    // 停用的那一條自動綁定本來就不看，不列；還沒選時是選不到的提示，不是「不指定」。
    expect(within(series).queryByRole('option', { name: 'Old' })).not.toBeInTheDocument()
    expect(within(series).queryByRole('option', { name: '不指定' })).not.toBeInTheDocument()
    expect(within(series).getByRole('option', { name: '選一條 Route' })).toBeDisabled()
    expect(screen.getByRole('combobox', { name: '電影送進' })).toHaveValue('5')
    await userEvent.type(screen.getByLabelText(/RSS 網址/), FEED_URL)
    expect(screen.getByRole('button', { name: '加入' })).toBeDisabled()
    await userEvent.selectOptions(series, 'TV')
    await userEvent.click(screen.getByRole('button', { name: '加入' }))

    await waitFor(() => expect(sent(stub, 'POST', '/api/rss/feeds')).toHaveLength(1))
    const [[, init]] = sent(stub, 'POST', '/api/rss/feeds')
    expect(JSON.parse(String(init?.body))).toEqual({
      url: FEED_URL,
      name: '',
      tv_route: 4,
      movie_route: 5,
      exclusions: [],
      interval_sec: 900,
    })
  })

  it('加 Feed 時就設排除條件：先記在表單裡、跟著加入一起送，卡片上是同一組（M4 票 110）', async () => {
    let feeds: Feed[] = []
    const stub = render({
      'GET /api/routes': { body: [managed(3, 'Anime', 'tvshows')] },
      'GET /api/rss/feeds': () => ({ body: feeds }),
      'POST /api/rss/feeds': () => {
        feeds = [feed({ tv_route_id: 3, exclusions: ['720p', '/v2$/'] })]
        return { status: 201, body: feeds[0] }
      },
    })
    renderApp('/rss')

    const rules = await screen.findByRole('group', { name: '排除條件' })
    expect(
      within(rules).getByText(/Mikan 加入之後很快就會開始下載，要排除的現在就加/),
    ).toBeVisible()
    // 新增表單也是 Feed 那一層：合集照全域（M4 票 113）。
    expect(within(rules).getByText('合集由全域設定：目前不自動下載。')).toBeVisible()
    await userEvent.click(within(rules).getByRole('button', { name: '加入「720p」' }))
    await userEvent.click(within(rules).getByRole('button', { name: '加入「简体」' }))
    await userEvent.type(within(rules).getByLabelText('加一條排除條件'), '/v2$/{Enter}')
    expect(within(rules).getByLabelText('加一條排除條件')).toHaveValue('')
    await userEvent.click(within(rules).getByRole('button', { name: '拿掉「简体」' }))
    expect(
      within(rules)
        .getAllByRole('listitem')
        .map((row) => row.textContent),
    ).toEqual(['720p×', '/v2$/×'])
    // 送出前不另打 API：規則只在表單裡。
    expect(stub.mock.calls.filter(([, init]) => init?.method === 'PUT')).toEqual([])

    await userEvent.type(screen.getByLabelText(/RSS 網址/), FEED_URL)
    await userEvent.click(screen.getByRole('button', { name: '加入' }))

    await waitFor(() => expect(sent(stub, 'POST', '/api/rss/feeds')).toHaveLength(1))
    expect(JSON.parse(String(sent(stub, 'POST', '/api/rss/feeds')[0][1]?.body))).toMatchObject({
      url: FEED_URL,
      tv_route: 3,
      exclusions: ['720p', '/v2$/'],
    })
    const row = await screen.findByRole('article', { name: 'Mikan' })
    await userEvent.click(within(row).getByRole('button', { name: /排除條件（2 條）/ }))
    expect(within(row).getByText('720p')).toBeVisible()
    expect(within(row).getByText('/v2$/')).toBeVisible()
    expect(within(rules).getByText('沒有標題規則。')).toBeInTheDocument()
  })

  it('加 Feed 時打了規則沒按「加入規則」：那一條也跟著送，送完表單清空', async () => {
    const stub = render({
      'GET /api/routes': { body: [managed(3, 'Anime', 'tvshows')] },
      'POST /api/rss/feeds': { status: 201, body: feed({ tv_route_id: 3, exclusions: ['720p'] }) },
    })
    renderApp('/rss')

    const rules = await screen.findByRole('group', { name: '排除條件' })
    await userEvent.click(within(rules).getByRole('button', { name: '加入「720p」' }))
    await userEvent.type(within(rules).getByLabelText('加一條排除條件'), ' 简体 ')
    await userEvent.type(screen.getByLabelText(/RSS 網址/), FEED_URL)
    await userEvent.click(screen.getByRole('button', { name: '加入' }))

    await waitFor(() => expect(sent(stub, 'POST', '/api/rss/feeds')).toHaveLength(1))
    expect(JSON.parse(String(sent(stub, 'POST', '/api/rss/feeds')[0][1]?.body)).exclusions).toEqual(
      ['720p', '简体'],
    )
    await waitFor(() => expect(within(rules).getByLabelText('加一條排除條件')).toHaveValue(''))
    expect(within(rules).getByText('沒有標題規則。')).toBeInTheDocument()
  })

  it('加 Feed 時規則寫壞：原因說在規則欄下，網址欄沒事，規則留著讓人改', async () => {
    render({
      'GET /api/routes': { body: [managed(3, 'Anime', 'tvshows')] },
      'POST /api/rss/feeds': {
        status: 422,
        body: {
          detail: {
            reason: 'rule_invalid',
            detail: '/[简繁/: unterminated character set at position 0',
          },
        },
      },
    })
    renderApp('/rss')

    const rules = await screen.findByRole('group', { name: '排除條件' })
    await userEvent.type(within(rules).getByLabelText('加一條排除條件'), '/[[简繁/{Enter}')
    const url = screen.getByLabelText(/RSS 網址/)
    await userEvent.type(url, FEED_URL)
    await userEvent.click(screen.getByRole('button', { name: '加入' }))

    expect(
      await within(rules).findByText('存不進去：/[简繁/: unterminated character set at position 0'),
    ).toBeInTheDocument()
    expect(url).not.toHaveAttribute('aria-invalid', 'true')
    expect(url).toHaveValue(FEED_URL)
    expect(within(rules).getByText('/[简繁/')).toBeInTheDocument()
  })

  it('英文：加 Feed 時的排除條件', async () => {
    let feeds: Feed[] = []
    const stub = render({
      'GET /api/routes': { body: [managed(3, 'Anime', 'tvshows')] },
      'GET /api/rss/feeds': () => ({ body: feeds }),
      'POST /api/rss/feeds': () => {
        feeds = [feed({ tv_route_id: 3, exclusions: ['720p'] })]
        return { status: 201, body: feeds[0] }
      },
    })
    await i18next.changeLanguage('en')
    try {
      renderApp('/rss')

      const rules = await screen.findByRole('group', { name: 'Exclusions' })
      expect(
        within(rules).getByText(/A Mikan feed starts downloading soon after it is added/),
      ).toBeVisible()
      await userEvent.click(within(rules).getByRole('button', { name: 'Add “720p”' }))
      await userEvent.type(screen.getByLabelText(/RSS address/), FEED_URL)
      await userEvent.click(screen.getByRole('button', { name: 'Add' }))

      await waitFor(() => expect(sent(stub, 'POST', '/api/rss/feeds')).toHaveLength(1))
      expect(
        JSON.parse(String(sent(stub, 'POST', '/api/rss/feeds')[0][1]?.body)).exclusions,
      ).toEqual(['720p'])
      const row = await screen.findByRole('article', { name: 'Mikan' })
      expect(within(row).getByRole('button', { name: /Exclusions \(1\)/ })).toBeVisible()
    } finally {
      await i18next.changeLanguage('zh-Hant')
    }
  })

  it('只有一條時預填它，一條都沒有的那一種不出現', async () => {
    render({ 'GET /api/routes': { body: [managed(3, 'Anime', 'tvshows')] } })
    renderApp('/rss')

    expect(await screen.findByRole('combobox', { name: '劇集送進' })).toHaveValue('3')
    expect(screen.queryByRole('combobox', { name: '電影送進' })).not.toBeInTheDocument()
  })

  it('舊 Feed 沒有劇集 Route：標「要選 Route」，改 Route 說出會當場綁上幾部', async () => {
    let feeds = [OLD]
    const stub = render({
      'GET /api/routes': { body: ROUTES },
      'GET /api/rss/feeds': () => ({ body: feeds }),
      'PUT /api/rss/feeds/1/routes': () => {
        feeds = [feed({ tv_route_id: 3, movie_route_id: 5 })]
        return { body: { feed: feeds[0], bound: 1, submitted: 12 } }
      },
    })
    renderApp('/rss')

    const row = await screen.findByRole('article', { name: 'Mikan' })
    expect(await within(row).findByText('要選 Route')).toBeInTheDocument()
    expect(within(row).getByText(/沒說劇集送進哪一條/)).toBeInTheDocument()
    await userEvent.click(within(row).getByRole('button', { name: '改 Route' }))
    const panel = within(row).getByRole('group', { name: /自動綁定到這裡/ })
    expect(within(panel).getByText(/停在待綁定的 1 部會當場綁上/)).toBeInTheDocument()
    expect(within(panel).getByRole('combobox', { name: '電影送進' })).toHaveValue('5')
    expect(within(panel).getByRole('button', { name: '存下並綁上 1 部' })).toBeDisabled()
    await userEvent.selectOptions(
      within(panel).getByRole('combobox', { name: '劇集送進' }),
      'Anime',
    )
    await userEvent.click(within(panel).getByRole('button', { name: '存下並綁上 1 部' }))

    await waitFor(() => expect(sent(stub, 'PUT', '/api/rss/feeds/1/routes')).toHaveLength(1))
    const [[, init]] = sent(stub, 'PUT', '/api/rss/feeds/1/routes')
    expect(JSON.parse(String(init?.body))).toEqual({ tv_route: 3, movie_route: 5 })
    expect(await within(row).findByText('存下了：當場綁上 1 部、送出 12 筆。')).toBeInTheDocument()
    await waitFor(() => expect(within(row).queryByText('要選 Route')).not.toBeInTheDocument())
  })

  it('從作品頁訂閱一部劇集的 Feed：兩條電影 Route 也不標要選，改 Route 只問劇集', async () => {
    const MOVIES_TWO = [...ROUTES, managed(7, 'Cinema', 'movies')]
    render({
      'GET /api/routes': { body: MOVIES_TWO },
      'GET /api/rss/feeds': {
        body: [feed({ tv_route_id: 3, movie_route_id: null, route_kinds: ['tv'] })],
      },
    })
    renderApp('/rss')

    const row = await screen.findByRole('article', { name: 'Mikan' })
    expect(await within(row).findByText('Anime')).toBeInTheDocument()
    expect(within(row).queryByText('要選 Route')).not.toBeInTheDocument()
    expect(within(row).queryByText(/電影送進/)).not.toBeInTheDocument()
    await userEvent.click(within(row).getByRole('button', { name: '改 Route' }))
    expect(within(row).queryByRole('combobox', { name: '電影送進' })).not.toBeInTheDocument()
    expect(within(row).getByRole('button', { name: '存下 Route' })).toBeEnabled()
  })

  it('英文：要選 Route 與改 Route 的句子', async () => {
    render({ 'GET /api/routes': { body: ROUTES }, 'GET /api/rss/feeds': { body: [OLD] } })
    await i18next.changeLanguage('en')
    try {
      renderApp('/rss')

      const row = await screen.findByRole('article', { name: 'Mikan' })
      expect(await within(row).findByText(/doesn't say which route series go into/)).toBeVisible()
      await userEvent.click(within(row).getByRole('button', { name: 'Change routes' }))
      expect(
        within(row).getByText(/the 1 title it grew that waits in unbound .* is bound on the spot/),
      ).toBeInTheDocument()
      expect(within(row).getByRole('button', { name: 'Save and bind 1 title' })).toBeDisabled()
    } finally {
      await i18next.changeLanguage('zh-Hant')
    }
  })

  it('手動綁定：Feed 說劇集送進 Anime，作品沒認出來的那一列選好作品後「入庫到」預選 Anime', async () => {
    const TWO_ROUTES = {
      ...KIMI,
      routes: [
        { id: 4, name: 'TV', slug: 'tv', collection_type: 'tvshows' },
        { id: 3, name: 'Anime', slug: 'anime', collection_type: 'tvshows' },
      ],
    } as Media
    render({
      'GET /api/rss/series': { body: [series({ feed_routes: { tv: 3, movie: 5 } })] },
      'GET /api/discover/search?q=Kimi%20ga%20Shinu%20made%20Koi%20wo%20Shitai': { body: FOUND },
      'GET /api/media/tv%3A262000': { body: TWO_ROUTES },
    })
    renderApp('/rss')
    const row = await screen.findByRole('article', { name: TITLE })

    await userEvent.click(within(row).getByRole('button', { name: '綁定' }))
    await userEvent.click(await within(row).findByRole('button', { name: /與妳相戀到生命盡頭/ }))

    expect(await within(row).findByRole('combobox', { name: '入庫到' })).toHaveValue('3')
  })

  it('手動綁定：選了電影作品就照 Feed 的電影那一格', async () => {
    const MOVIE = {
      ...KIMI,
      id: 'movie:900',
      kind: 'movie',
      routes: [
        { id: 5, name: 'Movies', slug: 'movies', collection_type: 'movies' },
        { id: 7, name: 'Cinema', slug: 'cinema', collection_type: 'movies' },
      ],
    } as Media
    const found = {
      ...FOUND,
      items: [{ ...FOUND.items[0], id: 'movie:900', tmdb_id: 900, kind: 'movie' }],
    }
    render({
      'GET /api/rss/series': { body: [series({ feed_routes: { tv: 3, movie: 7 } })] },
      'GET /api/discover/search?q=Kimi%20ga%20Shinu%20made%20Koi%20wo%20Shitai': { body: found },
      'GET /api/media/movie%3A900': { body: MOVIE },
    })
    renderApp('/rss')
    const row = await screen.findByRole('article', { name: TITLE })

    await userEvent.click(within(row).getByRole('button', { name: '綁定' }))
    await userEvent.click(await within(row).findByRole('button', { name: /與妳相戀到生命盡頭/ }))

    expect(await within(row).findByRole('combobox', { name: '入庫到' })).toHaveValue('7')
  })

  it('Feed 那一條被停用了也標「要選 Route」，改 Route 不沿用它', async () => {
    render({
      'GET /api/routes': { body: [...ROUTES.slice(1), managed(3, 'Anime', 'tvshows', false)] },
      'GET /api/rss/feeds': { body: [feed({ tv_route_id: 3, movie_route_id: 5 })] },
    })
    renderApp('/rss')

    const row = await screen.findByRole('article', { name: 'Mikan' })
    expect(await within(row).findByText('要選 Route')).toBeInTheDocument()
    await userEvent.click(within(row).getByRole('button', { name: '改 Route' }))
    expect(within(row).getByRole('combobox', { name: '劇集送進' })).toHaveValue('4')
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

  it('排除與重複的那一筆說出為什麼沒下載，不塗漆；重複的連到那一筆下載', async () => {
    render({
      'GET /api/rss/series': { body: [] },
      'GET /api/rss/items': {
        body: [
          item({
            id: 1,
            status: 'excluded',
            skip: { code: 'feed_rule', params: { rule: '720p' } },
          }),
          item({
            id: 2,
            status: 'duplicate',
            job_hash: 'a'.repeat(40),
            skip: { code: 'same_torrent', params: {} },
          }),
          item({
            id: 3,
            status: 'duplicate',
            skip: { code: 'in_library', params: { known: 'Kimi (2026) - S01E12 [1080p].mkv' } },
          }),
        ],
      },
    })
    renderApp('/rss')

    const list = await screen.findByRole('region', { name: /最近的 Feed Item/ })
    expect(within(list).getByText('已排除')).toBeInTheDocument()
    expect(within(list).getByText('這個 Feed 的排除條件「720p」擋下')).toBeInTheDocument()
    expect(within(list).getAllByText('重複')).toHaveLength(2)
    expect(within(list).getByText(/同一個 torrent 已經送過了/)).toBeInTheDocument()
    expect(
      within(list).getByText('媒體庫裡已經有同一個版本：Kimi (2026) - S01E12 [1080p].mkv'),
    ).toBeInTheDocument()
    expect(within(list).getAllByRole('link', { name: '看這一筆下載' })).toHaveLength(1)
  })

  it('全域：建議項一鍵加入，合集預設可以關掉', async () => {
    const stub = render({
      'PUT /api/rss/exclusions': { body: { not_single: true, rules: ['720p'] } },
    })
    renderApp('/rss')

    const section = await screen.findByRole('region', { name: '全域排除條件' })
    expect(within(section).getByText('沒有標題規則。')).toBeInTheDocument()
    const collections = within(section).getByRole('checkbox', { name: /不自動下載合集/ })
    expect(collections).toBeChecked()

    await userEvent.click(within(section).getByRole('button', { name: '加入「720p」' }))
    await waitFor(() => expect(sent(stub, 'PUT', '/api/rss/exclusions')).toHaveLength(1))
    expect(JSON.parse(String(sent(stub, 'PUT', '/api/rss/exclusions')[0][1]?.body))).toEqual({
      not_single: true,
      rules: ['720p'],
    })

    await userEvent.click(collections)
    await waitFor(() => expect(sent(stub, 'PUT', '/api/rss/exclusions')).toHaveLength(2))
    expect(JSON.parse(String(sent(stub, 'PUT', '/api/rss/exclusions')[1][1]?.body))).toEqual({
      not_single: false,
      rules: [],
    })
  })

  it('正則寫壞時在欄位下說出原因，打的字留著', async () => {
    render({
      'PUT /api/rss/exclusions': {
        status: 422,
        body: {
          detail: {
            reason: 'rule_invalid',
            detail: '/[简繁/: unterminated character set at position 0',
          },
        },
      },
    })
    renderApp('/rss')

    const section = await screen.findByRole('region', { name: '全域排除條件' })
    const field = within(section).getByLabelText('加一條排除條件')
    // user-event 的 `[` 是按鍵描述的開頭，`[[` 才是字面上的一個。
    await userEvent.type(field, '/[[简繁/')
    await userEvent.click(within(section).getByRole('button', { name: '加入規則' }))

    expect(
      await within(section).findByText(
        '存不進去：/[简繁/: unterminated character set at position 0',
      ),
    ).toBeInTheDocument()
    expect(field).toHaveValue('/[简繁/')
    expect(field).toHaveAttribute('aria-invalid', 'true')
  })

  it('Feed 那一層：展開才編輯，拿掉一條之後焦點回到加入欄', async () => {
    const stub = render({
      'GET /api/rss/feeds': { body: [feed({ exclusions: ['720p', '/v2$/i'] })] },
      'PUT /api/rss/feeds/1/exclusions': { body: feed({ exclusions: ['/v2$/i'] }) },
    })
    renderApp('/rss')

    const row = await screen.findByRole('article', { name: 'Mikan' })
    const toggle = within(row).getByRole('button', { name: /排除條件（2 條）/ })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'true')

    await userEvent.click(within(row).getByRole('button', { name: '拿掉「720p」' }))

    await waitFor(() => expect(sent(stub, 'PUT', '/api/rss/feeds/1/exclusions')).toHaveLength(1))
    expect(
      JSON.parse(String(sent(stub, 'PUT', '/api/rss/feeds/1/exclusions')[0][1]?.body)),
    ).toEqual({ rules: ['/v2$/i'] })
    await waitFor(() => expect(within(row).getByLabelText('加一條排除條件')).toHaveFocus())
  })

  it('RSS Series 那一層：待綁定的也編得到', async () => {
    const stub = render({
      'PUT /api/rss/series/7/exclusions': { body: series({ exclusions: ['简体'] }) },
    })
    renderApp('/rss')

    const pending = await screen.findByRole('region', { name: '待綁定' })
    await userEvent.click(within(pending).getByRole('button', { name: /排除條件（0 條）/ }))
    await userEvent.type(within(pending).getByLabelText('加一條排除條件'), ' 简体 ')
    await userEvent.click(within(pending).getByRole('button', { name: '加入規則' }))

    await waitFor(() => expect(sent(stub, 'PUT', '/api/rss/series/7/exclusions')).toHaveLength(1))
    expect(
      JSON.parse(String(sent(stub, 'PUT', '/api/rss/series/7/exclusions')[0][1]?.body)),
    ).toEqual({ rules: ['简体'] })
  })
})

describe('RSS 頁：每個 Feed 的輪詢間隔（M4 票 109）', () => {
  const CASES = [
    {
      lng: 'zh-Hant',
      url: /RSS 網址/,
      add: '加入',
      interval: '輪詢間隔',
      every15: /^每 15 分鐘/,
      every6h: /^每 6 小時/,
      every1d: /^每 24 小時/,
      sixHours: '6 小時',
      oneDay: '24 小時',
      change: '改輪詢間隔',
      save: '存下間隔',
      saved: '存下了：之後每 24 小時輪詢一次。',
      lede: /不會馬上輪詢/,
    },
    {
      lng: 'en',
      url: /RSS address/,
      add: 'Add',
      interval: 'Poll interval',
      every15: /^Every 15 minutes/,
      every6h: /^Every 6 hours/,
      every1d: /^Every 24 hours/,
      sixHours: '6 hours',
      oneDay: '24 hours',
      change: 'Change poll interval',
      save: 'Save interval',
      saved: 'Saved: polled every 24 hours from now on.',
      lede: /does not poll right away/,
    },
  ] as const

  it.each(CASES)('$lng：新增表單選檔位，預設 15 分鐘，存完 Feed 列說出新值', async (copy) => {
    let feeds: Feed[] = []
    const stub = render({
      'GET /api/routes': { body: [managed(3, 'Anime', 'tvshows')] },
      'GET /api/rss/feeds': () => ({ body: feeds }),
      'POST /api/rss/feeds': () => {
        feeds = [feed({ tv_route_id: 3, interval_sec: 21600 })]
        return { status: 201, body: feeds[0] }
      },
    })
    await i18next.changeLanguage(copy.lng)
    try {
      renderApp('/rss')

      const interval = await screen.findByRole('combobox', { name: copy.interval })
      expect(interval).toHaveValue('900')
      expect(within(interval).getAllByRole('option')).toHaveLength(7)
      await userEvent.selectOptions(interval, copy.sixHours)
      await userEvent.type(screen.getByLabelText(copy.url), FEED_URL)
      await userEvent.click(screen.getByRole('button', { name: copy.add }))

      await waitFor(() => expect(sent(stub, 'POST', '/api/rss/feeds')).toHaveLength(1))
      expect(
        JSON.parse(String(sent(stub, 'POST', '/api/rss/feeds')[0][1]?.body)).interval_sec,
      ).toBe(21600)
      const row = await screen.findByRole('article', { name: 'Mikan' })
      expect(within(row).getByText(copy.every6h)).toBeInTheDocument()
      // 送完表單回到預設。
      await waitFor(() => expect(interval).toHaveValue('900'))
    } finally {
      await i18next.changeLanguage('zh-Hant')
    }
  })

  it.each(CASES)('$lng：Feed 列就地改間隔，存完收起、那一列說出新值', async (copy) => {
    let feeds: Feed[] = [feed()]
    const stub = render({
      'GET /api/rss/feeds': () => ({ body: feeds }),
      'PUT /api/rss/feeds/1/interval': () => {
        feeds = [feed({ interval_sec: 86400 })]
        return { body: feeds[0] }
      },
    })
    await i18next.changeLanguage(copy.lng)
    try {
      renderApp('/rss')

      const row = await screen.findByRole('article', { name: 'Mikan' })
      expect(within(row).getByText(copy.every15)).toBeInTheDocument()
      await userEvent.click(within(row).getByRole('button', { name: copy.change }))
      expect(within(row).getByText(copy.lede)).toBeVisible()
      const picker = within(row).getByRole('combobox', { name: copy.interval })
      expect(picker).toHaveValue('900')
      await userEvent.selectOptions(picker, copy.oneDay)
      await userEvent.click(within(row).getByRole('button', { name: copy.save }))

      await waitFor(() => expect(sent(stub, 'PUT', '/api/rss/feeds/1/interval')).toHaveLength(1))
      expect(
        JSON.parse(String(sent(stub, 'PUT', '/api/rss/feeds/1/interval')[0][1]?.body)),
      ).toEqual({ interval_sec: 86400 })
      expect(await within(row).findByText(copy.every1d)).toBeInTheDocument()
      expect(within(row).getByRole('status')).toHaveTextContent(copy.saved)
      expect(within(row).queryByRole('combobox', { name: copy.interval })).not.toBeInTheDocument()
      expect(within(row).getByRole('button', { name: copy.change })).toHaveFocus()
    } finally {
      await i18next.changeLanguage('zh-Hant')
    }
  })

  it('改間隔被拒時說出原因，選的留著', async () => {
    render({
      'PUT /api/rss/feeds/1/interval': {
        status: 422,
        body: { detail: { reason: 'interval_unsupported', detail: '600' } },
      },
    })
    renderApp('/rss')

    const row = await screen.findByRole('article', { name: 'Mikan' })
    await userEvent.click(within(row).getByRole('button', { name: '改輪詢間隔' }))
    await userEvent.selectOptions(within(row).getByRole('combobox', { name: '輪詢間隔' }), '1 小時')
    await userEvent.click(within(row).getByRole('button', { name: '存下間隔' }))

    expect(await within(row).findByText('只能選清單上的間隔，什麼都沒存。')).toBeInTheDocument()
    expect(within(row).getByRole('combobox', { name: '輪詢間隔' })).toHaveValue('3600')
  })
})

describe('RSS 頁：排除條件分清全域與內建（M4 票 113）', () => {
  it('全域那一段：合集是內建判斷、與規則分開，建議項是關鍵字', async () => {
    render()
    renderApp('/rss')

    const section = await screen.findByRole('region', { name: '全域排除條件' })
    const builtin = within(section).getByRole('group', { name: '內建判斷' })
    expect(builtin).toHaveAccessibleDescription('看解析結果，不是關鍵字')
    expect(within(builtin).getByRole('checkbox', { name: /不自動下載合集/ })).toBeChecked()
    const rules = within(section).getByRole('group', { name: '標題規則' })
    expect(within(rules).queryByRole('checkbox')).not.toBeInTheDocument()
    expect(within(rules).getByText('建議關鍵字')).toBeVisible()
  })

  it('全域那一段的英文', async () => {
    render()
    await i18next.changeLanguage('en')
    try {
      renderApp('/rss')

      const section = await screen.findByRole('region', { name: 'Global exclusions' })
      const builtin = within(section).getByRole('group', { name: 'Built-in check' })
      expect(within(builtin).getByText('Reads the parsed release, not keywords')).toBeVisible()
      expect(within(builtin).getByRole('checkbox', { name: /batches/ })).toBeChecked()
      const rules = within(section).getByRole('group', { name: 'Title rules' })
      expect(within(rules).getByText('Suggested keywords')).toBeVisible()
    } finally {
      await i18next.changeLanguage('zh-Hant')
    }
  })

  it('Feed 與 RSS Series 那兩層說出全域的合集設定，切換全域開關後跟著變', async () => {
    let notSingle = true
    render({
      'GET /api/rss/exclusions': () => ({ body: { not_single: notSingle, rules: [] } }),
      'PUT /api/rss/exclusions': () => {
        notSingle = false
        return { body: { not_single: false, rules: [] } }
      },
    })
    renderApp('/rss')

    const row = await screen.findByRole('article', { name: 'Mikan' })
    await userEvent.click(within(row).getByRole('button', { name: /排除條件（0 條）/ }))
    const pending = screen.getByRole('region', { name: '待綁定' })
    await userEvent.click(within(pending).getByRole('button', { name: /排除條件（0 條）/ }))
    for (const layer of [row, pending]) {
      expect(within(layer).getByText('合集由全域設定：目前不自動下載。')).toBeVisible()
      expect(within(layer).getByRole('link', { name: '改全域設定' })).toHaveAttribute(
        'href',
        '#global-exclusions',
      )
    }
    expect(screen.getByRole('region', { name: '全域排除條件' })).toHaveAttribute(
      'id',
      'global-exclusions',
    )

    await userEvent.click(screen.getByRole('checkbox', { name: /不自動下載合集/ }))

    for (const layer of [row, pending]) {
      expect(await within(layer).findByText('合集由全域設定：目前會自動下載。')).toBeVisible()
    }
  })

  it('兩層的合集那一行的英文', async () => {
    render({ 'GET /api/rss/exclusions': { body: { not_single: false, rules: [] } } })
    await i18next.changeLanguage('en')
    try {
      renderApp('/rss')

      const row = await screen.findByRole('article', { name: 'Mikan' })
      await userEvent.click(within(row).getByRole('button', { name: /Exclusions \(0\)/ }))
      expect(
        within(row).getByText(
          'Batches follow the global setting: currently downloaded automatically.',
        ),
      ).toBeVisible()
      expect(within(row).getByRole('link', { name: 'Change the global setting' })).toBeVisible()
    } finally {
      await i18next.changeLanguage('zh-Hant')
    }
  })
})

/** 綁好的《与你相恋》：喵萌奶茶屋&LoliHouse 與 ANi 兩組（M4 票 13）。 */
function boundKimi(overrides: Partial<RssSeries> = {}): RssSeries {
  return series({
    media_id: 'tv:262000',
    media_title: '與妳相戀到生命盡頭',
    media_title_en: 'Kimishinu',
    route_id: 3,
    route_name: 'Anime',
    bound_by: '1',
    waiting: 0,
    confirmed: true,
    mikan_bangumi_name: '与你相恋到生命尽头',
    mikan_subgroup_name: 'LoliHouse',
    imported: 11,
    active: 1,
    excluded: 0,
    latest_episode: 12,
    ...overrides,
  })
}

const ANI = boundKimi({
  id: 8,
  key: 'mikan:4009:583',
  mikan_subgroup_id: 583,
  mikan_subgroup_name: 'ANi',
  group: 'ANi',
  imported: 3,
  active: 0,
  excluded: 2,
  latest_episode: 4,
})

/** 每日補漏的說明（M4 票 108）：RSS Series 段落、綁定確認、作品頁的訂閱確認說同一句。 */
const BACKFILL_LEDE =
  '綁好的 Mikan 字幕組每天再讀一次它在 Mikan 上的整季清單，補上 Feed 輪詢沒接到的集數（例如 Berth 停機的期間）；完結之後就不再讀。'

/** 綁好的非 Mikan RSS Series：沒有單一 feed，也就沒有補漏。 */
const NYAA = boundKimi({
  id: 10,
  key: 'nyaa:subsplease kimi',
  mikan_bangumi_id: null,
  mikan_subgroup_id: null,
  mikan_bangumi_name: '',
  mikan_subgroup_name: '',
  source: 'nyaa',
  group: 'SubsPlease',
})

describe('RSS 頁：每日補漏看得見（M4 票 108）', () => {
  const at = new Date(Date.now() - 3 * 3600_000).toISOString()

  it('Mikan 的一列說上次補漏、尚未補漏、已完結不再補漏；非 Mikan 的不說', async () => {
    render({
      'GET /api/rss/series': {
        body: [
          boundKimi({ backfilled_at: at }),
          { ...ANI, backfilled_at: null },
          boundKimi({
            id: 11,
            key: 'mikan:4009:1',
            mikan_subgroup_name: 'Done',
            finished: true,
            backfilled_at: at,
          }),
          NYAA,
        ],
      },
    })
    renderApp('/rss')

    const region = await screen.findByRole('region', { name: /RSS Series/ })
    expect(within(region).getByText(BACKFILL_LEDE)).toBeVisible()
    const loli = within(region).getByRole('article', { name: 'LoliHouse' })
    expect(loli).toHaveTextContent(`上次補漏：${relativePast(new Date(at), 'zh-Hant')}`)
    expect(within(region).getByRole('article', { name: 'ANi' })).toHaveTextContent('尚未補漏')
    const done = within(region).getByRole('article', { name: 'Done' })
    expect(done).toHaveTextContent('已完結，不再補漏')
    expect(done).not.toHaveTextContent('上次補漏')
    const nyaa = within(region).getByRole('article', { name: 'SubsPlease' })
    expect(nyaa).not.toHaveTextContent(/補漏/)
  })

  it.each(['zh-Hant', 'en'])('%s：訂閱與綁定確認句尾就是段落那一句（巢狀展開）', (lng) => {
    const lede = i18next.t('rss.bound.backfillLede', { lng })
    for (const key of ['rss.subscribe.season', 'rss.bind.willSendSeason'] as const) {
      const text = i18next.t(key, { lng })
      expect(text.endsWith(lede)).toBe(true)
      expect(text).not.toContain('$t(')
    }
  })

  it('英文介面同樣三種，段落說明也是英文', async () => {
    render({
      'GET /api/rss/series': {
        body: [
          boundKimi({ backfilled_at: at }),
          { ...ANI, backfilled_at: null },
          boundKimi({ id: 11, key: 'mikan:4009:1', mikan_subgroup_name: 'Done', finished: true }),
          NYAA,
        ],
      },
    })
    await i18next.changeLanguage('en')
    try {
      renderApp('/rss')

      const region = await screen.findByRole('region', { name: /RSS Series/ })
      expect(within(region).getByText(/whole season list read again once a day/)).toBeVisible()
      expect(within(region).getByRole('article', { name: 'LoliHouse' })).toHaveTextContent(
        `Last daily backfill: ${relativePast(new Date(at), 'en')}`,
      )
      expect(within(region).getByRole('article', { name: 'ANi' })).toHaveTextContent(
        'No daily backfill yet',
      )
      expect(within(region).getByRole('article', { name: 'Done' })).toHaveTextContent(
        'Finished, no more daily backfills',
      )
      expect(within(region).getByRole('article', { name: 'SubsPlease' })).not.toHaveTextContent(
        /backfill/,
      )
    } finally {
      await i18next.changeLanguage('zh-Hant')
    }
  })
})

describe('RSS 頁：以作品呈現 Series（M4 票 13）', () => {
  it('畫面上不出現 Mikan 的數字 id：待綁定、綁好的、沒讀到名字的都一樣', async () => {
    render({
      'GET /api/rss/series': {
        body: [
          series({ mikan_bangumi_id: 3985, mikan_subgroup_id: 583, key: 'mikan:3985:583' }),
          boundKimi(),
          boundKimi({ id: 9, key: 'mikan:4009:1', mikan_subgroup_id: 1, mikan_bangumi_name: '' }),
        ],
      },
    })
    renderApp('/rss')

    await screen.findByRole('region', { name: /RSS Series/ })
    const text = document.body.textContent ?? ''
    for (const id of ['3985', '583', '4009', '370', 'mikan:']) expect(text).not.toContain(id)
    // 名字讀到了就說名字，連到 Mikan 的番組頁（id 只在網址裡）。
    const link = screen.getAllByRole('link', { name: 'Mikan：与你相恋到生命尽头' })[0]
    expect(link).toHaveAttribute('href', 'https://mikanani.me/Home/Bangumi/4009#370')
  })

  it('同一部作品的兩個字幕組是一塊：作品名與 Route 在塊上，一組一列說件數與最近一集', async () => {
    render({ 'GET /api/rss/series': { body: [boundKimi(), ANI] } })
    renderApp('/rss')

    const work = await screen.findByRole('article', { name: '與妳相戀到生命盡頭' })
    expect(within(work).getByText('Anime')).toBeInTheDocument()
    const loli = within(work).getByRole('article', { name: 'LoliHouse' })
    expect(loli).toHaveTextContent('已入庫 11')
    expect(loli).toHaveTextContent('在路上 1')
    expect(loli).toHaveTextContent('排除 0')
    expect(loli).toHaveTextContent('最近 E12')
    const ani = within(work).getByRole('article', { name: 'ANi' })
    expect(ani).toHaveTextContent('排除 2')
    expect(ani).toHaveTextContent('最近 E04')
    // 長出它的那一筆（`title_raw`）不當成標題，也不當成「最近」。
    expect(within(work).queryByText(TITLE)).not.toBeInTheDocument()
  })

  it('展開一列才讀它的 Item：每一筆的狀態、集數、Job；Series 層的排除條件在進階裡', async () => {
    const stub = render({
      'GET /api/rss/series': { body: [boundKimi()] },
      'GET /api/rss/series/7/items': {
        body: [
          item({ id: 2, status: 'downloaded', job_hash: 'b'.repeat(40) }),
          item({
            id: 1,
            title: TITLE.replace(' - 12 ', ' - 11 '),
            episode: 11,
            status: 'excluded',
            skip: { code: 'series_rule', params: { rule: '720p' } },
          }),
        ],
      },
    })
    renderApp('/rss')

    const row = await screen.findByRole('article', { name: 'LoliHouse' })
    expect(sent(stub, 'GET', '/api/rss/series/7/items')).toHaveLength(0)
    await userEvent.click(within(row).getByText('展開'))

    const list = await within(row).findByRole('list')
    const lines = within(list).getAllByRole('listitem')
    expect(lines[0]).toHaveTextContent('已送單')
    expect(lines[0]).toHaveTextContent('E12')
    expect(within(lines[0]).getByRole('link', { name: '看這一筆下載' })).toHaveAttribute(
      'href',
      `/jobs/${'b'.repeat(40)}`,
    )
    expect(lines[1]).toHaveTextContent('已排除')
    expect(lines[1]).toHaveTextContent('E11')
    expect(within(row).getByText('進階')).toBeInTheDocument()
    expect(within(row).getByRole('button', { name: /排除條件（0 條）/ })).toBeInTheDocument()
    expect(within(row).getByRole('button', { name: '解除綁定' })).toBeInTheDocument()
  })

  it('讀不到它的 Item 時說出來，給一顆重讀', async () => {
    render({
      'GET /api/rss/series': { body: [boundKimi()] },
      'GET /api/rss/series/7/items': { status: 503, body: {} },
    })
    renderApp('/rss')

    const row = await screen.findByRole('article', { name: 'LoliHouse' })
    await userEvent.click(within(row).getByText('展開'))

    expect(await within(row).findByRole('alert')).toHaveTextContent(/讀不到它的 Feed Item。/)
    expect(within(row).getByRole('button', { name: '重讀' })).toBeInTheDocument()
  })

  it('完結的收進段尾預設收起的「已完結」，上面只留還在追的', async () => {
    render({ 'GET /api/rss/series': { body: [boundKimi({ finished: true }), ANI] } })
    renderApp('/rss')

    const region = await screen.findByRole('region', { name: /RSS Series/ })
    const finished = within(region).getByText('已完結 1 個').closest('details')
    expect(finished).not.toHaveAttribute('open')
    expect(
      within(finished as HTMLElement).getByRole('article', { name: 'LoliHouse' }),
    ).toBeInTheDocument()
    const active = within(region).getAllByRole('article', { name: '與妳相戀到生命盡頭' })[0]
    expect(within(active).getByRole('article', { name: 'ANi' })).toBeInTheDocument()
    expect(within(active).queryByRole('article', { name: 'LoliHouse' })).not.toBeInTheDocument()
  })

  it('全部完結時說沒有還在追的', async () => {
    render({ 'GET /api/rss/series': { body: [boundKimi({ finished: true })] } })
    renderApp('/rss')

    expect(await screen.findByText('沒有還在追的 RSS Series。')).toBeInTheDocument()
  })

  it('最近的 Feed Item 每一筆說出來自哪個 Feed、屬於哪個 Series；沒綁的說待綁定', async () => {
    render({
      'GET /api/rss/series': {
        body: [boundKimi(), series({ id: 9, key: 'mikan:1:1', group: 'ANi' })],
      },
      'GET /api/rss/items': {
        body: [item({ id: 1, series_id: 7, status: 'downloaded' }), item({ id: 2, series_id: 9 })],
      },
    })
    renderApp('/rss')

    const list = await screen.findByRole('region', { name: /最近的 Feed Item/ })
    const [bound, pending] = within(list).getAllByRole('listitem')
    expect(bound).toHaveTextContent('來自 Mikan · 與妳相戀到生命盡頭 × LoliHouse')
    expect(pending).toHaveTextContent('來自 Mikan · 待綁定')
  })
})

const SINGLE_URL = 'https://mikanani.me/RSS/Bangumi?bangumiId=4009&subgroupid=370'
const KIMI_RELEASE = '[喵萌奶茶屋&LoliHouse] 与你相恋到生命尽头 / Kimi ga Shinu made Koi wo Shitai'
const KIMI_SEARCH = 'GET /api/discover/search?q=Kimi%20ga%20Shinu%20made%20Koi%20wo%20Shitai'

function oneshotItem(guid: string, overrides: Partial<OneshotItem> = {}): OneshotItem {
  return {
    guid,
    title: `${KIMI_RELEASE} - ${guid} [WebRip 1080p]`,
    link: `https://mikanani.me/Home/Episode/${guid}`,
    source_id: `source-${guid}`,
    size: 500_000_000,
    published_at: '2026-09-24T08:08:01Z',
    release_kind: 'single',
    tags: {
      source: 'WEB',
      resolution: '1080p',
      subs: [],
      hardsub: false,
      group: '喵萌奶茶屋&LoliHouse',
      version: '',
      edition: '',
    },
    season: null,
    episode_start: Number(guid),
    episode_end: Number(guid),
    whole_season: false,
    strategy: null,
    job_hash: '',
    known: null,
    search_term: 'Kimi ga Shinu made Koi wo Shitai',
    ...overrides,
  }
}

/** feed 的順序（新的在前）：03 已經有下載、02、01，再一個 01–12 的合集。 */
const ONESHOT: OneshotItem[] = [
  oneshotItem('03', { job_hash: '03'.padStart(40, '0') }),
  oneshotItem('02'),
  oneshotItem('01'),
  oneshotItem('batch', {
    title: `[LoliHouse] ${KIMI_RELEASE} [01-12 合集][WebRip 1080p]`,
    release_kind: 'collection',
    episode_start: 1,
    episode_end: 12,
  }),
]

/** 送單替身：照順序一次回一個。 */
function answers(...replies: StubRoute[]) {
  let next = 0
  return () => replies[Math.min(next++, replies.length - 1)]
}

function created(hash: string, fresh = true): StubRoute {
  return { body: { job: { hash }, created: fresh } }
}

async function readLink() {
  const region = await screen.findByRole('region', { name: '一次性 RSS 連結' })
  await userEvent.type(within(region).getByLabelText(/要讀的網址/), SINGLE_URL)
  await userEvent.click(within(region).getByRole('button', { name: '讀取' }))
  return region
}

function bodies(stub: ReturnType<typeof stubApi>, method: string, path: string) {
  return sent(stub, method, path).map(([, init]) => JSON.parse(String(init?.body)))
}

function episodeBox(list: HTMLElement, episode: string) {
  return within(list).getByRole('checkbox', { name: `${KIMI_RELEASE} - ${episode} [WebRip 1080p]` })
}

describe('RSS 頁：一次性 RSS 連結（票 18）', () => {
  it('讀、選作品與 Route、勾三筆：舊的先，逐筆走一般的送單', async () => {
    const stub = render({
      'POST /api/rss/oneshot': { body: { kind: 'mikan', items: ONESHOT } },
      [KIMI_SEARCH]: { body: FOUND },
      'GET /api/media/tv%3A262000': { body: KIMI },
      'POST /api/jobs': answers(
        created('a'.repeat(40)),
        created('b'.repeat(40)),
        created('c'.repeat(40), false),
      ),
    })
    renderApp('/rss')
    const region = await readLink()

    const list = await within(region).findByRole('list', { name: '勾選要送出的' })
    expect(within(list).getAllByRole('checkbox')).toHaveLength(4)
    // 合集只標示、不擋；已經有下載的那一筆說一聲。沒選作品時季集是發佈名寫的。
    expect(within(list).getByText('合集')).toBeInTheDocument()
    expect(within(list).getByText('這一筆已經有下載了。')).toBeInTheDocument()
    expect(within(list).getByText('E02')).toBeInTheDocument()
    expect(within(region).getByText(/選好作品與 Route 才送得出去/)).toBeInTheDocument()
    expect(bodies(stub, 'POST', '/api/rss/oneshot')).toEqual([
      { url: SINGLE_URL, media: null, route: null },
    ])

    // 搜尋框預填第一筆的 `search_term`（後端讀的作品名）；唯一的 Route 預選好，清單照那部作品重讀一次。
    expect(within(region).getByRole('searchbox')).toHaveValue('Kimi ga Shinu made Koi wo Shitai')
    await userEvent.click(await within(region).findByRole('button', { name: /與妳相戀到生命盡頭/ }))
    expect(await within(region).findByText(KIMI.folder_name)).toBeInTheDocument()
    await waitFor(() =>
      expect(bodies(stub, 'POST', '/api/rss/oneshot').at(-1)).toEqual({
        url: SINGLE_URL,
        media: 'tv:262000',
        route: 3,
      }),
    )

    // 「勾選全部單集」不勾合集、不勾已經有下載的；合集另外勾。
    await userEvent.click(within(region).getByRole('button', { name: '勾選全部單集（2 筆）' }))
    await userEvent.click(within(list).getByRole('checkbox', { name: /01-12 合集/ }))
    await userEvent.click(within(region).getByRole('button', { name: '送出 3 筆' }))

    await waitFor(() => expect(sent(stub, 'POST', '/api/jobs')).toHaveLength(3))
    const jobs = bodies(stub, 'POST', '/api/jobs')
    // 送的是伺服器記下的那一筆的 id，不是網址（M4 票 79）。
    expect(jobs.map((body) => body.source_id)).toEqual([
      ONESHOT[3].source_id,
      ONESHOT[2].source_id,
      ONESHOT[1].source_id,
    ])
    expect(jobs[0]).toEqual({
      source_id: ONESHOT[3].source_id,
      media: 'tv:262000',
      route: 3,
    })
    expect(
      await within(region).findByText('送出 2 筆；1 筆本來就在了；0 筆沒有送出。'),
    ).toBeInTheDocument()
    expect(within(list).getAllByText('已送出')).toHaveLength(2)
    expect(within(list).getByText('本來就在了')).toBeInTheDocument()
  })

  it('一筆被拒不擋下一筆，那一列說出理由、還勾著', async () => {
    const stub = render({
      'POST /api/rss/oneshot': { body: { kind: 'mikan', items: ONESHOT } },
      [KIMI_SEARCH]: { body: FOUND },
      'GET /api/media/tv%3A262000': { body: KIMI },
      'POST /api/jobs': answers(
        { status: 422, body: { detail: { reason: 'source_unavailable', detail: 'HTTP 404' } } },
        created('b'.repeat(40)),
      ),
    })
    renderApp('/rss')
    const region = await readLink()
    await userEvent.click(await within(region).findByRole('button', { name: /與妳相戀到生命盡頭/ }))
    await within(region).findByText(KIMI.folder_name)
    const list = within(region).getByRole('list', { name: '勾選要送出的' })
    await userEvent.click(episodeBox(list, '01'))
    await userEvent.click(episodeBox(list, '02'))
    await userEvent.click(within(region).getByRole('button', { name: '送出 2 筆' }))

    expect(
      await within(region).findByText('送出 1 筆；0 筆本來就在了；1 筆沒有送出。'),
    ).toBeInTheDocument()
    expect(sent(stub, 'POST', '/api/jobs')).toHaveLength(2)
    expect(within(list).getByText('HTTP 404')).toBeInTheDocument()
    expect(episodeBox(list, '01')).toBeChecked()
    expect(within(region).getByRole('button', { name: '送出 1 筆' })).toBeEnabled()
  })

  it('讀到的不是 RSS 時在欄位下說出是哪一種失敗，附上原文', async () => {
    render({
      'POST /api/rss/oneshot': {
        status: 502,
        body: { detail: { reason: 'feed_not_rss', detail: 'the response is not an RSS feed' } },
      },
    })
    renderApp('/rss')
    const region = await readLink()

    expect(await within(region).findByText(/讀到了，但那不是 RSS/)).toBeInTheDocument()
    expect(within(region).getByText('the response is not an RSS feed')).toBeInTheDocument()
    expect(within(region).queryByRole('list', { name: '勾選要送出的' })).not.toBeInTheDocument()
  })

  it('讀不到之後同一條網址再按一次「讀取」就重讀', async () => {
    const stub = render({
      'POST /api/rss/oneshot': answers(
        {
          status: 502,
          body: { detail: { reason: 'feed_unreachable', detail: 'GET: connection refused' } },
        },
        { body: { kind: 'mikan', items: ONESHOT } },
      ),
    })
    renderApp('/rss')
    const region = await readLink()
    expect(await within(region).findByText(/現在讀不到這個網址/)).toBeInTheDocument()

    await userEvent.click(within(region).getByRole('button', { name: '讀取' }))

    expect(await within(region).findByRole('list', { name: '勾選要送出的' })).toBeInTheDocument()
    expect(sent(stub, 'POST', '/api/rss/oneshot')).toHaveLength(2)
    expect(within(region).queryByText(/現在讀不到這個網址/)).not.toBeInTheDocument()
  })

  it('沒有 Feed 時也在：它不建 Feed', async () => {
    render({ 'GET /api/rss/feeds': { body: [] } })
    renderApp('/rss')

    expect(await screen.findByRole('region', { name: '一次性 RSS 連結' })).toBeInTheDocument()
  })
})

// M4 票 90：RSS 頁各處的請求解析不出拒絕原因時，原本一律說「沒有做成」或「Berth 的 API 沒回應」——500 與 401 也是。
describe('RSS 頁對 Berth 的請求沒成時說出對的原因', () => {
  const NOT_DONE = /沒有成功。/
  // 離線那一句本身就說「它可能沒在跑」，所以舊句只認「後端可能沒在跑」那個尾巴。
  const NOT_THE_OLD = /自己的 API|後端可能沒在跑|還活著/

  function expectCause(element: HTMLElement, lead: RegExp, expected: RegExp) {
    expect(element).toHaveTextContent(lead)
    expect(element).toHaveTextContent(expected)
    expect(element).not.toHaveTextContent(NOT_THE_OLD)
  }

  it.each(REQUEST_FAILURES)('整頁讀不到清單（%s）', async (_, failure, expected) => {
    render({ 'GET /api/rss/feeds': failure })
    renderApp('/rss')

    expectCause(await screen.findByRole('alert'), /讀不到 RSS 的清單。/, expected)
  })

  it.each(REQUEST_FAILURES)('加 Feed（%s）：欄位下說出原因', async (_, failure, expected) => {
    render({ 'POST /api/rss/feeds': failure })
    renderApp('/rss')

    await userEvent.type(await screen.findByLabelText(/RSS 網址/), 'https://example.com/rss')
    await userEvent.click(screen.getByRole('button', { name: '加入' }))

    const field = await screen.findByLabelText(/RSS 網址/)
    await waitFor(() => expect(field).toHaveAttribute('aria-invalid', 'true'))
    expectCause(field.closest('form')!, NOT_DONE, expected)
  })

  it.each(REQUEST_FAILURES)('立即輪詢（%s）', async (_, failure, expected) => {
    render({ 'POST /api/rss/feeds/1/poll': failure })
    renderApp('/rss')
    const row = await screen.findByRole('article', { name: 'Mikan' })

    await userEvent.click(within(row).getByRole('button', { name: '立即輪詢' }))

    expectCause(await within(row).findByRole('alert'), NOT_DONE, expected)
  })

  it.each(REQUEST_FAILURES)('全域排除條件的開關（%s）', async (_, failure, expected) => {
    render({ 'PUT /api/rss/exclusions': failure })
    renderApp('/rss')
    const section = await screen.findByRole('region', { name: '全域排除條件' })

    await userEvent.click(within(section).getByRole('checkbox', { name: /不自動下載合集/ }))

    expectCause(await within(section).findByRole('alert'), NOT_DONE, expected)
  })

  it.each(REQUEST_FAILURES)('加一條排除規則（%s）', async (_, failure, expected) => {
    render({ 'PUT /api/rss/exclusions': failure })
    renderApp('/rss')
    const section = await screen.findByRole('region', { name: '全域排除條件' })

    await userEvent.type(within(section).getByLabelText('加一條排除條件'), '720p')
    await userEvent.click(within(section).getByRole('button', { name: '加入規則' }))

    const field = within(section).getByLabelText('加一條排除條件')
    await waitFor(() => expect(field).toHaveAttribute('aria-invalid', 'true'))
    expectCause(field.parentElement!.parentElement!, NOT_DONE, expected)
  })

  it.each(REQUEST_FAILURES)('綁定（%s）', async (_, failure, expected) => {
    render({
      'GET /api/discover/search?q=Kimi%20ga%20Shinu%20made%20Koi%20wo%20Shitai': { body: FOUND },
      'GET /api/media/tv%3A262000': { body: KIMI },
      'PUT /api/rss/series/7/binding': failure,
    })
    renderApp('/rss')
    const row = await screen.findByRole('article', { name: TITLE })

    await userEvent.click(within(row).getByRole('button', { name: '綁定' }))
    await userEvent.click(await within(row).findByRole('button', { name: /與妳相戀到生命盡頭/ }))
    await within(row).findByText(KIMI.folder_name)
    await userEvent.click(within(row).getByRole('button', { name: '綁定並送出' }))

    expectCause(await within(row).findByRole('alert'), NOT_DONE, expected)
  })

  it.each(REQUEST_FAILURES)('解除綁定（%s）', async (_, failure, expected) => {
    render({
      'GET /api/rss/series': { body: [boundKimi()] },
      'DELETE /api/rss/series/7/binding': failure,
    })
    renderApp('/rss')
    const row = await screen.findByRole('article', { name: 'LoliHouse' })

    await userEvent.click(within(row).getByRole('button', { name: '解除綁定' }))
    await userEvent.click(within(row).getByRole('button', { name: '解除綁定' }))

    expectCause(await within(row).findByRole('alert'), NOT_DONE, expected)
  })

  // 排除舊句：離線那一句本身含「可能沒在跑」，所以只認舊句獨有的字。
  const NOT_THE_OLD_API = /自己的 API|還活著/

  it.each(REQUEST_FAILURES)('綁定時搜不到作品（%s）', async (_, failure, expected) => {
    render({ 'GET /api/discover/search?q=Kimi%20ga%20Shinu%20made%20Koi%20wo%20Shitai': failure })
    renderApp('/rss')
    const row = await screen.findByRole('article', { name: TITLE })

    await userEvent.click(within(row).getByRole('button', { name: '綁定' }))

    const alert = await within(row).findByRole('alert')
    expect(alert).toHaveTextContent(/沒有搜成。/)
    expect(alert).toHaveTextContent(expected)
    expect(alert).not.toHaveTextContent(NOT_THE_OLD_API)
  })

  it.each(REQUEST_FAILURES)('綁定時讀不到作品詳情（%s）', async (_, failure, expected) => {
    render({
      'GET /api/discover/search?q=Kimi%20ga%20Shinu%20made%20Koi%20wo%20Shitai': { body: FOUND },
      'GET /api/media/tv%3A262000': failure,
    })
    renderApp('/rss')
    const row = await screen.findByRole('article', { name: TITLE })

    await userEvent.click(within(row).getByRole('button', { name: '綁定' }))
    await userEvent.click(await within(row).findByRole('button', { name: /與妳相戀到生命盡頭/ }))

    const alert = await within(row).findByRole('alert')
    expect(alert).toHaveTextContent(/讀不到這部作品的詳情。/)
    expect(alert).toHaveTextContent(expected)
    expect(alert).not.toHaveTextContent(NOT_THE_OLD_API)
  })

  it.each(REQUEST_FAILURES)('一次性連結搜不到作品（%s）', async (_, failure, expected) => {
    render({
      'POST /api/rss/oneshot': { body: { kind: 'mikan', items: ONESHOT } },
      [KIMI_SEARCH]: failure,
    })
    renderApp('/rss')
    const region = await readLink()

    const alert = await within(region).findByRole('alert')
    expect(alert).toHaveTextContent(/沒有搜成。/)
    expect(alert).toHaveTextContent(expected)
    expect(alert).not.toHaveTextContent(NOT_THE_OLD_API)
  })

  it.each(REQUEST_FAILURES)('一次性連結讀不到作品詳情（%s）', async (_, failure, expected) => {
    render({
      'POST /api/rss/oneshot': { body: { kind: 'mikan', items: ONESHOT } },
      [KIMI_SEARCH]: { body: FOUND },
      'GET /api/media/tv%3A262000': failure,
    })
    renderApp('/rss')
    const region = await readLink()
    await userEvent.click(await within(region).findByRole('button', { name: /與妳相戀到生命盡頭/ }))

    const alert = await within(region).findByRole('alert')
    expect(alert).toHaveTextContent(/讀不到這部作品的詳情。/)
    expect(alert).toHaveTextContent(expected)
    expect(alert).not.toHaveTextContent(NOT_THE_OLD_API)
  })

  it.each(REQUEST_FAILURES)('讀不到已綁定那一列的 Item（%s）', async (_, failure, expected) => {
    render({
      'GET /api/rss/series': { body: [boundKimi()] },
      'GET /api/rss/series/7/items': failure,
    })
    renderApp('/rss')
    const row = await screen.findByRole('article', { name: 'LoliHouse' })

    await userEvent.click(within(row).getByText('展開'))

    const alert = await within(row).findByRole('alert')
    expect(alert).toHaveTextContent(/讀不到它的 Feed Item。/)
    expect(alert).toHaveTextContent(expected)
    expect(alert).not.toHaveTextContent(NOT_THE_OLD_API)
    expect(within(row).getByRole('button', { name: '重讀' })).toBeVisible()
  })

  it.each(REQUEST_FAILURES)('第一輪讀不到預覽（%s）', async (_, failure, expected) => {
    render({
      'GET /api/rss/feeds': { body: [feed(), ACGRIP] },
      'GET /api/rss/feeds/2/preview': failure,
    })
    renderApp('/rss')
    const block = await firstRound()

    expectCause(await within(block).findByRole('alert'), /讀不到這個 Feed 讀到的內容。/, expected)
  })

  it.each(REQUEST_FAILURES)('第一輪送出選擇（%s）', async (_, failure, expected) => {
    render({
      'GET /api/rss/feeds': { body: [feed(), ACGRIP] },
      'GET /api/rss/feeds/2/preview': { body: PREVIEW },
      'POST /api/rss/feeds/2/prime': failure,
    })
    renderApp('/rss')
    const block = await firstRound()

    await userEvent.click(await within(block).findByRole('button', { name: '只追之後的' }))

    expectCause(await within(block).findByRole('alert'), NOT_DONE, expected)
  })

  it('第一輪送出被拒：後端說得出理由的一律畫出來，不再落回通用句', async () => {
    render({
      'GET /api/rss/feeds': { body: [feed(), ACGRIP] },
      'GET /api/rss/feeds/2/preview': { body: PREVIEW },
      'POST /api/rss/feeds/2/prime': {
        status: 409,
        body: { detail: { reason: 'feed_unread', detail: '' } },
      },
    })
    renderApp('/rss')
    const block = await firstRound()

    await userEvent.click(await within(block).findByRole('button', { name: '只追之後的' }))

    expect(await within(block).findByRole('alert')).toHaveTextContent(/這個 Feed 還沒讀過/)
  })

  it.each(REQUEST_FAILURES)(
    '一次性連結讀不到（%s）：欄位下說出原因',
    async (_, failure, expected) => {
      render({ 'POST /api/rss/oneshot': failure })
      renderApp('/rss')
      const region = await readLink()

      const field = within(region).getByLabelText(/要讀的網址/)
      await waitFor(() => expect(field).toHaveAttribute('aria-invalid', 'true'))
      expectCause(field.closest('form')!, NOT_DONE, expected)
    },
  )

  it.each(REQUEST_FAILURES)('一次性連結送到一半停下（%s）', async (_, failure, expected) => {
    render({
      'POST /api/rss/oneshot': { body: { kind: 'mikan', items: ONESHOT } },
      [KIMI_SEARCH]: { body: FOUND },
      'GET /api/media/tv%3A262000': { body: KIMI },
      'POST /api/jobs': failure,
    })
    renderApp('/rss')
    const region = await readLink()
    await userEvent.click(await within(region).findByRole('button', { name: /與妳相戀到生命盡頭/ }))
    await within(region).findByText(KIMI.folder_name)
    const list = within(region).getByRole('list', { name: '勾選要送出的' })
    await userEvent.click(episodeBox(list, '01'))
    await userEvent.click(within(region).getByRole('button', { name: '送出 1 筆' }))

    expectCause(await within(region).findByRole('alert'), /送到一半停下來了/, expected)
  })
})

describe('RSS 頁：被排除的那一筆仍然下載（M4 票 111）', () => {
  const COLLECTION = TITLE.replace(' - 12 ', ' [01-12 合集] ')
  const HELD = item({
    id: 21,
    title: COLLECTION,
    episode: null,
    status: 'excluded',
    skip: { code: 'not_single', params: {} },
  })
  const SENT = { ...HELD, status: 'downloaded', skip: null, job_hash: 'c'.repeat(40) } as const

  /** 放行之後重問的那一份換成已送單。 */
  function releasing(answer: StubRoute = { body: SENT }) {
    let items: FeedItem[] = [HELD]
    return render({
      'GET /api/rss/series': { body: [boundKimi()] },
      'GET /api/rss/items': () => ({ body: items }),
      'GET /api/rss/series/7/items': () => ({ body: items }),
      'POST /api/rss/items/21/release': () => {
        if (answer.status === undefined) items = [answer.body as FeedItem]
        return answer
      },
    })
  }

  async function recent() {
    const region = await screen.findByRole('region', { name: /最近的 Feed Item|Recent feed items/ })
    return within(region).findByRole('listitem')
  }

  it('最近的 Feed Item：按下去當場送出，那一列換成送出去的 Job', async () => {
    const stub = releasing()
    renderApp('/rss')
    const line = await recent()
    expect(line).toHaveTextContent('已排除')

    await userEvent.click(within(line).getByRole('button', { name: '仍然下載' }))

    await waitFor(() => expect(sent(stub, 'POST', '/api/rss/items/21/release')).toHaveLength(1))
    const after = await recent()
    await waitFor(() => expect(after).toHaveTextContent('已送單'))
    expect(within(after).getByRole('link', { name: '看這一筆下載' })).toHaveAttribute(
      'href',
      `/jobs/${'c'.repeat(40)}`,
    )
    expect(within(after).queryByRole('button', { name: '仍然下載' })).not.toBeInTheDocument()
  })

  it('RSS Series 展開的清單也有，英文介面同一顆', async () => {
    const stub = releasing()
    await i18next.changeLanguage('en')
    try {
      renderApp('/rss')
      const row = await screen.findByRole('article', { name: 'LoliHouse' })
      await userEvent.click(within(row).getByText('Expand'))
      const list = await within(row).findByRole('list')

      await userEvent.click(within(list).getByRole('button', { name: 'Download anyway' }))

      await waitFor(() => expect(sent(stub, 'POST', '/api/rss/items/21/release')).toHaveLength(1))
      await waitFor(() => expect(within(list).getByRole('listitem')).toHaveTextContent('Sent'))
    } finally {
      await i18next.changeLanguage('zh-Hant')
    }
  })

  it.each([
    ['zh-Hant', 'series_unbound', '仍然下載', /還沒綁定作品/],
    ['zh-Hant', 'feed_unprimed', '仍然下載', /還在等第一輪的決定/],
    ['en', 'series_unbound', 'Download anyway', /isn't bound to a title yet/],
    ['en', 'feed_unprimed', 'Download anyway', /still waiting on the first-round choice/],
  ] as const)('%s：放行不了（%s）時停用並說原因，按了不送', async (lang, blocked, name, why) => {
    const stub = render({
      'GET /api/rss/items': { body: [{ ...HELD, release_blocked: blocked }] },
    })
    await i18next.changeLanguage(lang)
    try {
      renderApp('/rss')
      const line = await recent()
      const button = within(line).getByRole('button', { name })

      expect(button).toHaveAttribute('aria-disabled', 'true')
      expect(button).toHaveAccessibleDescription(why)
      await userEvent.click(button)
      expect(sent(stub, 'POST', '/api/rss/items/21/release')).toHaveLength(0)
    } finally {
      await i18next.changeLanguage('zh-Hant')
    }
  })

  it('被拒時就地說原因', async () => {
    releasing({
      status: 409,
      body: { detail: { reason: 'item_not_excluded', detail: 'downloaded' } },
    })
    renderApp('/rss')
    const line = await recent()

    await userEvent.click(within(line).getByRole('button', { name: '仍然下載' }))

    expect(await within(line).findByRole('alert')).toHaveTextContent(/已經不是被排除的了/)
  })

  it('同一個 torrent 送過了：按下去那一列換成重複的理由', async () => {
    releasing({
      body: { ...HELD, status: 'duplicate', skip: { code: 'same_torrent', params: {} } },
    })
    renderApp('/rss')
    const line = await recent()

    await userEvent.click(within(line).getByRole('button', { name: '仍然下載' }))

    await waitFor(() => expect(line).toHaveTextContent('重複'))
    expect(within(line).queryByRole('button', { name: '仍然下載' })).not.toBeInTheDocument()
  })

  it('按下去送單被拒：還是排除，說出送單那一頭的原文', async () => {
    releasing({
      body: { ...HELD, error: 'route_unhealthy: the route is red' },
    })
    renderApp('/rss')
    const line = await recent()

    await userEvent.click(within(line).getByRole('button', { name: '仍然下載' }))

    await waitFor(() =>
      expect(line).toHaveTextContent(
        '仍然下載沒送出，這一筆還是排除： route_unhealthy: the route is red',
      ),
    )
    expect(line).toHaveTextContent('已排除')
  })

  it('送單被拒時這一筆還是排除，說出送單那一頭的原文', async () => {
    render({
      'GET /api/rss/items': {
        body: [{ ...HELD, error: 'source_unavailable: GET mikanani.me: connection refused' }],
      },
    })
    renderApp('/rss')
    const line = await recent()

    expect(line).toHaveTextContent('已排除')
    expect(line).toHaveTextContent(
      '仍然下載沒送出，這一筆還是排除： source_unavailable: GET mikanani.me: connection refused',
    )
  })
})
