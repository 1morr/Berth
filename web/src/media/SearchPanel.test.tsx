import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18next from 'i18next'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { Job } from '../api/jobs'
import type { Media } from '../api/media'
import type { QueryPlan, SearchResults, SearchResult } from '../api/search'
import { HEALTHY, REQUEST_FAILURES, stubApi, type StubRoute } from '../test/fetch'
import { renderApp } from '../test/render'

afterEach(() => {
  vi.unstubAllGlobals()
})

const MEDIA_PATH = 'GET /api/media/tv%3A120089'
const QUERIES_PATH = 'GET /api/search/queries?media=tv%3A120089'
const SEARCH_PATH = 'GET /api/search?media=tv%3A120089'

function media(overrides: Partial<Media> = {}): Media {
  return {
    id: 'tv:120089',
    tmdb_id: 120089,
    kind: 'tv',
    title: 'SPY×FAMILY 間諜家家酒',
    title_en: 'SPY x FAMILY',
    title_original: 'SPY×FAMILY',
    year: 2022,
    first_air_date: '2022-04-09',
    overview: '',
    overview_en: '',
    poster_url: '',
    poster_url_en: '',
    runtime: null,
    folder_name: 'SPY x FAMILY (2022) [tmdbid-120089]',
    folder_frozen: false,
    tracked: false,
    default_route_id: null,
    fetched_at: '2026-09-09T12:00:00Z',
    problem: null,
    detail: '',
    routes: [
      { id: 1, name: 'TV', slug: 'tv', collection_type: 'tvshows' },
      { id: 2, name: 'Anime', slug: 'anime', collection_type: 'tvshows' },
    ],
    seasons: [],
    files: [],
    unmatched: [],
    versions: [],
    awaiting_review: 0,
    ...overrides,
  }
}

function row(overrides: Partial<SearchResult> = {}): SearchResult {
  return {
    title: '[ANi] SPY x FAMILY - 50 [1080P][Baha][WEB-DL][AAC AVC][CHT][MP4]',
    indexer: 'ACG.RIP',
    size: 524288000,
    seeders: 42,
    info_url: 'https://acg.rip/t/344604',
    source_id: 'source-acg-50',
    key: 'a'.repeat(40),
    tags: {
      source: 'WEB',
      resolution: '1080p',
      subs: ['CHT'],
      hardsub: false,
      group: 'ANi',
      version: '',
      edition: '',
    },
    season: 3,
    episode_start: 13,
    episode_end: 13,
    whole_season: false,
    strategy: 'explicit',
    published_at: null,
    verdict: 'fits',
    evidence: '',
    ...overrides,
  }
}

/**
 * 按下搜尋之前的那一份（`GET /api/search/queries`）：名字與季的 chip 照後端出廠預設開著
 * （英文名、原名、不指定季加最新一季）。`queries` 由測試自己給——前端不重算，照抄後端回的。
 */
function plan(overrides: Partial<QueryPlan> = {}): QueryPlan {
  return {
    queries: ['SPY x FAMILY', 'SPY×FAMILY', '間諜家家酒'],
    problem: null,
    batch: null,
    names: [
      { name: 'SPY x FAMILY', kinds: ['english'], on: true },
      { name: 'SPY×FAMILY', kinds: ['original'], on: true },
      { name: '間諜家家酒', kinds: ['chinese'], on: false },
      { name: '间谍过家家', kinds: ['simplified'], on: false },
      { name: 'Agent x Ailə', kinds: ['alias'], on: false },
      { name: 'Spy Familie', kinds: ['alias'], on: false },
    ],
    seasons: [
      { number: 1, on: false },
      { number: 2, on: false },
      { number: 3, on: true },
    ],
    any_season: true,
    limit: 10,
    ...overrides,
  }
}

/** 開了這幾個名字與季之後，預覽（與搜尋）帶的參數。順序與 `api/search.ts` 寫的一樣。 */
function chosen(names: string[], seasons: number[], anySeason = true): string {
  const params = new URLSearchParams({ media: 'tv:120089' })
  for (const name of names) params.append('name', name)
  for (const season of seasons) params.append('in_season', String(season))
  params.set('any_season', String(anySeason))
  return params.toString()
}

/** 後端的 `counts`：每一類在每一站的總數。替身照送來的列算，要「總數比送來的多」時自己給。 */
function countsOf(rows: readonly SearchResult[]): SearchResults['counts'] {
  const tally = new Map<string, SearchResults['counts'][number]>()
  for (const one of rows) {
    const id = `${one.verdict}/${one.indexer}`
    const before = tally.get(id)
    tally.set(id, { verdict: one.verdict, indexer: one.indexer, total: (before?.total ?? 0) + 1 })
  }
  return [...tally.values()]
}

/** 送單成功時後端回的那一筆。只有畫面讀得到的那幾格才有意義。 */
function job(): Job {
  return {
    hash: 'a'.repeat(40),
    name: '[ANi] SPY x FAMILY - 50 [1080P][Baha][WEB-DL][AAC AVC][CHT][MP4]',
    state: 'submitted',
    trigger: 'manual',
    error: '',
    media_id: 'tv:120089',
    media_title: 'SPY×FAMILY 間諜家家酒',
    media_title_en: 'SPY x FAMILY',
    route_id: 1,
    route_name: 'TV',
    user_name: 'skipper',
    save_path: '',
    content_path: '',
    total_size: 0,
    progress: 0,
    client_state: '',
    added_at: '2026-09-10T12:00:00Z',
    retryable: false,
    replannable: false,
    reimportable: false,
    plan_id: null,
    audits: 0,
    series: '',
    previous_client: '',
  }
}

function results(overrides: Partial<SearchResults> = {}): SearchResults {
  const rows = overrides.rows ?? [row()]
  return {
    rows,
    counts: countsOf(rows),
    returned: rows.length,
    merged: 0,
    attempts: [{ step: 'SPY x FAMILY', status: 'ok', detail: '1', error: '' }],
    problem: null,
    detail: '',
    batch: null,
    ...overrides,
  }
}

function render(
  routes: Record<string, StubRoute | (() => StubRoute | Promise<StubRoute>)> = {},
  role: 'admin' | 'user' = 'admin',
) {
  return stubApi({
    'GET /api/health': { body: HEALTHY },
    'GET /api/auth/me': { body: { name: 'skipper', role } },
    [MEDIA_PATH]: { body: media() },
    [QUERIES_PATH]: { body: plan() },
    // 同一頁 admin 才有的「RSS 訂閱」段（M3 票 19）。
    'GET /api/rss/series?media=tv%3A120089': { body: [] },
    // 「下載」段一進頁面就問這部作品的下載；沒替身會是 404，畫出一格 `RequestFailed`（M4 票 90）。
    'GET /api/jobs?media=tv%3A120089&filter=open&page=1': {
      body: {
        filter: 'open',
        page: 1,
        page_size: 50,
        total: 0,
        jobs: [],
        counts: { active: 0, attention: 0, imported: 0, all: 0, open: 0 },
      },
    },
    ...routes,
  })
}

/**
 * 讓 `/api/search` 那一支**永遠不回**，好看清楚「還在問」的樣子。
 *
 * 替身平常是同步回應的，所以按下去的下一刻結果就到了——而真實世界那裡有 35–85 秒。
 */
function holdSearch(base: ReturnType<typeof stubApi>) {
  const held = new Promise<Response>(() => {})
  vi.stubGlobal(
    'fetch',
    vi.fn<typeof fetch>((input, init) =>
      String(input).startsWith('/api/search?') ? held : base(input, init),
    ),
  )
}

/** 只問一個查詢時，代價與等待那一句（M4 票 84b）。 */
const COST_ONE = '會問 1 個查詢；索引站要現場去連每一個追蹤站，通常要幾秒到一分鐘。'

/** 這一頁的搜尋區塊。其餘區塊的測試在 `pages/MediaDetailPage.test.tsx`。 */
function panel() {
  return screen.getByRole('region', { name: '搜尋 torrent' })
}

/** 預覽列出的那幾個查詢（一個查詢一項，M4 票 84）。 */
async function asked(): Promise<(string | null)[]> {
  const list = await screen.findByRole('list', { name: '要送出去的查詢' })
  return within(list)
    .getAllByRole('listitem')
    .map((item) => item.textContent)
}

