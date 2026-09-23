import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Media, WatchArea, WatchEpisode } from '../api/media'
import type { SearchResults } from '../api/search'
import { HEALTHY, session, stubApi, type StubRoute } from '../test/fetch'
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
    overview_en: 'A spy, an assassin and a telepath keep house.',
    poster_url: 'https://image.tmdb.org/t/p/w342/spy.jpg',
    poster_url_en: 'https://image.tmdb.org/t/p/w342/spy-en.jpg',
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
    awaiting_review: 0,
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
    actions: ['import', 'extra', 'skip'],
    ...overrides,
  }
}

/**
 * 同一集兩個版本（brief §7.7）。**有版本群組就一定有正片**——版本區塊掛在「有正片」底下。
 *
 * 每個版本各帶自己的 `job_hash`：版本清單上的刪除按的就是那一筆（M2 票 04），多版本並存時
 * 要拿掉的是其中一個。
 */
const TWO_VERSIONS = {
  files: [ledgerFile()],
  versions: [
    {
      season: 1,
      episode_start: 1,
      episode_end: null,
      // 名字是 Jellyfin 算的（票 14b）：反查到的那一刻抄進帳本。
      versions: [
        {
          name: 'OPERATION STRIX [WEB][1080p][Lilith-Raws]',
          tags: '[WEB][1080p][Lilith-Raws]',
          job_hash: 'aaaa1111',
        },
        {
          name: 'OPERATION STRIX [BD][2160p][Sakurato]',
          tags: '[BD][2160p][Sakurato]',
          job_hash: 'bbbb2222',
        },
      ],
    },
  ],
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
              poster_url_en: '',
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

  it('標題層級不跳級：h1 之後的第一個區塊是 h2（票 15 audit）', async () => {
    render()
    renderApp('/media/tv:120089')
    await screen.findByRole('heading', { level: 1 })

    const levels = screen.getAllByRole('heading').map((heading) => Number(heading.tagName.slice(1)))
    for (const [index, level] of levels.entries()) {
      if (index > 0) expect(level - levels[index - 1]).toBeLessThanOrEqual(1)
    }
  })

  it('三個標題都在——英文那一個是檔名用的（brief §7.5）', async () => {
    render()
    renderApp('/media/tv:120089')

    expect(await screen.findByRole('heading', { name: 'SPY×FAMILY 間諜家家酒' })).toBeVisible()
    expect(screen.getByText('SPY x FAMILY')).toBeVisible()
    expect(screen.getByText('SPY×FAMILY')).toBeVisible()
  })

  it('切到 EN 時 h1 與簡介換成 en-US 那一輪，不另印中文，也不重抓（brief §7.5）', async () => {
    const api = render()
    renderApp('/media/tv:120089')
    await screen.findByRole('heading', { level: 1, name: 'SPY×FAMILY 間諜家家酒' })
    const fetched = api.mock.calls.length

    await userEvent.click(screen.getByRole('button', { name: 'EN' }))

    const heading = await screen.findByRole('heading', { level: 1, name: 'SPY x FAMILY' })
    // 標題那一組裡只印一次（搜尋區塊的關鍵字預覽裡也有這串字，那不算）。
    expect(within(heading.parentElement as HTMLElement).getAllByText('SPY x FAMILY')).toHaveLength(
      1,
    )
    expect(screen.getByText('A spy, an assassin and a telepath keep house.')).toBeVisible()
    expect(screen.queryByText('SPY×FAMILY 間諜家家酒')).not.toBeInTheDocument()
    expect(screen.queryByText('互相隱藏了真實身份的新家庭。')).not.toBeInTheDocument()
    // 原文標題與兩者都不同，照樣在：字幕組會把它寫進檔名。
    expect(screen.getByText('SPY×FAMILY')).toBeVisible()
    expect(api.mock.calls.length).toBe(fetched)
  })

  it('海報跟著 UI 語言換（TMDB 的海報分語言，票 11）', async () => {
    // 海報沒有 alt（標題就在旁邊），所以照它的網址找那一張。
    const poster = () =>
      document.querySelector<HTMLImageElement>('img[src^="https://image.tmdb.org/"]')
    render()
    renderApp('/media/tv:120089')
    await screen.findByRole('heading', { level: 1, name: 'SPY×FAMILY 間諜家家酒' })
    expect(poster()).toHaveAttribute('src', 'https://image.tmdb.org/t/p/w342/spy.jpg')

    await userEvent.click(screen.getByRole('button', { name: 'EN' }))

    await screen.findByRole('heading', { level: 1, name: 'SPY x FAMILY' })
    expect(poster()).toHaveAttribute('src', 'https://image.tmdb.org/t/p/w342/spy-en.jpg')
  })

  it('身分帶的海報與牆上是同一份 ArtSlot：srcset 給 TMDB 的四個寬度，sizes 照身分帶那一欄（票 13）', async () => {
    render()
    renderApp('/media/tv:120089')
    await screen.findByRole('heading', { level: 1, name: 'SPY×FAMILY 間諜家家酒' })

    const poster = document.querySelector('img[src="https://image.tmdb.org/t/p/w342/spy.jpg"]')

    expect(poster?.getAttribute('srcset')?.split(', ')).toEqual([
      'https://image.tmdb.org/t/p/w185/spy.jpg 185w',
      'https://image.tmdb.org/t/p/w342/spy.jpg 342w',
      'https://image.tmdb.org/t/p/w500/spy.jpg 500w',
      'https://image.tmdb.org/t/p/w780/spy.jpg 780w',
    ])
    expect(poster).toHaveAttribute('sizes', '(min-width: 640px) 11rem, 7rem')
  })

  it('海報載不下來時換成「無海報」，不留瀏覽器的破圖示（票 11 的 audit）', async () => {
    const poster = () =>
      document.querySelector<HTMLImageElement>('img[src^="https://image.tmdb.org/"]')
    render()
    renderApp('/media/tv:120089')
    await screen.findByRole('heading', { level: 1, name: 'SPY×FAMILY 間諜家家酒' })

    // 這一格是 TMDB 的海報：那一端的圖不在時瀏覽器就會發 error。
    fireEvent.error(poster()!)

    expect(await screen.findByText('無海報')).toBeVisible()
    expect(poster()).toBeNull()
  })

  it('EN 介面上 en-US 那一輪沒有簡介時就不印簡介，不改印中文的', async () => {
    render({ [SPY_PATH]: { body: media({ overview_en: '' }) } })
    renderApp('/media/tv:120089')
    await screen.findByRole('heading', { level: 1, name: 'SPY×FAMILY 間諜家家酒' })

    await userEvent.click(screen.getByRole('button', { name: 'EN' }))

    await screen.findByRole('heading', { level: 1, name: 'SPY x FAMILY' })
    expect(screen.queryByText('互相隱藏了真實身份的新家庭。')).not.toBeInTheDocument()
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

  it('季預設全收，收起的季不渲染集列，展開才畫、收起又拿掉（M1.5 票 09）', async () => {
    render()
    renderApp('/media/tv:120089')

    const season = await screen.findByText('Season 2')
    // 不是「在 DOM 裡但看不見」：一季 1213 集的表收起時仍在 DOM 裡，開頁就多上萬個節點（票 15 audit）。
    expect(screen.queryByText('FOLLOW MAMA AND PAPA')).not.toBeInTheDocument()

    await userEvent.click(season)
    expect(await screen.findByText('FOLLOW MAMA AND PAPA')).toBeVisible()

    await userEvent.click(season)
    await waitFor(() => expect(screen.queryByText('FOLLOW MAMA AND PAPA')).not.toBeInTheDocument())
  })

  it('展開的一季底端就收得起來，收起之後焦點回到那一季的摘要列（M1.5 票 09）', async () => {
    render()
    renderApp('/media/tv:120089')

    await userEvent.click(await screen.findByText('Season 2'))
    await userEvent.click(await screen.findByRole('button', { name: '收起 S02' }))

    await waitFor(() => expect(screen.queryByText('FOLLOW MAMA AND PAPA')).not.toBeInTheDocument())
    expect(screen.getByText('Season 2').closest('summary')).toHaveFocus()
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
    expect(await screen.findByText('2 季')).toBeVisible()
    expect(screen.getByText('37 集')).toBeVisible()
    // 但清單本身仍然列得出那一季——它是真的存在。
    expect(screen.getByText('Specials')).toBeVisible()
  })

  it('識別值說「首播」，值就是那個日期而不是一個年份', async () => {
    render()
    renderApp('/media/tv:120089')

    expect(await screen.findByText('首播 2022-04-09')).toBeVisible()
    expect(screen.getByText('TMDB 120089')).toBeVisible()
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
    expect(screen.queryByRole('button', { name: '只看缺集' })).not.toBeInTheDocument()
    expect(screen.getByText('100 分鐘')).toBeVisible()
    expect(screen.getByText('上映 2022-04-09')).toBeVisible()
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

  it('S00 的檔案說的是特別篇，不是正片（CONTEXT.md：Specials 是 TMDB season 0）', async () => {
    render({
      [SPY_PATH]: { body: media({ files: [ledgerFile({ season: 0, episode_start: 3 })] }) },
    })
    renderApp('/media/tv:120089')

    const files = await screen.findByRole('region', { name: '檔案與版本' })
    await userEvent.click(within(files).getByText('1 個檔案'))

    // 處置在組的摘要上說一次就夠（M1.5 票 09b：逐檔列不再重複）。
    expect(within(files).getAllByText('特別篇')).toHaveLength(1)
    expect(within(files).queryByText('正片')).toBeNull()
  })

  it('逐檔列：季集與檔名在外面，Tags 與完整路徑收在裡面（M1.5 票 09b）', async () => {
    render({ [SPY_PATH]: { body: media({ files: [ledgerFile()] }) } })
    renderApp('/media/tv:120089')

    const files = await screen.findByRole('region', { name: '檔案與版本' })
    await userEvent.click(within(files).getByText('1 個檔案'))

    const name = 'SPY x FAMILY (2022) - S01E01 - OPERATION STRIX [WEB][1080p][Lilith-Raws].mkv'
    const row = within(files).getByText(name).closest('li')!
    expect(within(row).getByText('S01E01')).toBeVisible()
    // 資料夾是整組共用的，所以外面只留檔名；完整路徑與 Tags 展開才有。
    expect(within(row).getByText(/^\/data\/library\/anime\/SPY x FAMILY/)).not.toBeVisible()
    expect(within(row).getByText('[WEB][1080p][Lilith-Raws]')).not.toBeVisible()
    // 常態的帳本與 Jellyfin 由組的摘要說（「帳本對得上」「Jellyfin 已收錄 1」），逐檔列不重複。
    expect(within(row).queryByText('正片')).not.toBeInTheDocument()
    expect(within(row).queryByText('對得上')).not.toBeInTheDocument()
    expect(within(row).queryByText('Jellyfin 已收錄')).not.toBeInTheDocument()

    await userEvent.click(within(row).getByText(name))

    expect(within(row).getByText(/^\/data\/library\/anime\/SPY x FAMILY/)).toBeVisible()
    expect(within(row).getByText('[WEB][1080p][Lilith-Raws]')).toBeVisible()
  })

  it('例外仍然逐列說得出來：帳本對不上，以及組的計數說不出的那幾格（M1.5 票 09b）', async () => {
    const soon = new Date(Date.now() + 3 * 60 * 1000).toISOString()
    render({
      [SPY_PATH]: {
        body: media({
          files: [
            ledgerFile({ id: 1, episode_start: 1 }),
            ledgerFile({ id: 2, episode_start: 2, status: 'target_missing' }),
            ledgerFile({ id: 3, episode_start: 3, presence: 'searching', resolve_after: soon }),
          ],
        }),
      },
    })
    renderApp('/media/tv:120089')

    const files = await screen.findByRole('region', { name: '檔案與版本' })
    await userEvent.click(within(files).getByText('3 個檔案'))

    const rows = within(files).getAllByRole('listitem')
    // 對得上的那一列什麼都不必說；對不上的那一列自己說。
    expect(within(rows[0]).queryByText(/對得上|對不上/)).not.toBeInTheDocument()
    expect(within(rows[1]).getByText('媒體庫裡的檔案不見了')).toBeVisible()
    // 「還在掃描」帶的是下一次什麼時候查——組的計數說不出這個，所以留在列上。
    expect(within(rows[2]).getByText(/Jellyfin 還在掃描/)).toBeVisible()
    expect(within(rows[2]).getByText(/3 分鐘/)).toBeVisible()
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

  describe('只看缺集（M1.5 票 09）', () => {
    const episode = media().seasons[0].episodes[0]

    /** 第一季：已入庫、缺、未播出各一集；第二季：只有一集卡住。 */
    function gappy() {
      const [first, second] = media().seasons
      return media({
        seasons: [
          {
            ...first,
            episodes: [
              episode,
              { ...episode, episode_number: 2, name: 'SECURE A WIFE', status: 'missing' },
              {
                ...episode,
                episode_number: 3,
                name: 'PREPARE FOR THE INTERVIEW',
                status: 'unaired',
              },
            ],
          },
          second,
        ],
      })
    }

    it('每一季說得出缺幾集；卡住、下載中、未播出都不算缺', async () => {
      render({ [SPY_PATH]: { body: gappy() } })
      renderApp('/media/tv:120089')
      const toggle = await screen.findByRole('button', { name: '只看缺集' })
      expect(toggle).toHaveAttribute('aria-pressed', 'false')

      await userEvent.click(toggle)

      expect(toggle).toHaveAttribute('aria-pressed', 'true')
      expect(screen.getByText('共缺 1 集')).toBeVisible()
      const first = screen.getByText('Season 1').closest('summary')!
      const second = screen.getByText('Season 2').closest('summary')!
      expect(within(first).getByText('缺 1 集')).toBeVisible()
      expect(within(second).getByText('沒有缺集')).toBeVisible()
    })

    it('展開的集表只留缺的那幾列；一季沒有缺集時說一句話，不畫一張空表', async () => {
      render({ [SPY_PATH]: { body: gappy() } })
      renderApp('/media/tv:120089')
      await userEvent.click(await screen.findByRole('button', { name: '只看缺集' }))

      await userEvent.click(screen.getByText('Season 1'))
      expect(await screen.findByText('SECURE A WIFE')).toBeVisible()
      expect(screen.queryByText('OPERATION STRIX')).not.toBeInTheDocument()
      expect(screen.queryByText('PREPARE FOR THE INTERVIEW')).not.toBeInTheDocument()

      await userEvent.click(screen.getByText('Season 2'))
      expect(await screen.findByText('這一季沒有缺集。')).toBeVisible()
      expect(screen.queryByText('FOLLOW MAMA AND PAPA')).not.toBeInTheDocument()

      // 關掉就是整張表，展開的季不因切換而收起。
      await userEvent.click(screen.getByRole('button', { name: '只看缺集' }))
      expect(screen.getByText('OPERATION STRIX')).toBeVisible()
      expect(screen.getByText('FOLLOW MAMA AND PAPA')).toBeVisible()
    })

    it('整部作品都沒有缺集時工具列說得出來', async () => {
      render()
      renderApp('/media/tv:120089')

      await userEvent.click(await screen.findByRole('button', { name: '只看缺集' }))

      expect(screen.getByText('這部作品沒有缺集')).toBeVisible()
    })

    it('還沒有任何一季的劇集沒有這顆切換鍵（電影見票 04 那一條）', async () => {
      render({ [SPY_PATH]: { body: media({ seasons: [] }) } })
      renderApp('/media/tv:120089')

      expect(await screen.findByText('TMDB 上這部作品還沒有任何一季。')).toBeVisible()
      expect(screen.queryByRole('button', { name: '只看缺集' })).not.toBeInTheDocument()
    })

    it('換一部作品時回到全部——它是這一部當下的視角，不跟著走（M1.5 票 09b）', async () => {
      const bear = media({ id: 'tv:136315', tmdb_id: 136315, title: 'The Bear' })
      render({
        [SPY_PATH]: { body: gappy() },
        'GET /api/media/tv%3A136315': { body: bear },
        'GET /api/search/queries?media=tv%3A136315': { body: { queries: ['The Bear'] } },
      })
      // 先去一趟把 The Bear 放進快取：**它已經在快取裡**才是這個 bug 的重現條件——沒有讀取中的
      // 空檔，季表就不會卸掉重掛，篩選會原封不動跟著過去。
      const { router } = renderApp('/media/tv:136315')
      expect(await screen.findByRole('heading', { level: 1, name: /The Bear/ })).toBeVisible()
      await router.navigate({ to: '/media/$mediaId', params: { mediaId: 'tv:120089' } })

      await userEvent.click(await screen.findByRole('button', { name: '只看缺集' }))
      expect(screen.getByRole('button', { name: '只看缺集' })).toHaveAttribute(
        'aria-pressed',
        'true',
      )

      // `/media/$mediaId` 是同一條路由，所以換作品時元件不重掛（少了 `key` 篩選就跟著過去）。
      await router.navigate({ to: '/media/$mediaId', params: { mediaId: 'tv:136315' } })

      expect(await screen.findByRole('heading', { level: 1, name: /The Bear/ })).toBeVisible()
      expect(screen.getByRole('button', { name: '只看缺集' })).toHaveAttribute(
        'aria-pressed',
        'false',
      )
    })
  })

  describe('缺集一鍵搜（M1.5 票 10）', () => {
    const MISSING_QUERIES = 'GET /api/search/queries?media=tv%3A120089&missing=true'
    const MISSING_SEARCH = 'GET /api/search?media=tv%3A120089&missing=true'

    /** 第一季：已入庫、缺、未播出各一集；第二季：只有一集卡住（缺集是零）。 */
    function gappy() {
      const [first, second] = media().seasons
      const episode = first.episodes[0]
      return media({
        seasons: [
          {
            ...first,
            episodes: [
              episode,
              { ...episode, episode_number: 2, name: 'SECURE A WIFE', status: 'missing' },
              { ...episode, episode_number: 3, name: 'PREPARE', status: 'unaired' },
            ],
          },
          second,
        ],
      })
    }

    function found(title: string): SearchResults {
      return {
        rows: [
          {
            title,
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
            season: 1,
            episode_start: 2,
            episode_end: 2,
            whole_season: false,
            strategy: 'explicit',
          },
        ],
        total: 1,
        discarded: 0,
        attempts: [{ step: 'SPY x FAMILY S01E02', status: 'ok', detail: '1', error: '' }],
        problem: null,
        detail: '',
      }
    }

    function gaps(extra: Record<string, StubRoute | (() => StubRoute)> = {}) {
      return render({
        [SPY_PATH]: { body: gappy() },
        [MISSING_QUERIES]: { body: { queries: ['SPY x FAMILY S01E02'] } },
        [MISSING_SEARCH]: { body: found('[ANi] SPY x FAMILY - 02 [1080P][Baha][CHT]') },
        ...extra,
      })
    }

    function panel() {
      return screen.getByRole('region', { name: '搜尋 torrent' })
    }

    function asked(stub: ReturnType<typeof stubApi>) {
      return stub.mock.calls.map(([input]) => String(input))
    }

    it('季表上有缺集時工具列有入口；沒有缺集的作品不畫（票 10 驗收）', async () => {
      gaps()
      renderApp('/media/tv:120089')

      expect(await screen.findByRole('button', { name: '搜這部作品缺的集' })).toBeVisible()
    })

    it('一集都不缺時那顆按鈕不在——沒有缺集就沒有這條路', async () => {
      render()
      renderApp('/media/tv:120089')

      expect(await screen.findByRole('button', { name: '只看缺集' })).toBeVisible()
      expect(screen.queryByRole('button', { name: '搜這部作品缺的集' })).not.toBeInTheDocument()
    })

    it('按下去用後端依缺集產生的查詢搜，預覽照實換成那幾個（票 10 驗收）', async () => {
      const stub = gaps()
      renderApp('/media/tv:120089')

      await userEvent.click(await screen.findByRole('button', { name: '搜這部作品缺的集' }))

      // 預覽的那幾個字由後端給（`/search/queries` 收同一組參數），不是前端自己拼的。
      expect(await within(panel()).findByText('這部作品缺的那幾集，Berth 會這樣問：')).toBeVisible()
      expect(asked(stub)).toContain('/api/search/queries?media=tv%3A120089&missing=true')
      expect(asked(stub)).toContain('/api/search?media=tv%3A120089&missing=true')
      // 結果照舊畫在這一區塊裡，不在季表那邊另開一張表（shape §4）。
      expect(await within(panel()).findByText(/\[ANi\] SPY x FAMILY - 02/)).toBeVisible()
    })

    it('按下去焦點落在搜尋區塊的標題上（結果畫在那裡，shape §4）', async () => {
      gaps()
      renderApp('/media/tv:120089')

      await userEvent.click(await screen.findByRole('button', { name: '搜這部作品缺的集' }))

      expect(screen.getByRole('heading', { level: 2, name: '搜尋 torrent' })).toHaveFocus()
    })

    it('一季的入口住在展開區裡、只搜那一季（The Summary Is One Button Rule）', async () => {
      const stub = gaps({
        'GET /api/search/queries?media=tv%3A120089&missing=true&season=1': {
          body: { queries: ['SPY x FAMILY S01E02'] },
        },
        'GET /api/search?media=tv%3A120089&missing=true&season=1': {
          body: found('[ANi] SPY x FAMILY - 02 [1080P][Baha][CHT]'),
        },
      })
      renderApp('/media/tv:120089')
      await userEvent.click(await screen.findByText('Season 1'))

      const entry = await screen.findByRole('button', { name: '搜 S01 缺的集' })
      expect(entry.closest('summary')).toBeNull()
      await userEvent.click(entry)

      expect(asked(stub)).toContain('/api/search?media=tv%3A120089&missing=true&season=1')
    })

    it('沒有缺集的那一季展開之後也沒有這顆按鈕', async () => {
      gaps()
      renderApp('/media/tv:120089')

      await userEvent.click(await screen.findByText('Season 2'))

      expect(await screen.findByText('FOLLOW MAMA AND PAPA')).toBeVisible()
      expect(screen.queryByRole('button', { name: '搜 S02 缺的集' })).not.toBeInTheDocument()
    })

    it('先打了關鍵字再按缺集，送出去的是缺集那幾個——不是那個關鍵字', async () => {
      // `q` 有值時後端只問那一個（票 08），所以舊的關鍵字跟著送出去 = 預覽說一套、問的是另一套。
      const stub = gaps()
      renderApp('/media/tv:120089')
      await userEvent.type(await screen.findByLabelText('關鍵字'), 'BDRip')

      await userEvent.click(screen.getByRole('button', { name: '搜這部作品缺的集' }))

      expect(asked(stub)).toContain('/api/search?media=tv%3A120089&missing=true')
      expect(asked(stub).filter((url) => url.includes('q=BDRip'))).toEqual([])
      expect(screen.getByLabelText('關鍵字')).toHaveValue('')
    })

    it('改回作品名搜尋：預覽換回那幾個名字，出口自己收起來', async () => {
      gaps()
      renderApp('/media/tv:120089')
      await userEvent.click(await screen.findByRole('button', { name: '搜這部作品缺的集' }))
      await within(panel()).findByText('這部作品缺的那幾集，Berth 會這樣問：')

      await userEvent.click(screen.getByRole('button', { name: '改回作品名搜尋' }))

      expect(await within(panel()).findByText('SPY x FAMILY')).toBeVisible()
      expect(screen.queryByRole('button', { name: '改回作品名搜尋' })).not.toBeInTheDocument()
    })
  })

  describe('檔案依決定分組（M1.5 票 09）', () => {
    /** 芙莉蓮那一包的形狀：S01 三集正片、第一集多一個字幕。 */
    function batch() {
      return [1, 2, 3].map((episode) =>
        ledgerFile({
          id: episode,
          episode_start: episode,
          target_path: `/data/library/anime/Frieren/Season 01/Frieren - S01E0${episode}.mkv`,
        }),
      )
    }

    it('一組一行：處置、蓋到的集、檔案數、帳本與 Jellyfin；逐檔要展開那一組才畫', async () => {
      render({
        [SPY_PATH]: {
          body: media({
            files: [
              ...batch(),
              ledgerFile({
                id: 9,
                action: 'subtitle',
                presence: 'none',
                target_path: '/data/library/anime/Frieren/Season 01/Frieren - S01E01.zh-TW.ass',
              }),
            ],
          }),
        },
      })
      renderApp('/media/tv:120089')

      const files = await screen.findByRole('region', { name: '檔案與版本' })
      const [videos, subtitles] = within(files)
        .getAllByText(/^\d+ 個檔案$/)
        .map((count) => count.closest('summary')!)
      expect(within(videos).getByText('正片')).toBeVisible()
      expect(within(videos).getByText('S01 E01–E03')).toBeVisible()
      expect(within(videos).getByText('3 個檔案')).toBeVisible()
      expect(within(videos).getByText('帳本對得上')).toBeVisible()
      expect(within(videos).getByText('Jellyfin 已收錄 3')).toBeVisible()
      // 字幕不查 Jellyfin，所以沒有那一格。
      expect(within(subtitles).getByText('字幕')).toBeVisible()
      expect(within(subtitles).getByText('S01 E01')).toBeVisible()
      expect(within(subtitles).queryByText(/Jellyfin/)).not.toBeInTheDocument()
      expect(within(files).queryAllByText(/Frieren - S01E02\.mkv/)).toHaveLength(0)

      await userEvent.click(within(videos).getByText('3 個檔案'))

      // 檔名出現兩次：摘要上那一段，以及收起來的完整路徑裡（M1.5 票 09b）。
      expect(within(files).getAllByText(/Frieren - S01E02\.mkv/)[0]).toBeVisible()
      await userEvent.click(within(files).getByRole('button', { name: '收起 正片 S01 E01–E03' }))
      await waitFor(() =>
        expect(within(files).queryAllByText(/Frieren - S01E02\.mkv/)).toHaveLength(0),
      )
    })

    it('帳本對不上或 Jellyfin 找不到的那一組排到最前面，摘要說得出幾個', async () => {
      render({
        [SPY_PATH]: {
          body: media({
            files: [
              ...batch(),
              ledgerFile({ id: 21, season: 2, episode_start: 1, presence: 'lost' }),
              ledgerFile({ id: 22, season: 2, episode_start: 2, status: 'target_missing' }),
              ledgerFile({ id: 23, season: 2, episode_start: 3, presence: 'searching' }),
            ],
          }),
        },
      })
      renderApp('/media/tv:120089')

      const files = await screen.findByRole('region', { name: '檔案與版本' })
      const first = within(files)
        .getAllByText(/^\d+ 個檔案$/)[0]
        .closest('summary')!

      expect(within(first).getByText('S02 E01–E03')).toBeVisible()
      expect(within(first).getByText('1 個帳本對不上')).toBeVisible()
      expect(within(first).getByText('Jellyfin 已收錄 1')).toBeVisible()
      expect(within(first).getByText('Jellyfin 掃描中 1')).toBeVisible()
      expect(within(first).getByText('Jellyfin 找不到 1')).toBeVisible()
    })

    it('電影的檔案一兩個，照舊逐檔攤開、不分組', async () => {
      render({
        'GET /api/media/movie%3A872585': {
          body: media({
            id: 'movie:872585',
            tmdb_id: 872585,
            kind: 'movie',
            seasons: [],
            files: [ledgerFile({ season: null, episode_start: null })],
          }),
        },
      })
      renderApp('/media/movie:872585')

      const files = await screen.findByRole('region', { name: '檔案與版本' })

      // 不分組，所以沒有組的收合鍵，檔案一打開頁面就在那裡。
      expect(within(files).queryByRole('button', { name: /^收起/ })).not.toBeInTheDocument()
      // 上面沒有任何一行摘要說過，所以這一列每一格都自己說（M1.5 票 09b）。
      expect(within(files).getByText('正片')).toBeVisible()
      expect(within(files).getByText('對得上')).toBeVisible()
      expect(within(files).getByText('Jellyfin 已收錄')).toBeVisible()
      // 長路徑仍然收在列裡，展開才有。
      expect(within(files).getByText(/^\/data\/library\/anime\/SPY x FAMILY/)).not.toBeVisible()

      await userEvent.click(
        within(files).getByText(/^SPY x FAMILY \(2022\) - S01E01 - OPERATION STRIX/),
      )

      expect(within(files).getByText(/^\/data\/library\/anime\/SPY x FAMILY/)).toBeVisible()
    })
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
          unmatched: [
            {
              rel_path: 'SP01.mkv',
              job_hash: 'a'.repeat(40),
              job_name: 'release',
              job_file_id: 7,
              actions: ['import', 'extra', 'skip'],
            },
          ],
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
              job_file_id: 7,
              actions: ['import', 'extra', 'skip'],
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
        body: media(TWO_VERSIONS),
      },
    })
    renderApp('/media/tv:120089')

    const files = await screen.findByRole('region', { name: '檔案與版本' })

    expect(within(files).getByText('多版本並存')).toBeVisible()
    expect(within(files).getByText('OPERATION STRIX [BD][2160p][Sakurato]')).toBeVisible()
    expect(within(files).getByText(/由 Jellyfin 決定/)).toBeVisible()
  })

  it('版本清單上每一個版本各有自己的刪除——要拿掉的是其中一個（M2 票 04）', async () => {
    // 刪除的對話框是**同一個元件**（plan §7）：`/jobs` 的展開區掛的是它，這裡也是。
    render({ [SPY_PATH]: { body: media(TWO_VERSIONS) } })
    renderApp('/media/tv:120089')

    const files = await screen.findByRole('region', { name: '檔案與版本' })

    expect(within(files).getAllByRole('button', { name: '刪除' })).toHaveLength(2)
  })

  it('一般使用者在版本清單上看不到刪除（M2 票 04 驗收）', async () => {
    // **前端隱藏不是安全機制**：擋住的那一條在門禁上（`DELETE /jobs/{hash}` 回 403）。
    render({ [SPY_PATH]: { body: media(TWO_VERSIONS) } }, 'user')
    renderApp('/media/tv:120089')

    const files = await screen.findByRole('region', { name: '檔案與版本' })

    expect(within(files).getByText('多版本並存')).toBeVisible()
    expect(within(files).queryByRole('button', { name: '刪除' })).toBeNull()
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

describe('觀看區（M1.5 票 08）', () => {
  const WATCH_PATH = 'GET /api/media/tv%3A120089/watch'
  const MOVIE_PATH = 'GET /api/media/movie%3A1241982'
  const MOVIE_WATCH_PATH = 'GET /api/media/movie%3A1241982/watch'
  const SERIES = '0b1a2c3d4e5f60718293a4b5c6d7e8f9'
  const SEASON_ONE = '1c2b3a4d5e6f708192a3b4c5d6e7f8a9'
  const SEASON_TWO = '2d3c4b5a6f7e8091a2b3c4d5e6f7a8b9'
  const FILM = '6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e'
  const JELLYFIN = { public_url: '', url: 'http://jf.example:8096', port: null }
  const UNWATCHED = { played: false, progress: null, unplayed_episodes: null }
  const EPISODES = (season: string) =>
    `GET /api/jellyfin/shows/${SERIES}/episodes?season_id=${season}`
  const PLAYED = (id: string) => `/api/jellyfin/items/${id}/played`

  function episode(number: number, overrides: Partial<WatchEpisode> = {}): WatchEpisode {
    return {
      item_id: `e${String(number).padStart(31, '0')}`,
      name: `Episode ${number}`,
      season: 2,
      episode_start: number,
      episode_end: null,
      watch: UNWATCHED,
      still_url: '',
      ...overrides,
    }
  }

  const RESUMING = episode(4, {
    watch: { ...UNWATCHED, progress: 18 },
    still_url: `/api/jellyfin/items/${episode(4).item_id}/images/Primary?size=wide&tag=f00`,
  })

  function area(overrides: Partial<WatchArea> = {}): WatchArea {
    return {
      item_id: SERIES,
      kind: 'tv',
      watch: { ...UNWATCHED, unplayed_episodes: 9 },
      carry_on: RESUMING,
      seasons: [
        { id: SEASON_ONE, name: 'Season 1', number: 1 },
        { id: SEASON_TWO, name: 'Season 2', number: 2 },
      ],
      jellyfin: JELLYFIN,
      ...overrides,
    }
  }

  function inJellyfin(routes: Record<string, StubRoute | (() => StubRoute)> = {}) {
    return render({
      [WATCH_PATH]: { body: area() },
      [EPISODES(SEASON_TWO)]: {
        body: [episode(3, { watch: { ...UNWATCHED, played: true } }), RESUMING, episode(5)],
      },
      [EPISODES(SEASON_ONE)]: { body: [episode(1, { season: 1 })] },
      ...routes,
    })
  }

  function calls(api: ReturnType<typeof render>, method: string, path: string) {
    return api.mock.calls.filter(
      ([url, init]) => url === path && (init?.method ?? 'GET') === method,
    )
  }

  function tile(name: string) {
    return screen.getByText(name).closest('article') as HTMLElement
  }

  it('主按鈕在簡介之前，開 Jellyfin 那一集、新分頁，下面一行說集名與看到哪', async () => {
    inJellyfin()
    renderApp('/media/tv:120089')

    const carryOn = await screen.findByRole('link', { name: /繼續看 S02E04/ })
    expect(carryOn).toHaveAttribute(
      'href',
      `http://jf.example:8096/web/#/details?id=${RESUMING.item_id}`,
    )
    expect(carryOn).toHaveAttribute('target', '_blank')
    expect(carryOn).toHaveAccessibleName(/開新分頁/)
    expect(carryOn).toHaveAccessibleDescription('Episode 4 · 看到 18%')
    const overview = screen.getByText('互相隱藏了真實身份的新家庭。')
    expect(
      carryOn.compareDocumentPosition(overview) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
  })

  it('在 Jellyfin 裡：觀看在最上，Berth 的那一半收到下面（使用者拍板：分層）', async () => {
    inJellyfin()
    renderApp('/media/tv:120089')
    await screen.findByRole('heading', { name: '觀看' })

    expect(screen.getAllByRole('heading', { level: 2 }).map((row) => row.textContent)).toEqual([
      '觀看',
      '搜尋 torrent',
      '季集與入庫',
      '檔案與版本',
    ])
    expect(screen.getByText('剩 9 集沒看')).toBeVisible()
  })

  it('不在 Jellyfin（或看不到）時沒有觀看區也沒有主按鈕，搜尋就在身分帶正下方', async () => {
    render({ [WATCH_PATH]: { body: null } })
    renderApp('/media/tv:120089')
    await screen.findByRole('heading', { level: 1 })
    await waitFor(() => expect(screen.getByRole('button', { name: '搜尋' })).toBeVisible())

    expect(screen.getAllByRole('heading', { level: 2 }).map((row) => row.textContent)).toEqual([
      '搜尋 torrent',
      '季集與入庫',
      '檔案與版本',
    ])
    expect(screen.queryByRole('link', { name: /繼續看|看下一集|開始看/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /在 Jellyfin/ })).not.toBeInTheDocument()
  })

  it('季切換預設是主按鈕那一集所在的季；換季才問那一季的集', async () => {
    const api = inJellyfin()
    renderApp('/media/tv:120089')

    const seasons = await screen.findByRole('group', { name: '季' })
    expect(within(seasons).getByRole('button', { name: 'Season 2' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(await screen.findByText('Episode 5')).toBeVisible()
    expect(calls(api, 'GET', EPISODES(SEASON_ONE).slice(4))).toHaveLength(0)

    await userEvent.click(within(seasons).getByRole('button', { name: 'Season 1' }))

    expect(await screen.findByText('Episode 1')).toBeVisible()
    expect(within(seasons).getByRole('button', { name: 'Season 1' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(calls(api, 'GET', EPISODES(SEASON_ONE).slice(4))).toHaveLength(1)
  })

  it('一集一格：劇照、季集代號、集名、看到哪；主按鈕那一集帶「繼續看」，點下去開那一集', async () => {
    inJellyfin()
    renderApp('/media/tv:120089')

    await screen.findByText('Episode 5')
    const resuming = tile('Episode 4')
    expect(within(resuming).getByText('S02E04')).toBeVisible()
    expect(within(resuming).getByText('繼續看')).toBeVisible()
    expect(within(resuming).getByText('看到 18%')).toBeVisible()
    expect(resuming.querySelector('img')).toHaveAttribute('src', RESUMING.still_url)
    expect(within(resuming).getByRole('link')).toHaveAttribute(
      'href',
      `http://jf.example:8096/web/#/details?id=${RESUMING.item_id}`,
    )
    // 沒有劇照的集不借劇的圖：整季一模一樣的圖沒辦法用來挑集。
    expect(within(tile('Episode 5')).getByText('無圖')).toBeVisible()
    expect(within(tile('Episode 3')).getByText('已看')).toBeVisible()
  })

  it('沒有進度的集一按就標為已看：那一格就地換，主按鈕重問，那一季不重抓', async () => {
    const api = inJellyfin({
      [`POST ${PLAYED(episode(5).item_id)}`]: { body: { ...UNWATCHED, played: true } },
    })
    renderApp('/media/tv:120089')
    await screen.findByText('Episode 5')
    const seasons = calls(api, 'GET', EPISODES(SEASON_TWO).slice(4)).length
    const areas = calls(api, 'GET', WATCH_PATH.slice(4)).length

    const mark = within(tile('Episode 5')).getByRole('button', { name: /^標為已看/ })
    // 每一格都有這一顆：名字帶上集號與集名（票 13），控制項清單裡分得出是哪一集。
    expect(mark).toHaveAccessibleName(/^標為已看：S\d\dE05 Episode 5$/)
    // 開 Jellyfin 的那一塊也是：沒有劇照的集，圖位的「無圖」不進名字，看到哪是描述。
    const open = within(tile('Episode 5')).getByRole('link')
    expect(open).toHaveAccessibleName(/^S\d\dE05 Episode 5（開新分頁）$/)
    expect(open.closest('ul')?.tagName).toBe('UL')
    await userEvent.click(mark)

    expect(await within(tile('Episode 5')).findByText('已看')).toBeVisible()
    expect(calls(api, 'POST', PLAYED(episode(5).item_id))).toHaveLength(1)
    await waitFor(() => expect(calls(api, 'GET', WATCH_PATH.slice(4)).length).toBe(areas + 1))
    expect(calls(api, 'GET', EPISODES(SEASON_TWO).slice(4))).toHaveLength(seasons)
  })

  it('看到一半的集標為已看先確認：說得出會清掉看到幾 % 的位置', async () => {
    const api = inJellyfin()
    renderApp('/media/tv:120089')
    await screen.findByText('Episode 5')
    const resuming = tile('Episode 4')

    await userEvent.click(within(resuming).getByRole('button', { name: /^標為已看/ }))

    const confirm = within(resuming).getByRole('group')
    expect(confirm).toHaveAccessibleName(/18%.*位置.*找不回來/)
    expect(confirm).toHaveFocus()
    await userEvent.click(within(confirm).getByRole('button', { name: '取消' }))
    expect(calls(api, 'POST', PLAYED(RESUMING.item_id))).toHaveLength(0)
  })

  it('電影：主按鈕說繼續看與看到幾 %，旁邊一顆標為已看；沒有觀看區', async () => {
    render({
      [MOVIE_PATH]: {
        body: media({
          id: 'movie:1241982',
          tmdb_id: 1241982,
          kind: 'movie',
          title: '海洋奇緣2',
          title_en: 'Moana 2',
          title_original: 'Moana 2',
          runtime: 100,
          seasons: [],
        }),
      },
      [MOVIE_WATCH_PATH]: {
        body: area({
          item_id: FILM,
          kind: 'movie',
          watch: { ...UNWATCHED, progress: 42 },
          carry_on: null,
          seasons: [],
        }),
      },
      'GET /api/search/queries?media=movie%3A1241982': { body: { queries: ['Moana 2'] } },
    })
    renderApp('/media/movie:1241982')

    const carryOn = await screen.findByRole('link', { name: /繼續看/ })
    expect(carryOn).toHaveAttribute('href', `http://jf.example:8096/web/#/details?id=${FILM}`)
    expect(carryOn).toHaveAccessibleDescription('看到 42%')
    await userEvent.click(screen.getByRole('button', { name: /^標為已看/ }))
    expect(screen.getByRole('group', { name: /42%.*位置/ })).toHaveFocus()
    expect(screen.queryByRole('heading', { name: '觀看' })).not.toBeInTheDocument()
  })

  it('劇集全部看完時主按鈕開那部劇，說全部看完了', async () => {
    inJellyfin({
      [WATCH_PATH]: {
        body: area({ watch: { ...UNWATCHED, played: true }, carry_on: null }),
      },
    })
    renderApp('/media/tv:120089')

    const open = await screen.findByRole('link', {
      name: /^在 Jellyfin 開啟/,
      description: '全部看完了',
    })
    expect(open).toHaveAttribute('href', `http://jf.example:8096/web/#/details?id=${SERIES}`)
    // 沒有下一集時選第一個正片季。
    expect(
      within(screen.getByRole('group', { name: '季' })).getByRole('button', { name: 'Season 1' }),
    ).toHaveAttribute('aria-pressed', 'true')
  })

  it('不知道 Jellyfin 開在哪裡時不給一條死連結', async () => {
    inJellyfin({
      [WATCH_PATH]: { body: area({ jellyfin: { public_url: '', url: '', port: null } }) },
    })
    renderApp('/media/tv:120089')

    expect(await screen.findAllByText('不知道 Jellyfin 開在哪裡')).not.toHaveLength(0)
    expect(screen.queryByRole('link', { name: /繼續看/ })).not.toBeInTheDocument()
  })

  it('Jellyfin 問不到時觀看區換成一行字與重試，搜尋照樣在', async () => {
    const api = render({
      [WATCH_PATH]: {
        status: 503,
        body: {
          detail: { reason: 'jellyfin_unreachable', detail: 'GET /Items: connection refused' },
        },
      },
    })
    renderApp('/media/tv:120089')

    expect(await screen.findByText('問不到 Jellyfin，觀看區暫時看不到。')).toBeVisible()
    expect(screen.getByText('GET /Items: connection refused')).toBeVisible()
    expect(screen.getByRole('button', { name: '搜尋' })).toBeVisible()
    const asked = calls(api, 'GET', WATCH_PATH.slice(4)).length
    await userEvent.click(screen.getByRole('button', { name: '重試' }))
    await waitFor(() => expect(calls(api, 'GET', WATCH_PATH.slice(4)).length).toBe(asked + 1))
  })

  it('看過的集標為未看先確認：說得出清掉的是這一集的次數與時間', async () => {
    const api = inJellyfin()
    renderApp('/media/tv:120089')
    await screen.findByText('Episode 5')
    const watched = tile('Episode 3')

    await userEvent.click(within(watched).getByRole('button', { name: /^標為未看/ }))

    const confirm = within(watched).getByRole('group')
    expect(confirm).toHaveAccessibleName(/這一集.*觀看次數.*最後觀看時間.*找不回來/)
    expect(confirm).not.toHaveAccessibleName(/每一集/)
    await userEvent.click(within(confirm).getByRole('button', { name: '取消' }))
    expect(calls(api, 'DELETE', PLAYED(episode(3).item_id))).toHaveLength(0)
  })

  it('沒有下一集但還沒看完（只剩特別篇或缺片）時不說「全部看完了」', async () => {
    inJellyfin({ [WATCH_PATH]: { body: area({ carry_on: null }) } })
    renderApp('/media/tv:120089')

    // 主按鈕與觀看區標題列各一條，主按鈕在前；兩條都沒有描述。
    const [open] = await screen.findAllByRole('link', { name: /^在 Jellyfin 開啟/ })
    expect(open).not.toHaveAttribute('aria-describedby')
    expect(open).toHaveAttribute('href', `http://jf.example:8096/web/#/details?id=${SERIES}`)
    expect(screen.queryByText('全部看完了')).not.toBeInTheDocument()
    expect(screen.getByText('剩 9 集沒看')).toBeVisible()
  })

  it('沒看過的電影：主按鈕下面沒有那一行，切換鍵也不指向一個不存在的描述', async () => {
    render({
      [MOVIE_PATH]: {
        body: media({ id: 'movie:1241982', tmdb_id: 1241982, kind: 'movie', seasons: [] }),
      },
      [MOVIE_WATCH_PATH]: {
        body: area({ item_id: FILM, kind: 'movie', watch: UNWATCHED, carry_on: null, seasons: [] }),
      },
      'GET /api/search/queries?media=movie%3A1241982': { body: { queries: ['Moana 2'] } },
    })
    renderApp('/media/movie:1241982')

    expect(await screen.findByRole('link', { name: /在 Jellyfin 看/ })).toBeVisible()
    expect(screen.getByRole('button', { name: /^標為已看/ })).not.toHaveAttribute(
      'aria-describedby',
    )
  })

  it('帳號在 Jellyfin 被停用時送回登入頁', async () => {
    const account = session({ name: 'deckhand', role: 'user' })
    stubApi({
      'GET /api/health': { body: HEALTHY },
      'GET /api/auth/me': account.me,
      [SPY_PATH]: { body: media() },
      'GET /api/search/queries?media=tv%3A120089': { body: { queries: ['SPY x FAMILY'] } },
      [WATCH_PATH]: () => {
        account.signOut()
        return { status: 401, body: { detail: { reason: 'account_disabled', detail: '' } } }
      },
    })
    const { router } = renderApp('/media/tv:120089')

    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
  })
})

describe('停在待審核的下載（M2 票 06）', () => {
  it('一般使用者看得到「等管理員審核」', async () => {
    render({ [SPY_PATH]: { body: media({ awaiting_review: 1 }) } }, 'user')
    renderApp('/media/tv:120089')

    expect(
      await screen.findByText('這部作品有 1 筆下載停在待審核，等管理員審核。'),
    ).toBeInTheDocument()
  })

  it('admin 不畫那一句', async () => {
    render({ [SPY_PATH]: { body: media({ awaiting_review: 1 }) } })
    renderApp('/media/tv:120089')

    await screen.findByRole('heading', { level: 1 })
    expect(screen.queryByText(/等管理員審核/)).not.toBeInTheDocument()
  })

  it('沒有停下來的下載時什麼都不說', async () => {
    render({}, 'user')
    renderApp('/media/tv:120089')

    await screen.findByRole('heading', { level: 1 })
    expect(screen.queryByText(/等管理員審核/)).not.toBeInTheDocument()
  })
})

describe('修正一個檔案（M2 票 08）', () => {
  const UNMATCHED = {
    rel_path: '[Group] SPY×FAMILY/[Group] SPY×FAMILY OVA 2 [1080p].mkv',
    job_hash: '4bd0f6ef1d3b1e3cbb1e1b6b6c2a9c7d8e5f0a1b',
    job_name: '[Group] SPY×FAMILY S01 [01-25][1080p][CHT]',
    job_file_id: 7,
    actions: ['import', 'extra', 'skip'] as LedgerFile['actions'],
  }

  /** 電影不分組，檔案列直接在外面；點檔名就展開那一列。 */
  const FILE_NAME = 'SPY x FAMILY (2022) - S01E01 - OPERATION STRIX [WEB][1080p][Lilith-Raws].mkv'

  function bodyOf(stub: ReturnType<typeof render>, url: string): unknown {
    const call = stub.mock.calls.find(([called]) => called === url)
    return call ? JSON.parse(String(call[1]?.body)) : undefined
  }

  it('對不到的檔案：「修正」展開與審核佇列同一個表單，打同一支（帶 job_file_id）', async () => {
    const stub = render({
      [SPY_PATH]: { body: media({ unmatched: [UNMATCHED] }) },
      'POST /api/files/rematch': { body: { plan_id: 3, target_path: '/x/S00E02.mkv' } },
    })
    renderApp('/media/tv:120089')
    const files = await screen.findByRole('region', { name: '檔案與版本' })

    await userEvent.click(within(files).getByRole('button', { name: `修正 ${UNMATCHED.rel_path}` }))
    await userEvent.type(within(files).getByRole('spinbutton', { name: '季' }), '0')
    await userEvent.type(within(files).getByRole('spinbutton', { name: '起集' }), '2')
    await userEvent.click(within(files).getByRole('button', { name: '套用' }))

    await waitFor(() =>
      expect(bodyOf(stub, '/api/files/rematch')).toEqual({
        job_file_id: 7,
        action: 'import',
        season: 0,
        episode_start: 2,
        episode_end: null,
      }),
    )
    expect(await within(files).findByText('已修正。')).toBeInTheDocument()
  })

  it('已入庫的檔案：「修正」收在展開區，改指派先就地確認再送（帶 ledger_id）', async () => {
    const stub = render({
      [SPY_PATH]: { body: media({ kind: 'movie', files: [ledgerFile({ id: 42 })] }) },
      'POST /api/files/rematch': { body: { plan_id: 3, target_path: '' } },
    })
    renderApp('/media/tv:120089')
    const files = await screen.findByRole('region', { name: '檔案與版本' })

    await userEvent.click(within(files).getByText(FILE_NAME))
    await userEvent.click(within(files).getByRole('button', { name: /^修正 / }))
    await userEvent.selectOptions(within(files).getByRole('combobox', { name: '改成' }), 'skip')
    await userEvent.click(within(files).getByRole('button', { name: '套用' }))

    // 還沒送：它在媒體庫裡，拿掉之前先說清楚。
    expect(stub.mock.calls.some(([url]) => url === '/api/files/rematch')).toBe(false)
    expect(within(files).getByText(/這會從媒體庫拿掉它/)).toBeInTheDocument()
    await userEvent.click(within(files).getByRole('button', { name: '確定修正' }))

    await waitFor(() =>
      expect(bodyOf(stub, '/api/files/rematch')).toMatchObject({ ledger_id: 42, action: 'skip' }),
    )
  })

  it('字幕沒有自己的修正入口：它跟著它的影片走', async () => {
    render({
      [SPY_PATH]: {
        body: media({ kind: 'movie', files: [ledgerFile({ action: 'subtitle', actions: [] })] }),
      },
    })
    renderApp('/media/tv:120089')
    const files = await screen.findByRole('region', { name: '檔案與版本' })

    await userEvent.click(within(files).getByText(FILE_NAME))

    expect(within(files).queryByRole('button', { name: /^修正 / })).toBeNull()
  })

  it('一般使用者看不到修正入口（票上那一條驗收）', async () => {
    // **前端隱藏不是安全機制**：擋住的那一條在門禁上（`/files/*` 回 403）。
    render(
      {
        [SPY_PATH]: {
          body: media({ kind: 'movie', unmatched: [UNMATCHED], files: [ledgerFile()] }),
        },
      },
      'user',
    )
    renderApp('/media/tv:120089')
    const files = await screen.findByRole('region', { name: '檔案與版本' })

    await userEvent.click(within(files).getByText(FILE_NAME))

    expect(within(files).getByText('對不到的檔案')).toBeVisible()
    expect(within(files).queryByRole('button', { name: /^修正/ })).toBeNull()
  })

  it('那一份計劃還在等審核時不給修正，說一句去哪裡', async () => {
    render({ [SPY_PATH]: { body: media({ unmatched: [{ ...UNMATCHED, actions: [] }] }) } })
    renderApp('/media/tv:120089')
    const files = await screen.findByRole('region', { name: '檔案與版本' })

    expect(within(files).queryByRole('button', { name: /^修正/ })).toBeNull()
    expect(within(files).getByText(/到審核佇列決定/)).toBeVisible()
  })
})
