import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Media } from '../api/media'
import type { SearchResults, SearchResult } from '../api/search'
import { HEALTHY, stubApi, type StubRoute } from '../test/fetch'
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
    poster_url: '',
    runtime: null,
    folder_name: 'SPY x FAMILY (2022) [tmdbid-120089]',
    fetched_at: '2026-09-09T12:00:00Z',
    problem: null,
    detail: '',
    routes: [
      { id: 1, name: 'TV', slug: 'tv', collection_type: 'tvshows' },
      { id: 2, name: 'Anime', slug: 'anime', collection_type: 'tvshows' },
    ],
    seasons: [],
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
    download_url: 'http://prowlarr:9696/2/download?apikey=k',
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
    ...overrides,
  }
}

function results(overrides: Partial<SearchResults> = {}): SearchResults {
  return {
    rows: [row()],
    total: 1,
    discarded: 0,
    attempts: [{ step: 'SPY x FAMILY', status: 'ok', detail: '1', error: '' }],
    problem: null,
    detail: '',
    ...overrides,
  }
}

function render(
  routes: Record<string, StubRoute | (() => StubRoute)> = {},
  role: 'admin' | 'user' = 'admin',
) {
  return stubApi({
    'GET /api/health': { body: HEALTHY },
    'GET /api/auth/me': { body: { name: 'skipper', role } },
    [MEDIA_PATH]: { body: media() },
    [QUERIES_PATH]: { body: { queries: ['SPY x FAMILY', 'SPY×FAMILY', '間諜家家酒'] } },
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

/** 這一頁的搜尋區塊。其餘區塊的測試在 `pages/MediaDetailPage.test.tsx`。 */
function panel() {
  return screen.getByRole('region', { name: '搜尋 torrent' })
}

describe('搜尋 torrent 與結果表', () => {
  it('待命時先列出會送出去的關鍵字，而且一個索引站都還沒打', async () => {
    const stub = render()
    renderApp('/media/tv:120089')

    expect(await screen.findByText('SPY x FAMILY · SPY×FAMILY · 間諜家家酒')).toBeVisible()
    expect(screen.getByText(/這通常要一分鐘左右/)).toBeVisible()
    expect(stub.mock.calls.map(([input]) => String(input))).not.toContain(
      '/api/search?media=tv%3A120089',
    )
  })

  it('搜尋中先把要問的關鍵字鋪成纜繩，不是只有一顆變字的按鈕', async () => {
    // 一次搜尋要 35–85 秒；那段時間裡畫面上要有東西說得出「正在問什麼」。
    const base = render()
    holdSearch(base)
    renderApp('/media/tv:120089')
    await screen.findByText('SPY x FAMILY · SPY×FAMILY · 間諜家家酒')

    await userEvent.click(screen.getByRole('button', { name: '搜尋' }))

    const lines = within(panel()).getAllByRole('listitem')
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
          total: 2,
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
            },
          ],
        }),
      },
    })
    renderApp('/media/tv:120089')

    await userEvent.click(await screen.findByRole('button', { name: '搜尋' }))

    expect(await screen.findByText('GET /api/v1/search: ReadTimeout')).toBeVisible()
    // 垮掉的那一條不影響結果表。
    expect(within(panel()).getByRole('table')).toBeVisible()
  })

  it('索引站沒接時說得出下一步，而不是一張空清單（票 08 驗收）', async () => {
    render({
      [SEARCH_PATH]: {
        body: results({ rows: [], total: 0, attempts: [], problem: 'not_configured' }),
      },
    })
    renderApp('/media/tv:120089')

    await userEvent.click(await screen.findByRole('button', { name: '搜尋' }))

    expect(await screen.findByText(/設定精靈的第 5 步跳過了索引站/)).toBeVisible()
    expect(screen.getByRole('link', { name: '前往設定精靈' })).toBeVisible()
    expect(within(panel()).queryByRole('table')).not.toBeInTheDocument()
  })

  it('一般使用者看到的是「請管理員…」而不是一條進不去的連結', async () => {
    render(
      {
        [SEARCH_PATH]: {
          body: results({ rows: [], total: 0, attempts: [], problem: 'not_configured' }),
        },
      },
      'user',
    )
    renderApp('/media/tv:120089')

    await userEvent.click(await screen.findByRole('button', { name: '搜尋' }))

    expect(await screen.findByText('請管理員到設定精靈接上索引站。')).toBeVisible()
    expect(screen.queryByRole('link', { name: '前往設定精靈' })).not.toBeInTheDocument()
  })

  it('連不上索引站時也給得出「去哪裡改位址」', async () => {
    render({
      [SEARCH_PATH]: {
        body: results({
          rows: [],
          total: 0,
          attempts: [],
          problem: 'unreachable',
          detail: 'GET /api/v1/search: connection refused',
        }),
      },
    })
    renderApp('/media/tv:120089')

    await userEvent.click(await screen.findByRole('button', { name: '搜尋' }))

    expect(await screen.findByText(/連不上索引站/)).toBeVisible()
    expect(screen.getByText('GET /api/v1/search: connection refused')).toBeVisible()
    expect(screen.getByRole('link', { name: '前往設定精靈' })).toBeVisible()
  })

  it('搜到但一筆都沒有不是錯誤', async () => {
    render({ [SEARCH_PATH]: { body: results({ rows: [], total: 0 }) } })
    renderApp('/media/tv:120089')

    await userEvent.click(await screen.findByRole('button', { name: '搜尋' }))

    expect(await screen.findByText(/沒有東西/)).toBeVisible()
  })

  it('索引站回了一堆但沒有一筆是這部作品，說得出那一堆去了哪裡', async () => {
    render({
      [SEARCH_PATH]: { body: results({ rows: [], total: 0, discarded: 1518 }) },
    })
    renderApp('/media/tv:120089')

    await userEvent.click(await screen.findByRole('button', { name: '搜尋' }))

    expect(await screen.findByText(/索引站回了 1518 筆/)).toBeVisible()
  })

  it('略過的筆數不藏起來', async () => {
    render({ [SEARCH_PATH]: { body: results({ discarded: 1518 }) } })
    renderApp('/media/tv:120089')

    await userEvent.click(await screen.findByRole('button', { name: '搜尋' }))

    expect(await screen.findByText('另有 1518 筆名字對不上這部作品，已經略過。')).toBeVisible()
  })

  it('預設依做種排序，切成大小之後換一列在最前面', async () => {
    render({
      [SEARCH_PATH]: {
        body: results({
          rows: [
            row({ key: 'small', title: '小而多人做種', size: 1, seeders: 99 }),
            row({ key: 'big', title: '大而少人做種', size: 9_000_000_000, seeders: 1 }),
          ],
          total: 2,
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
    const stub = render({ [`${SEARCH_PATH}&q=Spy+Family+BDRip`]: { body: results() } })
    renderApp('/media/tv:120089')

    await userEvent.type(await screen.findByLabelText('關鍵字'), 'Spy Family BDRip')

    expect(screen.getByText('Berth 只會問這一個：')).toBeVisible()
    await userEvent.click(screen.getByRole('button', { name: '搜尋' }))
    expect(await within(panel()).findByRole('table')).toBeVisible()
    expect(stub.mock.calls.map(([input]) => String(input))).toContain(
      '/api/search?media=tv%3A120089&q=Spy+Family+BDRip',
    )
  })

  it('換一條 Route 就重問一次「會用哪幾個關鍵字」——它只影響這一輪搜尋（票 04b）', async () => {
    const stub = render({
      [`${QUERIES_PATH}&route=2`]: {
        body: { queries: ['SPY x FAMILY', 'SPY x FAMILY Season 3', '間諜家家酒 第3季'] },
      },
    })
    renderApp('/media/tv:120089')

    await userEvent.selectOptions(await screen.findByLabelText('入庫到'), 'Anime')

    expect(await screen.findByText(/SPY x FAMILY Season 3/)).toBeVisible()
    // 偏好不落地：整輪下來一個非 GET 都沒送出去。
    expect(stub.mock.calls.filter(([, init]) => init?.method === 'POST')).toEqual([])
  })
})