describe('搜尋 torrent 與結果表', () => {
  it('待命時先列出會送出去的關鍵字，而且一個索引站都還沒打', async () => {
    const stub = render()
    renderApp('/media/tv:120089')

    expect(await asked()).toEqual(['SPY x FAMILY', 'SPY×FAMILY', '間諜家家酒'])
    expect(screen.getByText(/通常要幾秒到一分鐘/)).toBeVisible()
    expect(stub.mock.calls.map(([input]) => String(input))).not.toContain(
      '/api/search?media=tv%3A120089',
    )
  })

  it('搜尋中先把要問的關鍵字鋪成纜繩，不是只有一顆變字的按鈕', async () => {
    // 一次搜尋要 35–85 秒；那段時間裡畫面上要有東西說得出「正在問什麼」。
    const base = render()
    holdSearch(base)
    renderApp('/media/tv:120089')
    await asked()

    await userEvent.click(screen.getByRole('button', { name: '搜尋' }))

    // 纜繩是一張有序清單；預覽那一張（`要送出去的查詢`）是另一張。
    const lines = within(within(panel()).getByRole('list', { name: '' })).getAllByRole('listitem')
    expect(lines.map((line) => line.textContent)).toEqual([
      '進行中SPY x FAMILY',
      '進行中SPY×FAMILY',
      '進行中間諜家家酒',
    ])
  })

  it('按下搜尋才問索引站，回來的每一列帶著大小、做種、來源與預估', async () => {
    render({ [SEARCH_PATH]: { body: results() } })
    renderApp('/media/tv:120089')

    await userEvent.click(await screen.findByRole('button', { name: '搜尋' }))

    const table = await within(panel()).findByRole('table')
    const cells = within(table).getAllByRole('cell')
    expect(within(cells[0]).getByText(/\[ANi\] SPY x FAMILY - 50/)).toBeVisible()
    // 桌機那四欄與窄版那一行講的是同一件事，所以同一個字串在 DOM 裡各有一份。
    expect(within(table).getAllByText('500 MB').length).toBeGreaterThan(0)
    expect(within(table).getAllByText('42').length).toBeGreaterThan(0)
    expect(within(table).getAllByRole('link', { name: 'ACG.RIP' })[0]).toHaveAttribute(
      'href',
      'https://acg.rip/t/344604',
    )
    expect(within(table).getAllByText('S03E13').length).toBeGreaterThan(0)
  })

  // M4 票 90：原本一律說「Berth 自己的 API 沒有回應」——500 與 401 也是。
  it.each(REQUEST_FAILURES)('搜尋沒有跑完（%s）時說出對的原因', async (_, failure, expected) => {
    render({ [SEARCH_PATH]: failure })
    renderApp('/media/tv:120089')

    await userEvent.click(await screen.findByRole('button', { name: '搜尋' }))

    const alert = await within(panel()).findByRole('alert')
    expect(alert).toHaveTextContent(/搜尋沒有跑完。/)
    expect(alert).toHaveTextContent(expected)
    expect(alert).not.toHaveTextContent(/自己的 API/)
  })

  describe('發佈欄（M3 票 14）', () => {
    // 替身的「現在」固定住，相對時間才是一個說得準的字串。
    beforeEach(() => {
      vi.useFakeTimers({ toFake: ['Date'], now: new Date('2026-09-25T12:00:00Z') })
    })
    afterEach(() => {
      vi.useRealTimers()
    })

    it('說相對時間，完整日期在 title；索引站沒報的是 —', async () => {
      render({
        [SEARCH_PATH]: {
          body: results({
            rows: [
              row({ published_at: '2026-09-04T13:01:00Z' }),
              row({ key: 'b'.repeat(40), title: '[Other] SPY x FAMILY - 51', published_at: null }),
            ],
          }),
        },
      })
      renderApp('/media/tv:120089')

      await userEvent.click(await screen.findByRole('button', { name: '搜尋' }))

      const table = await within(panel()).findByRole('table')
      expect(within(table).getByRole('columnheader', { name: '發佈' })).toBeInTheDocument()
      const [known] = within(table).getAllByText('3 週前')
      expect(known.closest('time')).toHaveAttribute('dateTime', '2026-09-04T13:01:00Z')
      expect(known.closest('time')).toHaveAttribute(
        'title',
        new Date('2026-09-04T13:01:00Z').toLocaleString('zh-Hant'),
      )
      const rows = within(table).getAllByRole('row')
      expect(within(rows[2]).getByText('—')).toBeInTheDocument()
    })

    it('英文介面同一欄叫 Published', async () => {
      render({
        [SEARCH_PATH]: { body: results({ rows: [row({ published_at: '2026-09-04T13:01:00Z' })] }) },
      })
      await i18next.changeLanguage('en')
      try {
        renderApp('/media/tv:120089')

        await userEvent.click(await screen.findByRole('button', { name: 'Search' }))

        const table = await screen.findByRole('table')
        expect(within(table).getByRole('columnheader', { name: 'Published' })).toBeInTheDocument()
        expect(within(table).getAllByText('3 weeks ago').length).toBeGreaterThan(0)
      } finally {
        await i18next.changeLanguage('zh-Hant')
      }
    })
  })

  it('Tags 逐格畫，內容與之後檔名裡的那一串一致（brief §6.8）', async () => {
    render({ [SEARCH_PATH]: { body: results() } })
    renderApp('/media/tv:120089')

    await userEvent.click(await screen.findByRole('button', { name: '搜尋' }))

    const table = await within(panel()).findByRole('table')
    for (const token of ['WEB', '1080p', 'CHT', 'ANi']) {
      expect(within(table).getByText(token)).toBeVisible()
    }
  })

  it('季包說「全季」，判斷不出來的就說判斷不出來——不猜一個數字', async () => {
    render({
      [SEARCH_PATH]: {
        body: results({
          rows: [
            row({ key: 'pack', whole_season: true, episode_start: 1, episode_end: 13 }),
            row({
              key: 'unknown',
              title: 'Some Unrelated Thing 2160p',
              season: null,
              episode_start: null,
              episode_end: null,
              strategy: null,
            }),
          ],
        }),
      },
    })
    renderApp('/media/tv:120089')

    await userEvent.click(await screen.findByRole('button', { name: '搜尋' }))

    const table = await within(panel()).findByRole('table')
    expect(within(table).getAllByText('全季')[0]).toBeVisible()
    expect(within(table).getAllByText('S03')[0]).toBeVisible()
    expect(within(table).getAllByText('判斷不出來')[0]).toBeVisible()
  })

  it('一個關鍵字問不動時另外幾個照樣有結果，而畫面說得出是哪一個垮了', async () => {
    render({
      [SEARCH_PATH]: {
        body: results({
          attempts: [
            { step: 'SPY x FAMILY', status: 'ok', detail: '1', error: '' },
            {
              step: 'SPY×FAMILY',
              status: 'failed',
              detail: '',
              error: 'GET /api/v1/search: ReadTimeout',
              failure: 'unreachable',
            },
          ],
        }),
      },
    })
    renderApp('/media/tv:120089')

    await userEvent.click(await screen.findByRole('button', { name: '搜尋' }))

    // 一句人話說哪一個垮了；原文收進技術細節（M4 票 21）。
    expect(await screen.findByText(/^連不到 索引站/)).toBeVisible()
    expect(screen.getByText('GET /api/v1/search: ReadTimeout')).not.toBeVisible()
    // 垮掉的那一條不影響結果表。
    expect(within(panel()).getByRole('table')).toBeVisible()
  })

  it('搜尋結束之後有回應的纜繩收成一行，展開才逐條列筆數（M1.5 票 08：全綠的纜繩曾佔掉 311px）', async () => {
    render({
      [SEARCH_PATH]: {
        body: results({
          attempts: [
            { step: 'SPY x FAMILY', status: 'ok', detail: '12', error: '' },
            { step: 'SPY×FAMILY', status: 'ok', detail: '3', error: '' },
            { step: '間諜家家酒', status: 'ok', detail: '0', error: '' },
          ],
        }),
      },
    })
    renderApp('/media/tv:120089')

    await userEvent.click(await screen.findByRole('button', { name: '搜尋' }))

    const summary = await within(panel()).findByText('3 個關鍵字都有回應')
    expect(summary).toBeVisible()
    // 纜繩摘要的 `<details>` 沒展開時仍在 DOM 裡，看不見的是它；全部正常時整塊沒有任何一塊信號色。
    // 名字 chip 上也有同一串字；纜繩的那一條在清單項裡。
    expect(within(panel()).getByText('SPY×FAMILY', { selector: 'li *' })).not.toBeVisible()
    for (const done of within(panel()).getAllByText('已完成')) expect(done).not.toBeVisible()

    await userEvent.click(summary)

    expect(within(panel()).getByText('SPY×FAMILY', { selector: 'li *' })).toBeVisible()
    expect(within(panel()).getByText('12')).toBeVisible()
  })

  it('垮掉的纜繩不收：它與原文畫在收起的那一行上面', async () => {
    render({
      [SEARCH_PATH]: {
        body: results({
          attempts: [
            { step: 'SPY x FAMILY', status: 'ok', detail: '1', error: '' },
            { step: '間諜家家酒', status: 'ok', detail: '2', error: '' },
            {
              step: 'SPY×FAMILY',
              status: 'failed',
              detail: '',
              error: 'GET /api/v1/search: ReadTimeout',
              failure: 'unreachable',
            },
          ],
        }),
      },
    })
    renderApp('/media/tv:120089')

    await userEvent.click(await screen.findByRole('button', { name: '搜尋' }))

    const failed = await within(panel()).findByText(/^連不到 索引站/)
    const summary = within(panel()).getByText('其餘 2 個關鍵字有回應')
    expect(failed).toBeVisible()
    expect(summary).toBeVisible()
    // 垮掉的那一條在摘要上面（需要你的事浮到摘要層）。
    expect(failed.compareDocumentPosition(summary) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(within(panel()).getByText('SPY x FAMILY', { selector: 'li *' })).not.toBeVisible()
  })

  it('沒有接索引站時說得出兩條路：接 Prowlarr，或這一頁的 RSS 訂閱（票 08、M4 票 61）', async () => {
    render({
      [SEARCH_PATH]: {
        body: results({ rows: [], attempts: [], problem: 'not_configured' }),
      },
    })
    renderApp('/media/tv:120089')

    await userEvent.click(await screen.findByRole('button', { name: '搜尋' }))

    expect(await screen.findByText(/Berth 沒有接索引站，所以這裡搜不到東西/)).toBeVisible()
    // 是選擇不是故障：中性色塊，不是「阻擋」。
    expect(within(panel()).getByText('沒有接索引站')).toBeVisible()
    expect(within(panel()).queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: '前往設定：Prowlarr' })).toHaveAttribute(
      'href',
      '/settings/indexers',
    )
    expect(screen.getByRole('link', { name: '到 RSS 訂閱' })).toHaveAttribute(
      'href',
      '#media-subscribe',
    )
    expect(document.getElementById('media-subscribe')).toHaveAccessibleName('RSS 訂閱')
    expect(within(panel()).queryByRole('table')).not.toBeInTheDocument()
  })

  it('沒有接索引站的說明在 en 也是兩條路', async () => {
    render({
      [SEARCH_PATH]: {
        body: results({ rows: [], attempts: [], problem: 'not_configured' }),
      },
    })
    await i18next.changeLanguage('en')
    try {
      renderApp('/media/tv:120089')

      await userEvent.click(await screen.findByRole('button', { name: 'Search' }))

      expect(await screen.findByText(/Berth has no indexer connected/)).toBeVisible()
      expect(screen.getByRole('link', { name: 'Open Prowlarr settings' })).toBeVisible()
      expect(screen.getByRole('link', { name: 'Go to RSS subscriptions' })).toBeVisible()
    } finally {
      await i18next.changeLanguage('zh-Hant')
    }
  })

  it('沒有接索引站時按下去之前就說，按了之後同一件事只說一次（票 13）', async () => {
    render({
      [QUERIES_PATH]: { body: plan({ queries: ['SPY x FAMILY'], problem: 'not_configured' }) },
      [SEARCH_PATH]: {
        body: results({ rows: [], attempts: [], problem: 'not_configured' }),
      },
    })
    renderApp('/media/tv:120089')

    // 還沒按：一個索引站都沒打，畫面已經說得出下一步。
    expect(await screen.findByText(/Berth 沒有接索引站/)).toBeVisible()
    expect(within(panel()).getByRole('link', { name: '前往設定：Prowlarr' })).toBeVisible()

    await userEvent.click(screen.getByRole('button', { name: '搜尋' }))

    expect(await screen.findByText('找到 0 筆，0 個關鍵字沒問到。')).toBeInTheDocument()
    expect(screen.getAllByText(/Berth 沒有接索引站/)).toHaveLength(1)
  })

  it('一般使用者看到的是「請管理員…」而不是兩條進不去的連結', async () => {
    render(
      {
        [SEARCH_PATH]: {
          body: results({ rows: [], attempts: [], problem: 'not_configured' }),
        },
      },
      'user',
    )
    renderApp('/media/tv:120089')

    await userEvent.click(await screen.findByRole('button', { name: '搜尋' }))

    expect(
      await screen.findByText('請管理員接上 Prowlarr，或替這部作品加一個 RSS 訂閱。'),
    ).toBeVisible()
    expect(screen.queryByRole('link', { name: '前往設定：Prowlarr' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: '到 RSS 訂閱' })).not.toBeInTheDocument()
  })

  it('連不上索引站時說人話、給「去哪裡改位址」，原文收進技術細節（M4 票 61，審計 P2-7）', async () => {
    render({
      [SEARCH_PATH]: {
        body: results({
          rows: [],
          attempts: [],
          problem: 'unreachable',
          detail: 'GET /api/v1/indexer: host does not resolve',
        }),
      },
    })
    renderApp('/media/tv:120089')

    await userEvent.click(await screen.findByRole('button', { name: '搜尋' }))

    expect(await screen.findByText(/連不上索引站/)).toBeVisible()
    const raw = screen.getByText('GET /api/v1/indexer: host does not resolve')
    expect(raw).not.toBeVisible()
    await userEvent.click(within(panel()).getByText('技術細節'))
    expect(raw).toBeVisible()
    expect(screen.getByRole('link', { name: '前往設定：Prowlarr' })).toBeVisible()
  })

  it('連不上索引站的分層在 en 也一樣', async () => {
    render({
      [SEARCH_PATH]: {
        body: results({
          rows: [],
          attempts: [],
          problem: 'unreachable',
          detail: 'GET /api/v1/indexer: host does not resolve',
        }),
      },
    })
    await i18next.changeLanguage('en')
    try {
      renderApp('/media/tv:120089')

      await userEvent.click(await screen.findByRole('button', { name: 'Search' }))

      expect(await screen.findByText(/Cannot reach the indexer/)).toBeVisible()
      expect(screen.getByText('GET /api/v1/indexer: host does not resolve')).not.toBeVisible()
      expect(screen.getByText('Technical details')).toBeVisible()
    } finally {
      await i18next.changeLanguage('zh-Hant')
    }
  })

  it('搜尋問的是全部的站：沒有「這次沒問」，也沒有「等請求預算」（M4 票 107）', async () => {
    render({ [SEARCH_PATH]: { body: results() } })
    renderApp('/media/tv:120089')

    await userEvent.click(await screen.findByRole('button', { name: '搜尋' }))

    expect(await within(panel()).findByRole('table')).toBeInTheDocument()
    expect(within(panel()).queryByText('這次沒問')).not.toBeInTheDocument()
    expect(within(panel()).queryByText(/請求預算/)).not.toBeInTheDocument()
  })

  it('搜到但一筆都沒有不是錯誤', async () => {
    render({ [SEARCH_PATH]: { body: results({ rows: [] }) } })
    renderApp('/media/tv:120089')

    await userEvent.click(await screen.findByRole('button', { name: '搜尋' }))

    expect(await screen.findByText(/沒有東西/)).toBeVisible()
  })

  describe('每一筆歸到一類，用篩選按鈕看（M4 票 83）', () => {
    const YEAR = row({
      key: 'year',
      title: 'SPY x FAMILY 1998 VHS',
      verdict: 'year',
      evidence: '1998',
    })
    const POPULAR = row({
      key: 'popular',
      title: 'Spider-Man: Brand New Day 2026.1080p',
      indexer: 'The Pirate Bay',
      verdict: 'unrelated',
    })
    const SPINOFF = row({
      key: 'spinoff',
      title: 'SPY.x.FAMILY.CODE.White.S01E01',
      indexer: 'The Pirate Bay',
      verdict: 'partial_title',
      evidence: 'SPY x FAMILY CODE White',
    })

    async function searched(body: SearchResults) {
      render({ [SEARCH_PATH]: { body } })
      renderApp('/media/tv:120089')
      await userEvent.click(await screen.findByRole('button', { name: '搜尋' }))
      return within(await within(panel()).findByRole('group', { name: '要列出哪幾類' }))
    }

    it('預設只開「符合」，其他類按了才一起列出，再按一次收回', async () => {
      const buttons = await searched(results({ rows: [row(), YEAR, POPULAR] }))

      const fits = buttons.getByRole('button', { name: '符合 1' })
      expect(fits).toHaveAttribute('aria-pressed', 'true')
      expect(buttons.getByRole('button', { name: '年份不符 1' })).toHaveAttribute(
        'aria-pressed',
        'false',
      )
      expect(screen.queryByText(YEAR.title)).toBeNull()

      await userEvent.click(buttons.getByRole('button', { name: '年份不符 1' }))
      expect(screen.getByText(YEAR.title)).toBeVisible()
      expect(screen.getByText(row().title)).toBeVisible()

      await userEvent.click(buttons.getByRole('button', { name: '年份不符 1' }))
      expect(screen.queryByText(YEAR.title)).toBeNull()
    })

    it('是 0 的類沒有按鈕，「符合」例外', async () => {
      const buttons = await searched(results({ rows: [POPULAR] }))

      expect(buttons.getAllByRole('button').map((button) => button.textContent)).toEqual([
        '符合 0',
        '名字對不上 1',
      ])
      expect(screen.getByText('沒有符合的結果；其他幾類有 1 筆，按上面的按鈕看。')).toBeVisible()
    })

    it('不是「符合」的列說出它是哪一類、為什麼；符合的列不標', async () => {
      const buttons = await searched(results({ rows: [row(), YEAR, SPINOFF] }))
      await userEvent.click(buttons.getByRole('button', { name: '年份不符 1' }))
      await userEvent.click(buttons.getByRole('button', { name: '只對上部分名字 1' }))

      const table = within(within(panel()).getByRole('table'))
      expect(table.getByText('發佈名寫 1998 年，不在這部作品的播出期間。')).toBeVisible()
      expect(
        table.getByText(
          '發佈名的片名是「SPY x FAMILY CODE White」，比這部作品的名字多一段：可能是衍生作品，也可能只是多寫了副標。',
        ),
      ).toBeVisible()
      expect(table.queryByText('符合')).toBeNull()
      // 依類別分組：「符合」永遠在最上面，其餘照按鈕的順序。
      const titles = table.getAllByText(/SPY/, { selector: 'p.value' })
      expect(titles.map((title) => title.textContent)).toEqual([
        row().title,
        YEAR.title,
        SPINOFF.title,
      ])
    })

    it('電影的年份那一句說出這部作品是哪一年', async () => {
      render({
        [MEDIA_PATH]: { body: media({ kind: 'movie', year: 1922 }) },
        [SEARCH_PATH]: {
          body: results({
            rows: [
              row({ key: 'remake', title: 'Nosferatu 2024', verdict: 'year', evidence: '2024' }),
            ],
          }),
        },
      })
      renderApp('/media/tv:120089')
      await userEvent.click(await screen.findByRole('button', { name: '搜尋' }))
      await userEvent.click(await screen.findByRole('button', { name: '年份不符 1' }))

      expect(screen.getByText('發佈名寫 2024 年，這部作品是 1922 年。')).toBeVisible()
    })

    it('「不是電影」那一句帶出觸發的那一段集數記號', async () => {
      render({
        [MEDIA_PATH]: { body: media({ kind: 'movie', year: 1922 }) },
        [SEARCH_PATH]: {
          body: results({
            rows: [
              row({
                key: 'laika',
                title: '[SubsPlease] Tsuki to Laika to Nosferatu - 05 (1080p)',
                verdict: 'not_movie',
                evidence: '- 05',
              }),
            ],
          }),
        },
      })
      renderApp('/media/tv:120089')
      await userEvent.click(await screen.findByRole('button', { name: '搜尋' }))
      await userEvent.click(await screen.findByRole('button', { name: '不是電影 1' }))

      expect(
        screen.getByText('發佈名有集數記號「- 05」，這部是電影；多半是劇集，或同名的動畫。'),
      ).toBeVisible()
    })

    it('英文介面：按鈕與理由', async () => {
      await i18next.changeLanguage('en')
      try {
        render({ [SEARCH_PATH]: { body: results({ rows: [row(), YEAR, SPINOFF] }) } })
        renderApp('/media/tv:120089')
        await userEvent.click(await screen.findByRole('button', { name: 'Search' }))
        const buttons = within(await screen.findByRole('group', { name: 'Kinds to list' }))
        await userEvent.click(buttons.getByRole('button', { name: 'Wrong year 1' }))
        await userEvent.click(buttons.getByRole('button', { name: 'Partial title 1' }))

        expect(buttons.getByRole('button', { name: 'Matches 1' })).toBeVisible()
        expect(
          screen.getByText('The release says 1998, outside the years this show aired.'),
        ).toBeVisible()
        expect(
          screen.getByText(
            'The release is titled “SPY x FAMILY CODE White”, longer than this title’s name: possibly a spin-off, or just a subtitle written out.',
          ),
        ).toBeVisible()
      } finally {
        await i18next.changeLanguage('zh-Hant')
      }
    })

    it('只看某個站：表格與按鈕上的數字都只算那一站', async () => {
      const buttons = await searched(
        results({
          rows: [
            row(),
            row({ key: 'tpb', title: 'SPY.x.FAMILY.S03E13.1080p', indexer: 'The Pirate Bay' }),
            POPULAR,
          ],
        }),
      )
      expect(buttons.getByRole('button', { name: '符合 2' })).toBeVisible()

      await userEvent.selectOptions(screen.getByLabelText('站'), 'The Pirate Bay')

      expect(buttons.getByRole('button', { name: '符合 1' })).toBeVisible()
      expect(buttons.getByRole('button', { name: '名字對不上 1' })).toBeVisible()
      expect(screen.getByText('SPY.x.FAMILY.S03E13.1080p')).toBeVisible()
      expect(screen.queryByText(row().title)).toBeNull()

      await userEvent.selectOptions(screen.getByLabelText('站'), 'ACG.RIP')
      await userEvent.click(buttons.getByRole('button', { name: '符合 1' }))
      expect(screen.getByText('沒有選任何一類。')).toBeVisible()
    })

    it('一類的總數比送來的多時，那一組底下說清楚只列了幾筆', async () => {
      await searched(
        results({
          rows: [row()],
          counts: [{ verdict: 'fits', indexer: 'ACG.RIP', total: 262 }],
          returned: 362,
          merged: 100,
        }),
      )

      expect(
        screen.getByText('這一類共 262 筆，這裡列出 1 筆：每站輪流取，站內做種多的先。'),
      ).toBeVisible()
      expect(screen.getByText('結果表 262 筆')).toBeVisible()
    })

    it('筆數那一行說回了幾筆與重複的；各類的數字在按鈕上', async () => {
      await searched(results({ rows: [row(), YEAR, POPULAR], returned: 5, merged: 2 }))

      expect(screen.getByText('索引站回了 5 筆。其中 2 筆重複、已合併。')).toBeVisible()
    })

    it('新的一輪搜尋回到只開「符合」', async () => {
      const buttons = await searched(results({ rows: [row(), YEAR] }))
      await userEvent.click(buttons.getByRole('button', { name: '年份不符 1' }))
      expect(screen.getByText(YEAR.title)).toBeVisible()

      await userEvent.click(screen.getByRole('button', { name: '搜尋' }))

      await waitFor(() => expect(screen.queryByText(YEAR.title)).toBeNull())
    })
  })

  describe('自己打關鍵字：分對得上與對不上（M4 票 83b）', () => {
    const MATCH = row({
      key: 'match',
      title: 'Spider-Man: Brand New Day 2026.1080p',
      indexer: 'The Pirate Bay',
      verdict: 'typed_match',
    })
    const MISS = row({
      key: 'miss',
      title: 'Avira Antivirus Pro 2026 Multi',
      indexer: 'The Pirate Bay',
      verdict: 'typed_miss',
    })
    const ELSEWHERE = row({ key: 'elsewhere', verdict: 'typed_match' })

    async function typedSearch(
      body: SearchResults,
      labels = { keyword: '關鍵字', search: '搜尋' },
    ) {
      render({ [`${SEARCH_PATH}&q=Spider-Man`]: { body } })
      renderApp('/media/tv:120089')
      await userEvent.type(await screen.findByLabelText(labels.keyword), 'Spider-Man')
      await userEvent.click(screen.getByRole('button', { name: labels.search }))
    }

    it('只有兩顆按鈕，預設只開「對得上」；對得上的列不標', async () => {
      await typedSearch(results({ rows: [MATCH, MISS] }))

      const buttons = within(await within(panel()).findByRole('group', { name: '要列出哪幾類' }))
      expect(buttons.getAllByRole('button').map((button) => button.textContent)).toEqual([
        '對得上 1',
        '對不上 1',
      ])
      expect(buttons.getByRole('button', { name: '對得上 1' })).toHaveAttribute(
        'aria-pressed',
        'true',
      )
      expect(screen.getByText(MATCH.title)).toBeVisible()
      expect(screen.queryByText(MISS.title)).toBeNull()
      expect(screen.queryByText('對得上', { selector: 'span' })).toBeNull()
      expect(screen.getByText('結果表 1 筆')).toBeVisible()
    })

    it('按了「對不上」才列出，那一句說出打的字', async () => {
      await typedSearch(results({ rows: [MATCH, MISS] }))
      const buttons = within(await within(panel()).findByRole('group', { name: '要列出哪幾類' }))

      await userEvent.click(buttons.getByRole('button', { name: '對不上 1' }))

      const table = within(within(panel()).getByRole('table'))
      expect(table.getByText(MISS.title)).toBeVisible()
      expect(table.getByText('發佈名裡沒有「Spider-Man」，也沒有這部作品的名字。')).toBeVisible()
    })

    it('對得上是 0、對不上有東西時，指向按鈕', async () => {
      await typedSearch(results({ rows: [MISS] }))

      const buttons = within(await within(panel()).findByRole('group', { name: '要列出哪幾類' }))
      expect(buttons.getAllByRole('button').map((button) => button.textContent)).toEqual([
        '對得上 0',
        '對不上 1',
      ])
      expect(screen.getByText('沒有對得上的結果；對不上的有 1 筆，按上面的按鈕看。')).toBeVisible()
    })

    it('只看某個站時按鈕的數字與表格跟著變', async () => {
      await typedSearch(results({ rows: [MATCH, MISS, ELSEWHERE] }))
      const buttons = within(await within(panel()).findByRole('group', { name: '要列出哪幾類' }))
      expect(buttons.getByRole('button', { name: '對得上 2' })).toBeVisible()

      await userEvent.selectOptions(screen.getByLabelText('站'), 'The Pirate Bay')

      expect(buttons.getByRole('button', { name: '對得上 1' })).toBeVisible()
      expect(screen.queryByText(ELSEWHERE.title)).toBeNull()
      expect(screen.getByText(MATCH.title)).toBeVisible()
    })

    it('英文介面', async () => {
      await i18next.changeLanguage('en')
      try {
        await typedSearch(results({ rows: [MISS] }), { keyword: 'Keyword', search: 'Search' })

        const region = await screen.findByRole('region', { name: 'Search torrents' })
        const buttons = within(await within(region).findByRole('group', { name: 'Kinds to list' }))
        expect(
          screen.getByText('Nothing matches. “No match” holds 1 result; use the buttons above.'),
        ).toBeVisible()
        await userEvent.click(buttons.getByRole('button', { name: 'No match 1' }))
        expect(
          screen.getByText(
            'The release contains neither “Spider-Man” nor any of this title’s names.',
          ),
        ).toBeVisible()
      } finally {
        await i18next.changeLanguage('zh-Hant')
      }
    })
  })

  describe('搜尋前選名字與季（M4 票 84）', () => {
    it('名字與季都是 chip，照後端說的預設開著；名字帶種類，別名收在展開區', async () => {
      render()
      renderApp('/media/tv:120089')
      await screen.findByRole('region', { name: '搜尋 torrent' })

      const names = await within(panel()).findByRole('group', { name: '要問的名字' })
      expect(within(names).getByRole('button', { name: 'SPY x FAMILY 英文名' })).toHaveAttribute(
        'aria-pressed',
        'true',
      )
      expect(within(names).getByRole('button', { name: 'SPY×FAMILY 原名' })).toHaveAttribute(
        'aria-pressed',
        'true',
      )
      expect(within(names).getByRole('button', { name: '間諜家家酒 中文名' })).toHaveAttribute(
        'aria-pressed',
        'false',
      )
      expect(within(names).getByRole('button', { name: '间谍过家家 簡體中文名' })).toHaveAttribute(
        'aria-pressed',
        'false',
      )
      // 別名三十幾個，不和四種名字擠在一排：收起來，摘要說有幾個。
      expect(within(panel()).getByText('其他別名 2 個')).toBeVisible()
      expect(within(panel()).getByRole('button', { name: 'Agent x Ailə 別名' })).not.toBeVisible()

      const seasons = within(panel()).getByRole('group', { name: '要問的季' })
      expect(
        within(seasons)
          .getAllByRole('button')
          .map((chip) => [chip.textContent, chip.getAttribute('aria-pressed')]),
      ).toEqual([
        ['不指定季', 'true'],
        ['S01', 'false'],
        ['S02', 'false'],
        ['S03', 'true'],
      ])
    })

    it('開了中文名：記住這一種（每一部作品都開），預覽換成後端照新的選擇算的那一份', async () => {
      const remembered: unknown[] = []
      const stub = render({
        'PUT /api/search/names': () => ({
          body: { kinds: { english: true, original: true, chinese: true, simplified: false } },
        }),
        [`GET /api/search/queries?${chosen(['SPY x FAMILY', 'SPY×FAMILY', '間諜家家酒'], [3])}`]: {
          body: plan({ queries: ['SPY x FAMILY', '間諜家家酒 第3季'] }),
        },
      })
      renderApp('/media/tv:120089')
      await screen.findByRole('region', { name: '搜尋 torrent' })

      await userEvent.click(
        await within(panel()).findByRole('button', { name: '間諜家家酒 中文名' }),
      )

      await waitFor(async () => expect(await asked()).toEqual(['SPY x FAMILY', '間諜家家酒 第3季']))
      expect(within(panel()).getByRole('button', { name: '間諜家家酒 中文名' })).toHaveAttribute(
        'aria-pressed',
        'true',
      )
      for (const [input, init] of stub.mock.calls) {
        if (String(input) === '/api/search/names') remembered.push(JSON.parse(String(init?.body)))
      }
      expect(remembered).toEqual([{ kinds: { chinese: true } }])
    })

    it('別名開了不記住；季也不記住', async () => {
      const both = ['SPY x FAMILY', 'SPY×FAMILY', 'Agent x Ailə']
      const stub = render({
        [`GET /api/search/queries?${chosen(both, [3])}`]: { body: plan() },
        [`GET /api/search/queries?${chosen(both, [1, 3])}`]: { body: plan() },
      })
      renderApp('/media/tv:120089')
      await screen.findByRole('region', { name: '搜尋 torrent' })

      await userEvent.click(await within(panel()).findByText('其他別名 2 個'))
      await userEvent.click(within(panel()).getByRole('button', { name: 'Agent x Ailə 別名' }))
      await userEvent.click(within(panel()).getByRole('button', { name: 'S01' }))

      expect(within(panel()).getByText('其他別名 2 個，開了 1 個')).toBeVisible()
      const methods = stub.mock.calls.map(([, init]) => init?.method ?? 'GET')
      expect(methods).not.toContain('PUT')
    })

    it('超過上限時搜尋鍵停用並說原因，按了也不會問', async () => {
      const over = plan({ queries: Array.from({ length: 12 }, (_, i) => `SPY x FAMILY ${i}`) })
      const stub = render({ [QUERIES_PATH]: { body: over } })
      renderApp('/media/tv:120089')
      await screen.findByRole('region', { name: '搜尋 torrent' })

      const submit = await within(panel()).findByRole('button', { name: '搜尋' })
      await waitFor(() => expect(submit).toBeDisabled())
      expect(
        within(panel()).getByText('開了 12 個查詢，一次最多 10 個：關掉幾個名字或季。'),
      ).toBeVisible()
      expect(submit).toHaveAccessibleDescription(
        '開了 12 個查詢，一次最多 10 個：關掉幾個名字或季。',
      )
      // 不能搜時整句換成原因：等多久那半句不出現（M4 票 84b）。
      expect(within(panel()).queryByText(/幾秒到一分鐘/)).toBeNull()
      await userEvent.click(submit)
      expect(stub.mock.calls.map(([input]) => String(input))).not.toContain(
        '/api/search?media=tv%3A120089',
      )
    })

    it('一個名字都沒開時也停用，但自己打了關鍵字就照樣能搜', async () => {
      const none = plan({
        queries: [],
        names: plan().names.map((chip) => ({ ...chip, on: false })),
      })
      render({ [QUERIES_PATH]: { body: none } })
      renderApp('/media/tv:120089')
      await screen.findByRole('region', { name: '搜尋 torrent' })

      const submit = await within(panel()).findByRole('button', { name: '搜尋' })
      await waitFor(() => expect(submit).toBeDisabled())
      expect(within(panel()).getByText('至少開一個名字，或自己打一個關鍵字。')).toBeVisible()
      expect(submit).toHaveAccessibleDescription('至少開一個名字，或自己打一個關鍵字。')
      expect(within(panel()).queryByText(/幾秒到一分鐘/)).toBeNull()
      // 原因緊接在停用的鍵底下、名字 chip 之前（M4 票 132）：390 寬時 chip 與清單把它推出第一屏。
      const reason = within(panel()).getByText('至少開一個名字，或自己打一個關鍵字。')
      const names = within(panel()).getByRole('group', { name: '要問的名字' })
      expect(submit.compareDocumentPosition(reason) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
      expect(reason.compareDocumentPosition(names) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()

      await userEvent.type(within(panel()).getByLabelText('關鍵字'), 'Spy Family BDRip')

      expect(submit).toBeEnabled()
      expect(within(panel()).getByText(COST_ONE)).toBeVisible()
    })

    it('打了關鍵字時名字與季的 chip 停用並說為什麼：按了也不影響要問的那一個（M4 票 132）', async () => {
      render()
      renderApp('/media/tv:120089')
      await screen.findByRole('region', { name: '搜尋 torrent' })
      const names = await within(panel()).findByRole('group', { name: '要問的名字' })

      await userEvent.type(within(panel()).getByLabelText('關鍵字'), 'Spy Family BDRip')

      const hint = '打了關鍵字時只問那一個；清掉它，名字與季才用得上。'
      expect(within(panel()).getByText(hint)).toBeVisible()
      // 停用的 chip 不在 Tab 順序上：說明在它們之前，逐行讀的時候先讀到。
      expect(
        within(panel()).getByText(hint).compareDocumentPosition(names) &
          Node.DOCUMENT_POSITION_FOLLOWING,
      ).toBeTruthy()
      for (const chip of [
        ...within(names).getAllByRole('button'),
        ...within(within(panel()).getByRole('group', { name: '要問的季' })).getAllByRole('button'),
      ]) {
        expect(chip).toBeDisabled()
      }

      await userEvent.clear(within(panel()).getByLabelText('關鍵字'))

      expect(within(names).getByRole('button', { name: 'SPY x FAMILY 英文名' })).toBeEnabled()
      expect(within(panel()).queryByText(hint)).toBeNull()
    })

    it('快照還沒讀到時不畫空的 chip，搜尋鍵照舊按得下去（由後端說 no_query）', async () => {
      render({ [QUERIES_PATH]: { body: plan({ queries: [], names: [], seasons: [] }) } })
      renderApp('/media/tv:120089')
      await screen.findByRole('region', { name: '搜尋 torrent' })

      const submit = await within(panel()).findByRole('button', { name: '搜尋' })
      expect(within(panel()).queryByRole('group', { name: '要問的名字' })).toBeNull()
      expect(submit).toBeEnabled()
      expect(within(panel()).queryByText('至少開一個名字，或自己打一個關鍵字。')).toBeNull()
      // 一個查詢都沒有時代價那一句不畫（M4 票 84b）。
      expect(within(panel()).getByText('會問 · 0 個查詢')).toBeVisible()
      expect(within(panel()).queryByText(/幾秒到一分鐘/)).toBeNull()
    })

    it('按了 chip、新的預覽還沒回來時搜尋鍵停著：送出去的要是畫面上列的那一份', async () => {
      render({
        [`GET /api/search/queries?${chosen(['SPY x FAMILY'], [3])}`]: () => new Promise(() => {}),
      })
      renderApp('/media/tv:120089')
      await screen.findByRole('region', { name: '搜尋 torrent' })
      const submit = await within(panel()).findByRole('button', { name: '搜尋' })
      expect(submit).toBeEnabled()

      await userEvent.click(within(panel()).getByRole('button', { name: 'SPY×FAMILY 原名' }))

      await waitFor(() => expect(submit).toBeDisabled())
    })

    it('按下搜尋送的是預覽的同一份選擇', async () => {
      const choice = chosen(['SPY x FAMILY'], [3])
      const stub = render({
        [`GET /api/search/queries?${choice}`]: { body: plan({ queries: ['SPY x FAMILY'] }) },
        [`GET /api/search?${choice}`]: { body: results() },
      })
      renderApp('/media/tv:120089')
      await screen.findByRole('region', { name: '搜尋 torrent' })

      await userEvent.click(await within(panel()).findByRole('button', { name: 'SPY×FAMILY 原名' }))
      await waitFor(async () => expect(await asked()).toEqual(['SPY x FAMILY']))
      await userEvent.click(within(panel()).getByRole('button', { name: '搜尋' }))

      await within(panel()).findByRole('table')
      expect(stub.mock.calls.map(([input]) => String(input))).toContain(`/api/search?${choice}`)
    })

    /** 第一季缺一集的作品：季表上「搜這部作品缺的集」按得下去。 */
    function gappy(): Media {
      return media({
        seasons: [
          {
            season_number: 1,
            name: 'Season 1',
            episode_count: 1,
            air_date: '2022-04-09',
            imported: 0,
            aired: 1,
            episodes: [
              {
                episode_number: 1,
                name: 'E1',
                air_date: '2022-04-09',
                runtime: 24,
                absolute_number: null,
                status: 'missing',
                job: null,
              },
            ],
          },
        ],
      })
    }

    it('從季表搜缺的集時不畫季 chip——缺的形狀決定問哪幾季', async () => {
      render({
        [MEDIA_PATH]: { body: gappy() },
        'GET /api/search/queries?media=tv%3A120089&missing=true': {
          body: plan({ queries: ['SPY x FAMILY S01E01'] }),
        },
        'GET /api/search?media=tv%3A120089&missing=true': { body: results() },
      })
      renderApp('/media/tv:120089')
      await screen.findByRole('region', { name: '搜尋 torrent' })
      await within(panel()).findByRole('group', { name: '要問的季' })

      await userEvent.click(await screen.findByRole('button', { name: '搜這部作品缺的集' }))

      await waitFor(() =>
        expect(within(panel()).queryByRole('group', { name: '要問的季' })).toBeNull(),
      )
      expect(within(panel()).getByRole('group', { name: '要問的名字' })).toBeVisible()
    })

    it('搜缺的集超過上限時只叫人關名字——那時沒有季可以關', async () => {
      const over = Array.from({ length: 12 }, (_, i) => `SPY x FAMILY S0${i}`)
      render({
        [MEDIA_PATH]: { body: gappy() },
        'GET /api/search/queries?media=tv%3A120089&missing=true': {
          body: plan({ queries: over }),
        },
        'GET /api/search?media=tv%3A120089&missing=true': { body: results() },
      })
      renderApp('/media/tv:120089')

      await userEvent.click(await screen.findByRole('button', { name: '搜這部作品缺的集' }))

      expect(
        await within(panel()).findByText('開了 12 個查詢，一次最多 10 個：關掉幾個名字。'),
      ).toBeVisible()
      expect(within(panel()).getByRole('button', { name: '搜尋' })).toHaveAccessibleDescription(
        '開了 12 個查詢，一次最多 10 個：關掉幾個名字。',
      )
      expect(within(panel()).queryByText(/幾秒到一分鐘/)).toBeNull()
    })
  })

  describe('預覽是一個帶查詢數的欄位，代價與等待一句（M4 票 84b）', () => {
    it('標籤的查詢數與清單項數相同；不再另說一句「Berth 會問這幾個」', async () => {
      render()
      renderApp('/media/tv:120089')

      expect(await asked()).toHaveLength(3)
      expect(within(panel()).getByText('會問 · 3 個查詢')).toBeVisible()
      expect(within(panel()).queryByText(/Berth 會問/)).toBeNull()
    })

    it('查詢數那一行是 live region：按 chip 換了幾個查詢，聽得到（M4 票 132）', async () => {
      render()
      renderApp('/media/tv:120089')
      await screen.findByRole('region', { name: '搜尋 torrent' })

      expect(await within(panel()).findByText('會問 · 3 個查詢')).toHaveAttribute(
        'aria-live',
        'polite',
      )
    })

    it('會問幾個查詢與要等多久是同一句', async () => {
      render()
      renderApp('/media/tv:120089')
      await screen.findByRole('region', { name: '搜尋 torrent' })

      expect(
        await within(panel()).findByText(
          '會問 3 個查詢；索引站要現場去連每一個追蹤站，通常要幾秒到一分鐘。',
        ),
      ).toBeVisible()
    })

    it('英文介面：標籤照單複數說查詢數，代價與等待同一句', async () => {
      await i18next.changeLanguage('en')
      try {
        render()
        renderApp('/media/tv:120089')
        const region = await screen.findByRole('region', { name: 'Search torrents' })

        expect(await within(region).findByText('Will ask · 3 queries')).toBeVisible()
        expect(
          within(region).getByText(
            'Sends 3 queries; the indexer contacts every tracker it knows, which usually takes a few seconds to a minute.',
          ),
        ).toBeVisible()
        expect(within(region).queryByText(/Berth will ask/)).toBeNull()

        await userEvent.type(within(region).getByLabelText('Keyword'), 'Spy Family BDRip')

        expect(within(region).getByText('Will ask · 1 query')).toBeVisible()
        expect(
          within(region).getByText(
            'Sends 1 query; the indexer contacts every tracker it knows, which usually takes a few seconds to a minute.',
          ),
        ).toBeVisible()
      } finally {
        await i18next.changeLanguage('zh-Hant')
      }
    })
  })

  it('預設依做種排序，切成大小之後換一列在最前面', async () => {
    render({
      [SEARCH_PATH]: {
        body: results({
          rows: [
            row({ key: 'small', title: '小而多人做種', size: 1, seeders: 99 }),
            row({ key: 'big', title: '大而少人做種', size: 9_000_000_000, seeders: 1 }),
          ],
        }),
      },
    })
    renderApp('/media/tv:120089')
    await userEvent.click(await screen.findByRole('button', { name: '搜尋' }))

    const first = () => within(within(panel()).getByRole('table')).getAllByRole('row')[1]
    expect(within(first()).getByText('小而多人做種')).toBeVisible()

    await userEvent.click(screen.getByRole('button', { name: '大小' }))

    expect(within(first()).getByText('大而少人做種')).toBeVisible()
    expect(screen.getByRole('columnheader', { name: '大小' })).toHaveAttribute(
      'aria-sort',
      'descending',
    )
  })

  it('自己打了關鍵字就只問那一個', async () => {
    const stub = render({
      [`${SEARCH_PATH}&q=Spy+Family+BDRip`]: {
        body: results({ rows: [row({ verdict: 'typed_match' })] }),
      },
    })
    renderApp('/media/tv:120089')

    await userEvent.type(await screen.findByLabelText('關鍵字'), 'Spy Family BDRip')

    expect(await asked()).toEqual(['Spy Family BDRip'])
    expect(within(panel()).getByText('會問 · 1 個查詢')).toBeVisible()
    expect(within(panel()).queryByText(/Berth 只會問/)).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: '搜尋' }))
    expect(await within(panel()).findByRole('table')).toBeVisible()
    expect(stub.mock.calls.map(([input]) => String(input))).toContain(
      '/api/search?media=tv%3A120089&q=Spy+Family+BDRip',
    )
  })

  describe('送單（票 09）', () => {
    /** 搜一次，回一列結果。送單那顆鍵掛在那一列上。 */
    async function searched(
      routes: Record<string, StubRoute | (() => StubRoute | Promise<StubRoute>)> = {},
    ) {
      const stub = render({ [SEARCH_PATH]: { body: results() }, ...routes })
      renderApp('/media/tv:120089')
      await userEvent.selectOptions(await screen.findByLabelText('入庫到'), 'TV')
      await userEvent.click(screen.getByRole('button', { name: '搜尋' }))
      await within(panel()).findByRole('table')
      return stub
    }

    it('確認裡印著資料夾名，而且說清楚這一按就定了（票 04b、brief §4.5）', async () => {
      await searched()

      await userEvent.click(screen.getByRole('button', { name: '送單' }))

      // 搜尋列底下也有同一串字（那是「將會是」的預覽，M1.5 票 08 從身分帶搬來），所以只看確認區塊裡的那一份。
      const confirm = within(within(panel()).getByRole('group', { name: /資料夾會是/ }))
      expect(confirm.getByText('SPY x FAMILY (2022) [tmdbid-120089]')).toBeVisible()
      expect(confirm.getByText(/送單成功那一刻這串字就定下來/)).toBeVisible()
    })

    it('已經凍結過的作品說的是「不會再動它」', async () => {
      await searched({ [MEDIA_PATH]: { body: media({ folder_frozen: true }) } })

      await userEvent.click(screen.getByRole('button', { name: '送單' }))

      expect(screen.getByText(/這串字已經定下來了/)).toBeVisible()
    })

    it('確認之後才真的送出去，body 帶著那一列與選的 Route', async () => {
      const stub = await searched({
        'POST /api/jobs': { body: { job: job(), created: true } },
      })

      await userEvent.click(screen.getByRole('button', { name: '送單' }))
      await userEvent.click(screen.getByRole('button', { name: '確認送單' }))

      expect(await screen.findByText('已送出')).toBeVisible()
      const sent = stub.mock.calls.find(([, init]) => init?.method === 'POST')
      // 只送那一列的 id（M4 票 79）：連結、發佈名、hash、發佈時間與大小都是伺服器記的那一份。
      expect(JSON.parse(String(sent?.[1]?.body))).toEqual({
        source_id: 'source-acg-50',
        media: 'tv:120089',
        route: 1,
      })
    })

    // M3 票 06：送出中再按一次會多建一次（後端冪等，但第二次回「已經在了」會蓋掉「已送出」）。
    it('送出中再按不會再送一次，焦點留在那一顆上', async () => {
      let answer: (route: StubRoute) => void = () => {}
      const stub = await searched({
        'POST /api/jobs': () => new Promise((resolve) => (answer = resolve)),
      })

      await userEvent.click(screen.getByRole('button', { name: '送單' }))
      await userEvent.click(screen.getByRole('button', { name: '確認送單' }))
      const pending = await screen.findByRole('button', { name: '送單中…' })
      await userEvent.click(pending)

      expect(pending).toHaveAttribute('aria-disabled', 'true')
      expect(pending).toHaveFocus()
      expect(stub.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1)
      answer({ body: { job: job(), created: true } })
      expect(await screen.findByText('已送出')).toBeVisible()
    })

    it('同一筆再送一次時說的是「這一個已經在了」，不是一則錯誤（plan §3.3）', async () => {
      await searched({ 'POST /api/jobs': { body: { job: job(), created: false } } })

      await userEvent.click(screen.getByRole('button', { name: '送單' }))
      await userEvent.click(screen.getByRole('button', { name: '確認送單' }))

      expect(await screen.findByText('這一個已經在了')).toBeVisible()
    })

    it('紅的 Route 被擋下來時說的是那個理由與下一步（brief §4.4）', async () => {
      await searched({
        'POST /api/jobs': {
          status: 409,
          body: { detail: { reason: 'route_unhealthy', detail: 'tv' } },
        },
      })

      await userEvent.click(screen.getByRole('button', { name: '送單' }))
      await userEvent.click(screen.getByRole('button', { name: '確認送單' }))

      const alert = await screen.findByRole('alert')
      expect(alert).toHaveTextContent(/那條 Route 現在是紅的/)
      // 服務回的原文貼在旁邊，不翻譯（與精靈的纜繩同一個規矩）。
      expect(alert).toHaveTextContent('tv')
    })

    it('結果過期了說的是再搜一次（M4 票 79）', async () => {
      await searched({
        'POST /api/jobs': {
          status: 404,
          body: { detail: { reason: 'source_expired', detail: '' } },
        },
      })

      await userEvent.click(screen.getByRole('button', { name: '送單' }))
      await userEvent.click(screen.getByRole('button', { name: '確認送單' }))

      const alert = await screen.findByRole('alert')
      expect(alert).toHaveTextContent(/這一筆過期了/)
      expect(alert).toHaveTextContent(/重新搜一次/)
    })

    it.each(REQUEST_FAILURES)('送單沒有成功（%s）時說出對的原因', async (_, failure, expected) => {
      await searched({ 'POST /api/jobs': failure })

      await userEvent.click(screen.getByRole('button', { name: '送單' }))
      await userEvent.click(screen.getByRole('button', { name: '確認送單' }))

      const alert = await screen.findByRole('alert')
      expect(alert).toHaveTextContent(/送單沒有成功。/)
      expect(alert).toHaveTextContent(expected)
      expect(alert).not.toHaveTextContent(/自己的 API/)
    })

    it('磁碟不夠時說的是那個理由與下一步，量到的數字貼在旁邊（M3 票 04）', async () => {
      await searched({
        'POST /api/jobs': {
          status: 409,
          body: {
            detail: {
              reason: 'low_disk_space',
              detail: '/data/torrent/incomplete: 3.2 GiB free, below 10 GiB',
            },
          },
        },
      })

      await userEvent.click(screen.getByRole('button', { name: '送單' }))
      await userEvent.click(screen.getByRole('button', { name: '確認送單' }))

      const alert = await screen.findByRole('alert')
      expect(alert).toHaveTextContent(/下載目錄的磁碟空間低於門檻/)
      expect(alert).toHaveTextContent('3.2 GiB free')
    })

    it('刪除過、紀錄還在的那一個被擋下來時，給得出去那一筆的路（M3 票 04）', async () => {
      const hash = 'a'.repeat(40)
      await searched({
        'POST /api/jobs': {
          status: 409,
          body: { detail: { reason: 'job_removed', detail: hash } },
        },
      })

      await userEvent.click(screen.getByRole('button', { name: '送單' }))
      await userEvent.click(screen.getByRole('button', { name: '確認送單' }))

      const alert = await screen.findByRole('alert')
      expect(alert).toHaveTextContent(/之前下載過、後來刪除了/)
      expect(within(alert).getByRole('link', { name: '看那一筆下載' })).toHaveAttribute(
        'href',
        `/jobs/${hash}`,
      )
      // hash 已經在連結裡了，不再另外貼一次原文。
      expect(alert).not.toHaveTextContent(hash)
    })

    it('還沒選 Route 時按鈕照樣按得下去，說不行的是那句話（票 02b）', async () => {
      // 兩條 Route 都收得下這部作品，所以下拉不會自動選一條。
      const stub = render({ [`${SEARCH_PATH}`]: { body: results() } })
      renderApp('/media/tv:120089')
      await userEvent.click(await screen.findByRole('button', { name: '搜尋' }))
      await within(panel()).findByRole('table')

      await userEvent.click(screen.getByRole('button', { name: '送單' }))

      expect(screen.getByText(/先在上面選一條/)).toBeVisible()
      expect(screen.getByRole('button', { name: '確認送單' })).toBeEnabled()
      expect(stub.mock.calls.filter(([, init]) => init?.method === 'POST')).toEqual([])

      // 按下去也**不打 API**：送一個假的 route id 出去會換回一句「那條 Route 不在了」，
      // 而使用者根本還沒選過（PRODUCT 原則 4：說得出下一步的那一句才算數）。
      await userEvent.click(screen.getByRole('button', { name: '確認送單' }))

      expect(await screen.findByRole('alert')).toHaveTextContent(/先在上面選一條/)
      expect(stub.mock.calls.filter(([, init]) => init?.method === 'POST')).toEqual([])
    })

    it('確認說出送到哪一條 Route（票 15 critique：選 Route 的下拉在表格外面）', async () => {
      await searched()

      await userEvent.click(screen.getByRole('button', { name: '送單' }))

      expect(within(panel()).getByText('入庫到「TV」')).toBeVisible()
    })

    it('展開確認時焦點進到確認裡，取消之後回到送單鍵（票 15 critique）', async () => {
      await searched()

      await userEvent.click(screen.getByRole('button', { name: '送單' }))
      expect(screen.getByRole('group', { name: /這部作品在媒體庫裡的資料夾會是/ })).toHaveFocus()

      await userEvent.click(screen.getByRole('button', { name: '取消' }))
      expect(screen.getByRole('button', { name: '送單' })).toHaveFocus()
    })

    it('Esc 收起確認，焦點回到送單鍵', async () => {
      await searched()

      await userEvent.click(screen.getByRole('button', { name: '送單' }))
      await userEvent.keyboard('{Escape}')

      expect(screen.queryByRole('button', { name: '確認送單' })).not.toBeInTheDocument()
      expect(screen.getByRole('button', { name: '送單' })).toHaveFocus()
    })

    it('送出之後宣告結果，焦點落在「看下載列表」', async () => {
      await searched({ 'POST /api/jobs': { body: { job: job(), created: true } } })

      await userEvent.click(screen.getByRole('button', { name: '送單' }))
      await userEvent.click(screen.getByRole('button', { name: '確認送單' }))

      expect(await screen.findByRole('status')).toHaveTextContent('已送出')
      expect(screen.getByRole('link', { name: '看下載列表' })).toHaveFocus()
    })

    it('選了 Route 之後，「先選一條 Route」那句錯誤就不在了', async () => {
      render({ [`${SEARCH_PATH}`]: { body: results() } })
      renderApp('/media/tv:120089')
      await userEvent.click(await screen.findByRole('button', { name: '搜尋' }))
      await within(panel()).findByRole('table')
      await userEvent.click(screen.getByRole('button', { name: '送單' }))
      await userEvent.click(screen.getByRole('button', { name: '確認送單' }))
      // 錯誤是一句完整的話，不是懸著冒號、等著接資料夾名的那一句。
      expect(await screen.findByRole('alert')).toHaveTextContent(/先在上面選一條.*。$/)

      await userEvent.selectOptions(screen.getByLabelText('入庫到'), 'TV')

      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    })

    it('上次送單用的那條 Route 是下一次的預選值（plan §2.2）', async () => {
      render({ [MEDIA_PATH]: { body: media({ default_route_id: 2 }) } })
      renderApp('/media/tv:120089')

      expect(await screen.findByLabelText('入庫到')).toHaveValue('2')
    })
  })
})
