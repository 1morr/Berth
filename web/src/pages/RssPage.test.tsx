import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Media } from '../api/media'
import type { Feed, FeedItem, OneshotItem, RssSeries } from '../api/rss'
import type { ManagedRoute } from '../api/routes'
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
    exclusions: [],
    primed_at: '2026-09-25T11:00:00Z',
    route_id: null,
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
    exclusions: [],
    confirmed: false,
    source: 'mikan',
    group: '喵萌奶茶屋&LoliHouse',
    latest_title: TITLE,
    latest_at: '2026-09-24T12:00:00Z',
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
    skip: null,
    size: null,
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
      'GET /api/rss/feeds': { body: [feed(), { ...ACGRIP, last_polled_at: null, items: 0 }] },
    })
    renderApp('/rss')
    const block = await firstRound()

    expect(within(block).getByText(/第一輪還沒輪到/)).toBeInTheDocument()
    expect(within(block).queryByRole('button', { name: '只追之後的' })).not.toBeInTheDocument()
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
    // Mikan 的 RSS Series 預設補舊集（票 12）：幾集要讀了才知道，鍵上不說總數。
    expect(within(row).getByRole('checkbox', { name: '同時補下載舊集' })).toBeChecked()
    await userEvent.click(within(row).getByRole('button', { name: '綁定、送出 2 集並補舊集' }))

    await waitFor(() => expect(sent(stub, 'PUT', '/api/rss/series/7/binding')).toHaveLength(1))
    const [[, init]] = sent(stub, 'PUT', '/api/rss/series/7/binding')
    expect(JSON.parse(String(init?.body))).toEqual({
      media: 'tv:262000',
      route: 3,
      backfill: true,
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
    expect(
      within(row).queryByRole('button', { name: '綁定、送出 2 集並補舊集' }),
    ).not.toBeInTheDocument()
    await userEvent.selectOptions(within(row).getByRole('combobox'), '3')
    await userEvent.click(within(row).getByRole('button', { name: '綁定、送出 2 集並補舊集' }))

    await waitFor(() => expect(sent(stub, 'PUT', '/api/rss/series/7/binding')).toHaveLength(1))
    const [[, init]] = sent(stub, 'PUT', '/api/rss/series/7/binding')
    expect(JSON.parse(String(init?.body))).toEqual({
      media: 'tv:262000',
      route: 3,
      backfill: true,
    })
  })

  it('補舊集取消勾選：鍵說回送出幾集，送出 `backfill: false`', async () => {
    const stub = render({
      'GET /api/rss/series': { body: [series()] },
      'GET /api/discover/search?q=Kimi%20ga%20Shinu%20made%20Koi%20wo%20Shitai': { body: FOUND },
      'GET /api/media/tv%3A262000': { body: KIMI },
      'PUT /api/rss/series/7/binding': { body: { ...series(), submitted: 2 } },
    })
    renderApp('/rss')
    const row = await screen.findByRole('article', { name: TITLE })
    await userEvent.click(within(row).getByRole('button', { name: '綁定' }))
    await userEvent.click(await within(row).findByRole('button', { name: /與妳相戀到生命盡頭/ }))

    const backfill = await within(row).findByRole('checkbox', { name: '同時補下載舊集' })
    await userEvent.click(backfill)
    // 說明跟著換成取消之後的後果。
    expect(backfill).toHaveAccessibleDescription(/更早的集數記成略過/)
    await userEvent.click(within(row).getByRole('button', { name: '綁定並送出 2 集' }))

    await waitFor(() => expect(sent(stub, 'PUT', '/api/rss/series/7/binding')).toHaveLength(1))
    const [[, init]] = sent(stub, 'PUT', '/api/rss/series/7/binding')
    expect(JSON.parse(String(init?.body))).toMatchObject({ backfill: false })
  })

  it('不是 Mikan 的 RSS Series 沒有補舊集那一格', async () => {
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

    expect(within(row).queryByRole('checkbox', { name: '同時補下載舊集' })).not.toBeInTheDocument()
    await waitFor(() => expect(sent(stub, 'PUT', '/api/rss/series/7/binding')).toHaveLength(1))
    const [[, init]] = sent(stub, 'PUT', '/api/rss/series/7/binding')
    expect(JSON.parse(String(init?.body))).toMatchObject({ backfill: false })
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

    expect(await screen.findByText(/這一版收 Mikan/)).toBeInTheDocument()
  })

  it('兩條以上的 Route：加 Feed 時選自動綁定送進哪一條，Feed 那一列說出它（票 21）', async () => {
    const route = (id: number, name: string, enabled = true) =>
      ({ route: { id, name, enabled }, jobs: 0, ledger_entries: 0, in_use: false }) as ManagedRoute
    const stub = render({
      'GET /api/routes': { body: [route(3, 'Anime'), route(4, 'TV'), route(5, 'Old', false)] },
      'GET /api/rss/feeds': { body: [feed({ route_id: 3 })] },
      'POST /api/rss/feeds': { status: 201, body: feed({ id: 2, route_id: 4 }) },
    })
    renderApp('/rss')

    const row = await screen.findByRole('article', { name: 'Mikan' })
    expect(await within(row).findByText('Anime')).toBeInTheDocument()
    const picker = await screen.findByLabelText('自動綁定送進')
    // 停用的那一條自動綁定本來就不看，不列。
    expect(within(picker).queryByRole('option', { name: 'Old' })).not.toBeInTheDocument()
    await userEvent.type(screen.getByLabelText(/RSS 網址/), FEED_URL)
    await userEvent.selectOptions(picker, 'TV')
    await userEvent.click(screen.getByRole('button', { name: '加入' }))

    await waitFor(() => expect(sent(stub, 'POST', '/api/rss/feeds')).toHaveLength(1))
    const [[, init]] = sent(stub, 'POST', '/api/rss/feeds')
    expect(JSON.parse(String(init?.body))).toEqual({ url: FEED_URL, name: '', route: 4 })
  })

  it('只有一條啟用中的 Route 時不問送進哪一條', async () => {
    render()
    renderApp('/rss')

    await screen.findByRole('article', { name: 'Mikan' })
    expect(screen.queryByLabelText('自動綁定送進')).not.toBeInTheDocument()
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

    const section = await screen.findByRole('region', { name: '排除條件' })
    expect(within(section).getByText('沒有排除條件。')).toBeInTheDocument()
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

    const section = await screen.findByRole('region', { name: '排除條件' })
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

const SINGLE_URL = 'https://mikanani.me/RSS/Bangumi?bangumiId=4009&subgroupid=370'
const KIMI_RELEASE = '[喵萌奶茶屋&LoliHouse] 与你相恋到生命尽头 / Kimi ga Shinu made Koi wo Shitai'
const KIMI_SEARCH = 'GET /api/discover/search?q=Kimi%20ga%20Shinu%20made%20Koi%20wo%20Shitai'

function oneshotItem(guid: string, overrides: Partial<OneshotItem> = {}): OneshotItem {
  return {
    guid,
    title: `${KIMI_RELEASE} - ${guid} [WebRip 1080p]`,
    link: `https://mikanani.me/Home/Episode/${guid}`,
    url: `https://mikanani.me/Download/20260924/${guid}.torrent`,
    info_hash: guid.padStart(40, '0'),
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

    // 搜尋框預填第一筆的作品名；唯一的 Route 預選好，清單照那部作品重讀一次。
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
    expect(jobs.map((body) => body.source.url)).toEqual([
      ONESHOT[3].url,
      ONESHOT[2].url,
      ONESHOT[1].url,
    ])
    expect(jobs[0]).toEqual({
      source: {
        url: ONESHOT[3].url,
        title: ONESHOT[3].title,
        info_hash: ONESHOT[3].info_hash,
        published_at: ONESHOT[3].published_at,
      },
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
