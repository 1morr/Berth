import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Media } from '../api/media'
import { HEALTHY, stubApi, type StubRoute } from '../test/fetch'
import { renderApp } from '../test/render'

afterEach(() => {
  vi.unstubAllGlobals()
})

const SPY_PATH = 'GET /api/media/tv%3A120089'

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
    overview: '互相隱藏了真實身份的新家庭。',
    poster_url: 'https://image.tmdb.org/t/p/w342/spy.jpg',
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
    seasons: [
      {
        season_number: 1,
        name: 'Season 1',
        episode_count: 25,
        air_date: '2022-04-09',
        imported: 1,
        aired: 1,
        episodes: [
          {
            episode_number: 1,
            name: 'OPERATION STRIX',
            air_date: '2022-04-09',
            runtime: 25,
            absolute_number: 1,
            status: 'imported',
          },
        ],
      },
      {
        season_number: 2,
        name: 'Season 2',
        episode_count: 12,
        air_date: '2023-10-07',
        imported: 0,
        aired: 1,
        episodes: [
          {
            episode_number: 1,
            name: 'FOLLOW MAMA AND PAPA',
            air_date: '2023-10-07',
            runtime: 24,
            absolute_number: 26,
            status: 'stuck',
          },
        ],
      },
    ],
    files: [],
    unmatched: [],
    versions: [],
    ...overrides,
  }
}

type LedgerFile = Media['files'][number]

function ledgerFile(overrides: Partial<LedgerFile> = {}): LedgerFile {
  return {
    id: 1,
    action: 'import',
    season: 1,
    episode_start: 1,
    episode_end: null,
    tags: '[WEB][1080p][Lilith-Raws]',
    target_path:
      '/data/library/anime/SPY x FAMILY (2022) [tmdbid-120089]/Season 01/SPY x FAMILY (2022) - S01E01 - OPERATION STRIX [WEB][1080p][Lilith-Raws].mkv',
    status: 'ok',
    presence: 'found',
    resolve_after: null,
    resolve_attempts: 0,
    job_hash: '4bd0f6ef1d3b1e3cbb1e1b6b6c2a9c7d8e5f0a1b',
    ...overrides,
  }
}

/** 走真正的 route tree：這一頁掛在 `/media/$mediaId`，而錯誤裡有站內連結。 */
function render(
  routes: Record<string, StubRoute | (() => StubRoute)> = {},
  role: 'admin' | 'user' = 'admin',
) {
  return stubApi({
    'GET /api/health': { body: HEALTHY },
    'GET /api/auth/me': { body: { name: 'skipper', role } },
    [SPY_PATH]: { body: media() },
    // 票 08 的搜尋區塊待命時就會問一次「會用哪幾個關鍵字」（不打索引站，只讀快照）。
    'GET /api/search/queries?media=tv%3A120089': { body: { queries: ['SPY x FAMILY'] } },
    ...routes,
  })
}

