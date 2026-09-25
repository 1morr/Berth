import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18next from 'i18next'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { Job } from '../api/jobs'
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
    download_url: 'http://prowlarr:9696/2/download?apikey=k',
    key: 'a'.repeat(40),
    info_hash: 'a'.repeat(40),
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
    ...overrides,
  }
}

/** 送單成功時後端回的那一筆。只有畫面讀得到的那幾格才有意義。 */
function job(): Job {
  return {
    hash: 'a'.repeat(40),
    name: '[ANi] SPY x FAMILY - 50 [1080P][Baha][WEB-DL][AAC AVC][CHT][MP4]',
    state: 'submitted',
    trigger: 'manual',
    trigger_ref: '',
    error: '',
    media_id: 'tv:120089',
    media_title: 'SPY×FAMILY 間諜家家酒',
    media_title_en: 'SPY x FAMILY',
    route_id: 1,
    route_name: 'TV',
    route_slug: 'tv',
    user_id: 1,
    user_name: 'skipper',
    save_path: '',
    content_path: '',
    total_size: 0,
    progress: 0,
    client_state: '',
    added_at: '2026-09-10T12:00:00Z',
    completed_at: null,
    imported_at: null,
    retryable: false,
    replannable: false,
    reimportable: false,
    plan_id: null,
    audits: 0,
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
    retry_at: null,
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
    [QUERIES_PATH]: { body: { queries: ['SPY x FAMILY', 'SPY×FAMILY', '間諜家家酒'] } },
    // 同一頁 admin 才有的「RSS 訂閱」段（M3 票 19）。
    'GET /api/rss/series?media=tv%3A120089': { body: [] },
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
            total: 2,
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
    // 收起來的 `<details>` 仍在 DOM 裡，看不見的是它；全部正常時整塊沒有任何一塊信號色。
    expect(within(panel()).getByText('SPY×FAMILY')).not.toBeVisible()
    for (const done of within(panel()).getAllByText('已完成')) expect(done).not.toBeVisible()

    await userEvent.click(summary)

    expect(within(panel()).getByText('SPY×FAMILY')).toBeVisible()
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
            },
          ],
        }),
      },
    })
    renderApp('/media/tv:120089')

    await userEvent.click(await screen.findByRole('button', { name: '搜尋' }))

    const failed = await within(panel()).findByText('GET /api/v1/search: ReadTimeout')
    const summary = within(panel()).getByText('其餘 2 個關鍵字有回應')
    expect(failed).toBeVisible()
    expect(summary).toBeVisible()
    // 垮掉的那一條在摘要上面（需要你的事浮到摘要層）。
    expect(failed.compareDocumentPosition(summary) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(within(panel()).getByText('SPY x FAMILY')).not.toBeVisible()
  })

  it('索引站沒接時說得出下一步，而不是一張空清單（票 08 驗收）', async () => {
    render({
      [SEARCH_PATH]: {
        body: results({ rows: [], total: 0, attempts: [], problem: 'not_configured' }),
      },
    })
    renderApp('/media/tv:120089')

    await userEvent.click(await screen.findByRole('button', { name: '搜尋' }))

    expect(await screen.findByText(/設定精靈的第 6 步跳過了索引站/)).toBeVisible()
    expect(screen.getByRole('link', { name: '前往設定：索引站' })).toHaveAttribute(
      'href',
      '/settings/indexers',
    )
    expect(within(panel()).queryByRole('table')).not.toBeInTheDocument()
  })

  it('索引站沒接時按下去之前就說，按了之後同一件事只說一次（票 13）', async () => {
    render({
      [QUERIES_PATH]: { body: { queries: ['SPY x FAMILY'], problem: 'not_configured' } },
      [SEARCH_PATH]: {
        body: results({ rows: [], total: 0, attempts: [], problem: 'not_configured' }),
      },
    })
    renderApp('/media/tv:120089')

    // 還沒按：一個索引站都沒打，畫面已經說得出下一步。
    expect(await screen.findByText(/設定精靈的第 6 步跳過了索引站/)).toBeVisible()
    expect(within(panel()).getByRole('link', { name: '前往設定：索引站' })).toBeVisible()

    await userEvent.click(screen.getByRole('button', { name: '搜尋' }))

    expect(await screen.findByText('找到 0 筆，0 個關鍵字沒問到。')).toBeInTheDocument()
    expect(screen.getAllByText(/設定精靈的第 6 步跳過了索引站/)).toHaveLength(1)
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

    expect(await screen.findByText('請管理員到設定接上索引站。')).toBeVisible()
    expect(screen.queryByRole('link', { name: '前往設定：索引站' })).not.toBeInTheDocument()
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
    expect(screen.getByRole('link', { name: '前往設定：索引站' })).toBeVisible()
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
      expect(JSON.parse(String(sent?.[1]?.body))).toEqual({
        source: {
          url: 'http://prowlarr:9696/2/download?apikey=k',
          title: '[ANi] SPY x FAMILY - 50 [1080P][Baha][WEB-DL][AAC AVC][CHT][MP4]',
          // 索引站報的那一個，不是 `key`——不報 hash 的站那一格是一條 guid。
          info_hash: 'a'.repeat(40),
          // 規劃時比播出日（M3 票 14）：那一列的發佈時間原樣帶回去，沒報就是 null。
          published_at: null,
        },
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