describe('Media 詳情頁', () => {
  it('探索牆的卡片點得進詳情頁（票 03 留下的那條線由票 04 接手）', async () => {
    stubApi({
      'GET /api/health': { body: HEALTHY },
      'GET /api/auth/me': { body: { name: 'skipper', role: 'admin' } },
      'GET /api/discover/trending': {
        body: {
          items: [
            {
              id: 'tv:120089',
              tmdb_id: 120089,
              kind: 'tv',
              title: 'SPY×FAMILY 間諜家家酒',
              title_en: 'SPY x FAMILY',
              year: 2022,
              poster_url: '',
            },
          ],
          problem: null,
          detail: '',
        },
      },
      'GET /api/discover/popular': { body: { items: [], problem: null, detail: '' } },
      [SPY_PATH]: { body: media() },
    })
    const { router } = renderApp('/')

    await userEvent.click(await screen.findByRole('link', { name: /SPY×FAMILY/ }))

    // 冒號在路徑段裡會被編碼；`mediaId` 解回來仍然是 `tv:120089`（下面那一行證明了）。
    await waitFor(() => expect(router.state.location.pathname).toBe('/media/tv%3A120089'))
    expect(await screen.findByRole('heading', { name: 'SPY×FAMILY 間諜家家酒' })).toBeVisible()
  })

  it('三個標題都在——英文那一個是檔名用的（brief §7.5）', async () => {
    render()
    renderApp('/media/tv:120089')

    expect(await screen.findByRole('heading', { name: 'SPY×FAMILY 間諜家家酒' })).toBeVisible()
    expect(screen.getByText('SPY x FAMILY')).toBeVisible()
    expect(screen.getByText('SPY×FAMILY')).toBeVisible()
  })

  it('資料夾名在送單之前就看得到，而且說得出它什麼時候定下來（票 04b）', async () => {
    render()
    renderApp('/media/tv:120089')

    expect(await screen.findByText('資料夾將會是')).toBeVisible()
    expect(screen.getByText('SPY x FAMILY (2022) [tmdbid-120089]')).toBeVisible()
    expect(screen.getByText(/第一次送單成功那一刻這串字就定下來/)).toBeVisible()
  })

  it('這一頁沒有「追蹤」這個動作（票 04b）', async () => {
    render()
    renderApp('/media/tv:120089')

    await screen.findByRole('heading', { name: 'SPY×FAMILY 間諜家家酒' })

    expect(screen.queryByRole('button', { name: '追蹤' })).not.toBeInTheDocument()
    expect(screen.queryByText('已追蹤')).not.toBeInTheDocument()
  })

  it('季預設全收，展開才列出那一季的集（使用者拍板）', async () => {
    render()
    renderApp('/media/tv:120089')

    const season = await screen.findByText('Season 2')
    // 收起來的 `<details>` 仍然在 DOM 裡，看不見的是它——所以問的是可見性不是存在。
    expect(screen.getByText('FOLLOW MAMA AND PAPA')).not.toBeVisible()

    await userEvent.click(season)

    expect(await screen.findByText('FOLLOW MAMA AND PAPA')).toBeVisible()
  })

  it('第二季第一集的絕對編號是 26，不是 1（brief §20.3）', async () => {
    render()
    renderApp('/media/tv:120089')

    await userEvent.click(await screen.findByText('Season 2'))

    const row = (await screen.findByText('FOLLOW MAMA AND PAPA')).closest('tr')
    expect(within(row!).getByText('#26')).toBeVisible()
  })

  it('沒有 Absolute group 的作品不畫絕對編號那一欄', async () => {
    const plain = media()
    render({
      [SPY_PATH]: {
        body: media({
          seasons: plain.seasons.map((season) => ({
            ...season,
            episodes: season.episodes.map((episode) => ({ ...episode, absolute_number: null })),
          })),
        }),
      },
    })
    renderApp('/media/tv:120089')

    await userEvent.click(await screen.findByText('Season 2'))

    expect(screen.queryByRole('columnheader', { name: '絕對' })).not.toBeInTheDocument()
  })

  it('後端只回相符的 Route，下拉就只列得出那幾條', async () => {
    render()
    renderApp('/media/tv:120089')

    const select = await screen.findByLabelText<HTMLSelectElement>('入庫到')

    expect([...select.options].map((option) => option.text)).toEqual(['尚未指定', 'TV', 'Anime'])
  })

  it('選了 Route 不會送出任何請求——它是偏好，不是承諾（票 04b）', async () => {
    const stub = render()
    renderApp('/media/tv:120089')

    await userEvent.selectOptions(await screen.findByLabelText('入庫到'), 'Anime')

    expect(stub.mock.calls.filter(([, init]) => init?.method === 'POST')).toEqual([])
  })

  it('季數與集數不把 Specials 算進去', async () => {
    render({
      [SPY_PATH]: {
        body: media({
          seasons: [
            {
              season_number: 0,
              name: 'Specials',
              episode_count: 3,
              air_date: '2023-07-28',
              imported: 0,
              aired: 0,
              episodes: [],
            },
            ...media().seasons,
          ],
        }),
      },
    })
    renderApp('/media/tv:120089')

    // TMDB 自己報的是 3 季 50 集；把特輯算進去會變成 4 季 53 集，與封面對不起來。
    expect(await screen.findByText('2 季 · 37 集')).toBeVisible()
    // 但清單本身仍然列得出那一季——它是真的存在。
    expect(screen.getByText('Specials')).toBeVisible()
  })

  it('識別欄位說「首播 / 上映」，值就是那個日期而不是一個年份', async () => {
    render()
    renderApp('/media/tv:120089')

    // 季列上也有同一個日期，所以問的是識別那一份剖面裡的那一格。
    const row = (await screen.findByText('首播 / 上映')).closest('div')
    expect(within(row!).getByText('2022-04-09')).toBeVisible()
  })

  it('只有一條相符的 Route 時自動選它（票 04b）', async () => {
    render({
      [SPY_PATH]: {
        body: media({
          routes: [{ id: 2, name: 'Anime', slug: 'anime', collection_type: 'tvshows' }],
        }),
      },
    })
    renderApp('/media/tv:120089')

    const select = await screen.findByLabelText<HTMLSelectElement>('入庫到')

    expect(select.value).toBe('2')
  })

  it('兩條以上時不替使用者選，而清掉選擇之後也不會被選回去', async () => {
    render()
    renderApp('/media/tv:120089')

    const select = await screen.findByLabelText<HTMLSelectElement>('入庫到')
    expect(select.value).toBe('')

    await userEvent.selectOptions(select, 'Anime')
    await userEvent.selectOptions(select, '尚未指定')

    expect(select.value).toBe('')
  })

  it('快照過期不是紅燈——頁面照樣畫得出來（The One Meaning Rule）', async () => {
    render({
      [SPY_PATH]: { body: media({ problem: 'unreachable', detail: 'connection refused' }) },
    })
    renderApp('/media/tv:120089')

    await screen.findByText('Season 2')

    // 紅色只代表「在你動手之前走不下去」，而這一格的前提正是頁面仍然可用。
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('電影沒有季集區塊，改說片長（票 04 驗收）', async () => {
    render({
      'GET /api/media/movie%3A1241982': {
        body: media({
          id: 'movie:1241982',
          tmdb_id: 1241982,
          kind: 'movie',
          title: '海洋奇緣2',
          title_en: 'Moana 2',
          title_original: 'Moana 2',
          runtime: 100,
          seasons: [],
          routes: [{ id: 3, name: 'Movies', slug: 'movies', collection_type: 'movies' }],
        }),
      },
    })
    renderApp('/media/movie:1241982')

    expect(await screen.findByText('電影沒有季集。')).toBeVisible()
    expect(screen.getByText('100 分鐘')).toBeVisible()
  })

  it('一條相符的 Route 都沒有時說得出下一步', async () => {
    render({ [SPY_PATH]: { body: media({ routes: [] }) } })
    renderApp('/media/tv:120089')

    expect(await screen.findByText(/還沒有任何一條收劇集的 Route/)).toBeVisible()
    expect(screen.getByRole('link', { name: '到設定精靈建 Route' })).toBeVisible()
  })

  it('一般使用者看到的是「請管理員」，不是一條進不去的連結', async () => {
    render({ [SPY_PATH]: { body: media({ routes: [] }) } }, 'user')
    renderApp('/media/tv:120089')

    expect(await screen.findByText(/請管理員建一條/)).toBeVisible()
    expect(screen.queryByRole('link', { name: '到設定精靈建 Route' })).not.toBeInTheDocument()
  })

  it('快照過期而 TMDB 連不上時，季集照樣畫得出來（shape brief §5）', async () => {
    render({
      [SPY_PATH]: {
        body: media({
          problem: 'unreachable',
          detail: 'GET /tv/120089: connection refused',
        }),
      },
    })
    renderApp('/media/tv:120089')

    expect(await screen.findByText('Season 2')).toBeVisible()
    expect(screen.getByText(/連不上 TMDB/)).toBeVisible()
    expect(screen.getByText('GET /tv/120089: connection refused')).toBeVisible()
  })

  it('TMDB 上沒有這部作品時不給重試，給的是回探索頁的路', async () => {
    render({
      [SPY_PATH]: {
        body: media({
          problem: 'not_found',
          detail: 'tv/120089: no such title on TMDB',
          fetched_at: null,
          seasons: [],
        }),
      },
    })
    renderApp('/media/tv:120089')

    expect(await screen.findByText(/TMDB 上沒有這部作品/)).toBeVisible()
    expect(screen.queryByRole('button', { name: '重試' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: '回探索頁' })).toBeVisible()
  })

  it('集表多一欄「入庫」，每一集說得出它在媒體庫裡的樣子（票 13）', async () => {
    render()
    renderApp('/media/tv:120089')

    await userEvent.click(await screen.findByText('Season 1'))
    const imported = (await screen.findByText('OPERATION STRIX')).closest('tr')!
    expect(within(imported).getByText('已入庫')).toBeVisible()

    await userEvent.click(screen.getByText('Season 2'))
    const stuck = (await screen.findByText('FOLLOW MAMA AND PAPA')).closest('tr')!
    // 卡住的那一集要人去看是哪一筆下載停下來了。
    expect(within(stuck).getByRole('link', { name: '卡住' })).toHaveAttribute('href', '/jobs')
  })

  it('季列說得出這一季播出的集數裡入庫了幾集', async () => {
    render()
    renderApp('/media/tv:120089')

    const season = (await screen.findByText('Season 1')).closest('summary')!

    expect(within(season).getByText('1 / 1 集入庫')).toBeVisible()
  })

  it('檔案清單說得出每個檔案的季集、Tags、目標路徑、帳本與 Jellyfin', async () => {
    render({ [SPY_PATH]: { body: media({ files: [ledgerFile()] }) } })
    renderApp('/media/tv:120089')

    const files = await screen.findByRole('region', { name: '檔案與版本' })
    await userEvent.click(within(files).getByText('1 個檔案'))

    expect(within(files).getByText('正片')).toBeVisible()
    expect(within(files).getByText('S01E01')).toBeVisible()
    expect(within(files).getByText('[WEB][1080p][Lilith-Raws]')).toBeVisible()
    expect(within(files).getByText(/Season 01\/SPY x FAMILY \(2022\) - S01E01/)).toBeVisible()
    expect(within(files).getByText('對得上')).toBeVisible()
    expect(within(files).getByText('Jellyfin 已收錄')).toBeVisible()
  })

  it('還在等 Jellyfin 的檔案說得出下一次什麼時候查', async () => {
    const soon = new Date(Date.now() + 3 * 60 * 1000).toISOString()
    render({
      [SPY_PATH]: {
        body: media({
          files: [ledgerFile({ presence: 'searching', resolve_after: soon, resolve_attempts: 1 })],
        }),
      },
    })
    renderApp('/media/tv:120089')

    const files = await screen.findByRole('region', { name: '檔案與版本' })
    await userEvent.click(within(files).getByText('1 個檔案'))

    expect(within(files).getByText(/Jellyfin 還在掃描/)).toBeVisible()
    expect(within(files).getByText(/3 分鐘/)).toBeVisible()
  })

  it('反查用完的檔案說得出試了幾次', async () => {
    render({
      [SPY_PATH]: {
        body: media({ files: [ledgerFile({ presence: 'lost', resolve_attempts: 6 })] }),
      },
    })
    renderApp('/media/tv:120089')

    const files = await screen.findByRole('region', { name: '檔案與版本' })
    await userEvent.click(within(files).getByText('1 個檔案'))

    expect(within(files).getByText('Jellyfin 試了 6 次都沒找到')).toBeVisible()
  })

  it('季列的計數照後端給的數字，不自己重算（shape brief §7）', async () => {
    const plain = media()
    render({
      [SPY_PATH]: {
        body: media({ seasons: [{ ...plain.seasons[0], imported: 3, aired: 7 }] }),
      },
    })
    renderApp('/media/tv:120089')

    const season = (await screen.findByText('Season 1')).closest('summary')!

    expect(within(season).getByText('3 / 7 集入庫')).toBeVisible()
  })

  it('有檔案但沒有多版本時說一句話，不留空區塊', async () => {
    render({ [SPY_PATH]: { body: media({ files: [ledgerFile()] }) } })
    renderApp('/media/tv:120089')

    const files = await screen.findByRole('region', { name: '檔案與版本' })

    expect(within(files).getByText('每一集都只有一個版本。')).toBeVisible()
  })

  it('只有對不到的檔案時，仍然說得出一個檔案都還沒入庫', async () => {
    render({
      [SPY_PATH]: {
        body: media({
          unmatched: [{ rel_path: 'SP01.mkv', job_hash: 'a'.repeat(40), job_name: 'release' }],
        }),
      },
    })
    renderApp('/media/tv:120089')

    const files = await screen.findByRole('region', { name: '檔案與版本' })

    expect(within(files).getByText('還沒有任何檔案入庫。')).toBeVisible()
    expect(within(files).getByText('SP01.mkv')).toBeVisible()
  })

  it('一個檔案都沒入庫時說一句話，不留一塊空白', async () => {
    render()
    renderApp('/media/tv:120089')

    const files = await screen.findByRole('region', { name: '檔案與版本' })

    expect(within(files).getByText('還沒有任何檔案入庫。')).toBeVisible()
  })

  it('對不到的檔案列出來，並說得出它留在原位', async () => {
    render({
      [SPY_PATH]: {
        body: media({
          unmatched: [
            {
              rel_path: '[Group] SPY×FAMILY/[Group] SPY×FAMILY [SP][01] [1080p].mkv',
              job_hash: '4bd0f6ef1d3b1e3cbb1e1b6b6c2a9c7d8e5f0a1b',
              job_name: '[Group] SPY×FAMILY S01 [01-25][1080p][CHT]',
            },
          ],
        }),
      },
    })
    renderApp('/media/tv:120089')

    const files = await screen.findByRole('region', { name: '檔案與版本' })

    expect(within(files).getByText('對不到的檔案')).toBeVisible()
    expect(within(files).getByText(/\[SP\]\[01\]/)).toBeVisible()
    expect(within(files).getByText(/留在 complete 原位/)).toBeVisible()
    expect(within(files).getByRole('link', { name: '看下載列表' })).toHaveAttribute('href', '/jobs')
  })

  it('多版本並存列出 Jellyfin 版本選單上會出現的名字（brief §7.7）', async () => {
    render({
      [SPY_PATH]: {
        body: media({
          // 有版本群組就一定有正片——版本區塊掛在「有正片」底下。
          files: [ledgerFile()],
          versions: [
            {
              season: 1,
              episode_start: 1,
              episode_end: null,
              labels: [
                'SPY x FAMILY (2022) - S01E01 - OPERATION STRIX [WEB][1080p][Lilith-Raws]',
                'SPY x FAMILY (2022) - S01E01 - OPERATION STRIX [BD][2160p][Sakurato]',
              ],
            },
          ],
        }),
      },
    })
    renderApp('/media/tv:120089')

    const files = await screen.findByRole('region', { name: '檔案與版本' })

    expect(within(files).getByText('多版本並存')).toBeVisible()
    expect(within(files).getByText(/\[BD\]\[2160p\]\[Sakurato\]/)).toBeVisible()
    expect(within(files).getByText(/先後順序不保證/)).toBeVisible()
  })

  it('憑證缺失時連到精靈的泊位 3，與探索頁同一塊', async () => {
    render({
      [SPY_PATH]: {
        body: media({
          problem: 'credential_missing',
          detail: 'a TMDB credential is required',
          fetched_at: null,
          seasons: [],
        }),
      },
    })
    renderApp('/media/tv:120089')

    const link = await screen.findByRole('link', { name: '前往設定精靈' })
    expect(link).toHaveAttribute('href', '/setup?berth=3')
  })
})
