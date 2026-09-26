import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { stubApi } from '../test/fetch'
import { renderWithProviders } from '../test/render'
import {
  ALL_BUNDLED,
  SEQUENCE_DONE,
  detection,
  jellyfinSetup,
  library,
  setupStatus,
  step,
} from '../test/fixtures'
import { SetupPage } from './SetupPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

const STATUS = 'GET /api/setup/status'
const JELLYFIN = 'GET /api/setup/jellyfin'
const BOOTSTRAP = 'POST /api/setup/jellyfin/bootstrap'
const CONNECT = 'POST /api/setup/jellyfin/connect'
const PATHS = 'POST /api/setup/jellyfin/libraries/paths'
const SAVE = 'PUT /api/setup/jellyfin/bundled'

/** 送出去的每一份清單，依序（票 06f）。 */
function savedLists(fetchStub: ReturnType<typeof stubApi>): unknown[] {
  return fetchStub.mock.calls
    .filter(([url, init]) => url === '/api/setup/jellyfin/bundled' && init?.method === 'PUT')
    .map(([, init]) => JSON.parse(String(init?.body)) as unknown)
}

/** 比停手存檔的等待再久一點：拿來證明「沒有存」。 */
function quietFor(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/** 第 1–2 步都做完了，精靈在泊位 1。 */
const AT_BERTH_ONE = setupStatus({
  current_step: 3,
  admin_created: true,
  admin_username: 'skipper',
  services: ALL_BUNDLED,
})

const NAS = setupStatus({
  ...AT_BERTH_ONE,
  services: [
    detection({ origin: 'existing', reason: 'setup_completed', detail: '12.0.0' }),
    ...ALL_BUNDLED.slice(1),
  ],
})

describe('泊位 1：套件內 Jellyfin', () => {
  it('剖面在按之前就列出七支端點', async () => {
    stubApi({ [STATUS]: { body: AT_BERTH_ONE }, [JELLYFIN]: { body: jellyfinSetup() } })

    renderWithProviders(<SetupPage />)
    // 剖面是那份 `dl`；序列裡的每一條纜繩也標著自己的端點，所以要限定在剖面內找。
    const cutaway = (await screen.findByText('將會做什麼')).closest('section')!

    expect(within(cutaway).getByText('POST /Startup/User')).toBeInTheDocument()
    expect(within(cutaway).getByText('POST /Library/VirtualFolders')).toBeInTheDocument()
    expect(within(cutaway).getByText('POST /Auth/Keys')).toBeInTheDocument()
    expect(within(cutaway).getByText('建立清單上的媒體庫')).toBeInTheDocument()
    // 12.x 原生合併多版本，序列裡沒有「裝插件」也沒有「重啟」（票 14b）。
    expect(within(cutaway).queryByText('POST /Packages/Installed')).not.toBeInTheDocument()
  })

  it('按下靠泊之後逐條纜繩留下實測值', async () => {
    const fetchStub = stubApi({
      [STATUS]: { body: AT_BERTH_ONE },
      [JELLYFIN]: { body: jellyfinSetup() },
      [SAVE]: { body: jellyfinSetup() },
      [BOOTSTRAP]: { body: jellyfinSetup({ steps: SEQUENCE_DONE, api_key_present: true }) },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await user.click(await screen.findByRole('button', { name: '開始靠泊' }))

    const sequence = await screen.findByTestId('sequence')
    await waitFor(() => expect(within(sequence).getAllByText('已完成')).toHaveLength(7))
    expect(within(sequence).getByText('Movies · TV · Anime')).toBeInTheDocument()
    expect(within(sequence).getByText('12.1.0')).toBeInTheDocument()
    expect(fetchStub.mock.calls.some(([url]) => url === '/api/setup/jellyfin/bootstrap')).toBe(true)
  })

  it('重按之後已經對的那幾步標成「已經是這樣」', async () => {
    stubApi({
      [STATUS]: { body: AT_BERTH_ONE },
      [JELLYFIN]: {
        body: jellyfinSetup({
          api_key_present: true,
          version: '12.1.0',
          steps: [
            step('public_info', 'ok', '12.1.0'),
            ...SEQUENCE_DONE.slice(1).map((row) => ({ ...row, status: 'skipped' as const })),
          ],
        }),
      },
    })

    renderWithProviders(<SetupPage />)
    const sequence = await screen.findByTestId('sequence')

    await waitFor(() => expect(within(sequence).getAllByText('已經是這樣')).toHaveLength(6))
    expect(screen.getByRole('button', { name: '重新跑一次' })).toBeInTheDocument()
  })

  it('失敗的那一步就地變紅，附原文與可複製的手動步驟', async () => {
    stubApi({
      [STATUS]: { body: AT_BERTH_ONE },
      [JELLYFIN]: {
        body: jellyfinSetup({
          steps: [
            ...SEQUENCE_DONE.slice(0, 3),
            step('libraries', 'failed', '', 'POST /Library/VirtualFolders: 500'),
            step('remote_access', 'pending'),
            step('complete', 'pending'),
            step('api_key', 'pending'),
          ],
        }),
      },
    })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByText(/POST \/Library\/VirtualFolders: 500/)).toBeInTheDocument()
    expect(screen.getByText('http://jellyfin:8096/web/#/dashboard/libraries')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '重試失敗的那一步' })).toBeInTheDocument()
    const sequence = screen.getByTestId('sequence')
    // 失敗那一步之後的都沒跑到——序列停在那裡，而不是跳過它繼續。
    expect(within(sequence).getAllByText('尚未執行')).toHaveLength(3)
  })

  it('版本低於 12 時說出目前版本與升級前要做的事', async () => {
    stubApi({
      [STATUS]: { body: AT_BERTH_ONE },
      [JELLYFIN]: {
        body: jellyfinSetup({
          version: '10.11.11',
          version_supported: false,
          steps: [
            step('public_info', 'failed', '10.11.11', 'Jellyfin 10.11.11 is older than 12.0'),
          ],
        }),
      },
    })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByText(/這台 Jellyfin 是 10.11.11/)).toBeInTheDocument()
    expect(screen.getByText(/完整備份/)).toBeInTheDocument()
    expect(screen.getByText(/移除第三方插件/)).toBeInTheDocument()
  })

  it('泊位板在精靈前進之後把 BTH 1 標成已繫上', async () => {
    stubApi({
      [STATUS]: { body: setupStatus({ ...AT_BERTH_ONE, current_step: 4 }) },
      [JELLYFIN]: { body: jellyfinSetup({ steps: SEQUENCE_DONE, api_key_present: true }) },
    })

    renderWithProviders(<SetupPage />)
    const board = await screen.findByRole('region', { name: '泊位板' })

    await waitFor(() =>
      // 走過的那一格是按鈕（票 06d），漆塗在按鈕上。
      expect(within(board).getByText('BTH 1').closest('button')).toHaveClass('bg-secured'),
    )
  })
})

describe('泊位 1：套件內 Jellyfin 的媒體庫清單（票 06f）', () => {
  it('改名、改類型、改資料夾、刪列、加列，停手就存下來', async () => {
    const fetchStub = stubApi({
      [STATUS]: { body: AT_BERTH_ONE },
      [JELLYFIN]: { body: jellyfinSetup() },
      [SAVE]: { body: jellyfinSetup() },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    const movies = await screen.findByRole('group', { name: 'Movies' })
    const name = within(movies).getByLabelText('名稱')
    await user.clear(name)
    await user.type(name, '電影')
    // 名稱不是 ASCII：資料夾不替他推導，要自己填。
    expect(within(movies).getByLabelText('資料夾')).toHaveValue('')
    expect(within(movies).getByText('名稱不是英文字母時，資料夾要自己填。')).toBeInTheDocument()
    await user.type(within(movies).getByLabelText('資料夾'), 'films')
    expect(within(movies).getByText('/data/library/films')).toBeInTheDocument()
    // 自己填過的資料夾，之後再改名也不會被推導蓋掉。
    await user.type(name, '院線')
    expect(within(movies).getByLabelText('資料夾')).toHaveValue('films')
    await user.click(screen.getByRole('button', { name: '移除「Anime」' }))
    await user.click(screen.getByRole('button', { name: '加一個媒體庫' }))
    const added = screen.getByRole('group', { name: '第 3 個媒體庫' })
    expect(within(added).getByLabelText('名稱')).toHaveFocus()
    await user.type(within(added).getByLabelText('名稱'), 'Docs')
    // ASCII 的名稱：資料夾跟著推導。
    expect(within(added).getByLabelText('資料夾')).toHaveValue('docs')
    await user.selectOptions(within(added).getByLabelText('內容類型'), '電影')

    await waitFor(
      () =>
        expect(savedLists(fetchStub).at(-1)).toEqual({
          libraries: [
            { name: '電影院線', collection_type: 'movies', folder: 'films' },
            { name: 'TV', collection_type: 'tvshows', folder: 'tv' },
            { name: 'Docs', collection_type: 'movies', folder: 'docs' },
          ],
        }),
      { timeout: 3000 },
    )
  })

  it('刪掉一列之後，焦點落在原本那個位置現在的那一列', async () => {
    stubApi({
      [STATUS]: { body: AT_BERTH_ONE },
      [JELLYFIN]: { body: jellyfinSetup() },
      [SAVE]: { body: jellyfinSetup() },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await screen.findByRole('group', { name: 'Movies' })
    await user.click(screen.getByRole('button', { name: '移除「TV」' }))

    expect(screen.getByRole('article', { name: 'Anime' })).toHaveFocus()
  })

  it('重名、重複資料夾、跳出根目錄、空清單各有擋下的說法，而且不存、不讓靠泊', async () => {
    const fetchStub = stubApi({
      [STATUS]: { body: AT_BERTH_ONE },
      [JELLYFIN]: { body: jellyfinSetup() },
      [SAVE]: { body: jellyfinSetup() },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    const tv = await screen.findByRole('group', { name: 'TV' })
    await user.clear(within(tv).getByLabelText('名稱'))
    // 不分大小寫；資料夾跟著名稱推導，所以它也撞上了。
    await user.type(within(tv).getByLabelText('名稱'), 'MOVIES')
    const anime = screen.getByRole('group', { name: 'Anime' })
    await user.clear(within(anime).getByLabelText('資料夾'))
    await user.type(within(anime).getByLabelText('資料夾'), '../anime')

    expect(within(tv).getByText('名稱重複了（不分大小寫）。')).toBeInTheDocument()
    expect(within(tv).getByText(/資料夾重複了/)).toBeInTheDocument()
    expect(within(anime).getByText(/資料夾是媒體庫根目錄底下的一層/)).toBeInTheDocument()
    expect(within(anime).getByLabelText('資料夾')).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByRole('button', { name: '開始靠泊' })).toBeDisabled()
    expect(screen.getByText('清單有標紅的格子，改好才能靠泊。')).toBeInTheDocument()

    for (const row of ['Movies', 'MOVIES', 'Anime']) {
      await user.click(screen.getByRole('button', { name: `移除「${row}」` }))
    }

    expect(screen.getByText('至少要一個媒體庫。')).toBeInTheDocument()
    await quietFor(900)
    expect(savedLists(fetchStub)).toEqual([])
  })

  it('按下靠泊先存剖面上的那一份，再跑序列', async () => {
    const fetchStub = stubApi({
      [STATUS]: { body: AT_BERTH_ONE },
      [JELLYFIN]: { body: jellyfinSetup() },
      [SAVE]: { body: jellyfinSetup() },
      [BOOTSTRAP]: { body: jellyfinSetup({ steps: SEQUENCE_DONE, api_key_present: true }) },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    const anime = await screen.findByRole('group', { name: 'Anime' })
    await user.click(within(anime).getByRole('button', { name: '移除「Anime」' }))
    await user.click(screen.getByRole('button', { name: '開始靠泊' }))

    await waitFor(() =>
      expect(fetchStub.mock.calls.map(([url]) => url)).toContain('/api/setup/jellyfin/bootstrap'),
    )
    const urls = fetchStub.mock.calls.map(([url]) => url)
    expect(urls.indexOf('/api/setup/jellyfin/bundled')).toBeLessThan(
      urls.indexOf('/api/setup/jellyfin/bootstrap'),
    )
    expect(savedLists(fetchStub)[0]).toEqual({
      libraries: [
        { name: 'Movies', collection_type: 'movies', folder: 'movies' },
        { name: 'TV', collection_type: 'tvshows', folder: 'tv' },
      ],
    })
  })

  it('建好的那幾列鎖住，說出要去 Jellyfin 改；還沒建的照樣能改', async () => {
    stubApi({
      [STATUS]: { body: setupStatus({ ...AT_BERTH_ONE, current_step: 4 }) },
      [JELLYFIN]: {
        body: jellyfinSetup({
          steps: SEQUENCE_DONE,
          api_key_present: true,
          bundled: [
            { name: '電影', collection_type: 'movies', folder: 'films', built: true },
            { name: 'TV', collection_type: 'tvshows', folder: 'tv', built: true },
            { name: '紀錄片', collection_type: 'movies', folder: 'docs', built: false },
          ],
        }),
      },
    })

    // 精靈已經走到第 4 步；從泊位板回頭看泊位 1。
    renderWithProviders(<SetupPage />)
    const board = await screen.findByRole('region', { name: '泊位板' })
    await userEvent.click(await within(board).findByRole('button', { name: /BTH 1/ }))
    const list = (await screen.findByRole('heading', { name: '要建的媒體庫' })).closest('section')!

    expect(within(list).getAllByText('已建立')).toHaveLength(2)
    expect(within(list).getByText('/data/library/films')).toBeInTheDocument()
    expect(within(list).queryByRole('group', { name: '電影' })).not.toBeInTheDocument()
    expect(within(list).queryByRole('button', { name: '移除「電影」' })).not.toBeInTheDocument()
    expect(within(list).getByText(/到 Jellyfin 的「控制台 → 媒體庫」/)).toBeInTheDocument()
    const documentaries = within(list).getByRole('group', { name: '紀錄片' })
    expect(within(documentaries).getByLabelText('名稱')).toBeEnabled()
    expect(screen.getByText(/Jellyfin 有 Berth 管理員、2 個媒體庫/)).toBeInTheDocument()
  })

  it('後端擋下來的清單就地說出理由', async () => {
    stubApi({
      [STATUS]: { body: AT_BERTH_ONE },
      [JELLYFIN]: { body: jellyfinSetup() },
      [SAVE]: {
        status: 422,
        body: { detail: { reason: 'built_changed', detail: "'Movies' already exists" } },
      },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    const anime = await screen.findByRole('group', { name: 'Anime' })
    await user.click(within(anime).getByRole('button', { name: '移除「Anime」' }))

    expect(
      await screen.findByText(
        '清單沒存下來：已經建好的媒體庫被改了。要改名或刪除，到 Jellyfin 做。',
        {},
        { timeout: 3000 },
      ),
    ).toBeInTheDocument()
  })
})

describe('泊位 1：清單的拒絕帶著列號', () => {
  it('後端說得出是第幾列就說第幾個', async () => {
    stubApi({
      [STATUS]: { body: AT_BERTH_ONE },
      [JELLYFIN]: { body: jellyfinSetup() },
      // 另一個分頁先存了一份：這一份在後端看來第二列撞名。
      [SAVE]: { status: 422, body: { detail: { reason: 'name_taken', detail: "'TV'", row: 1 } } },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    const anime = await screen.findByRole('group', { name: 'Anime' })
    await user.click(within(anime).getByRole('button', { name: '移除「Anime」' }))

    expect(
      await screen.findByText(
        '清單沒存下來（第 2 個）：名稱重複了（不分大小寫）。',
        {},
        { timeout: 3000 },
      ),
    ).toBeInTheDocument()
  })
})

describe('泊位 1：既有 Jellyfin', () => {
  const CONNECTED = jellyfinSetup({
    origin: 'existing',
    base_url: 'http://nas:8096',
    api_key_present: true,
    version: '12.0.0',
    steps: [step('public_info', 'ok', '12.0.0'), step('api_key', 'ok', 'Berth')],
    libraries: [
      library(),
      library({
        name: 'Anime',
        collection_type: 'tvshows',
        locations: ['/volume1/media/anime'],
        metadata_fetchers: ['TheTVDB', 'TheMovieDb'],
        uses_tvdb: true,
        berth_path: '/data/library/anime',
      }),
    ],
  })

  it('先要那台伺服器的管理員帳密，沒有靠泊按鈕', async () => {
    stubApi({
      [STATUS]: { body: NAS },
      [JELLYFIN]: { body: jellyfinSetup({ origin: 'existing', base_url: 'http://nas:8096' }) },
    })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByLabelText('Jellyfin 管理員帳號')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '開始靠泊' })).not.toBeInTheDocument()
    // 紅線：既有 Jellyfin 上不會出現任何「建立媒體庫」的動作——套件內那一份清單也不在。
    expect(screen.queryByText('要建的媒體庫')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '加一個媒體庫' })).not.toBeInTheDocument()
  })

  it('送出帳密去換一把 API key', async () => {
    const fetchStub = stubApi({
      [STATUS]: { body: NAS },
      [JELLYFIN]: { body: jellyfinSetup({ origin: 'existing', base_url: 'http://nas:8096' }) },
      [CONNECT]: { body: CONNECTED },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await user.type(await screen.findByLabelText('Jellyfin 管理員帳號'), 'owner')
    await user.type(screen.getByLabelText('Jellyfin 管理員密碼'), 's3cret')
    await user.click(screen.getByRole('button', { name: '登入並建立 API key' }))

    await waitFor(() => {
      const call = fetchStub.mock.calls.find(([url]) => url === '/api/setup/jellyfin/connect')
      expect(call && JSON.parse(String(call[1]?.body))).toEqual({
        username: 'owner',
        password: 's3cret',
      })
    })
  })

  it('列出媒體庫與各自路徑，掛 TVDB 的那個給警告', async () => {
    stubApi({ [STATUS]: { body: NAS }, [JELLYFIN]: { body: CONNECTED } })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByText('/volume1/media/films')).toBeInTheDocument()
    expect(screen.getByText('/volume1/media/anime')).toBeInTheDocument()
    expect(screen.getByText('TheTVDB · TheMovieDb')).toBeInTheDocument()
    expect(screen.getByText(/這個媒體庫用 TVDB 取 metadata/)).toBeInTheDocument()
  })

  it('「加入 Berth 路徑」要二次確認才送出，並先顯示會加哪一條', async () => {
    const fetchStub = stubApi({
      [STATUS]: { body: NAS },
      [JELLYFIN]: { body: CONNECTED },
      [PATHS]: { body: CONNECTED },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    const films = (await screen.findByText('Films')).closest('li')!
    expect(within(films).getByText('/data/library/films')).toBeInTheDocument()

    await user.click(within(films).getByRole('button', { name: '加入 Berth 路徑' }))

    // 還沒送出，先說清楚舊路徑不動。
    expect(
      fetchStub.mock.calls.some(([url]) => url === '/api/setup/jellyfin/libraries/paths'),
    ).toBe(false)
    expect(within(films).getByText(/舊路徑不動/)).toBeInTheDocument()

    await user.click(within(films).getByRole('button', { name: '確認加入' }))

    await waitFor(() => {
      const call = fetchStub.mock.calls.find(
        ([url]) => url === '/api/setup/jellyfin/libraries/paths',
      )
      expect(call && JSON.parse(String(call[1]?.body))).toEqual({ library: 'Films' })
    })
  })

  it('已經有 Berth 路徑的媒體庫不再顯示那顆按鈕', async () => {
    stubApi({
      [STATUS]: { body: NAS },
      [JELLYFIN]: {
        body: {
          ...CONNECTED,
          libraries: [
            library({
              locations: ['/volume1/media/films', '/data/library/films'],
              has_berth_path: true,
            }),
          ],
        },
      },
    })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByText('已接上')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '加入 Berth 路徑' })).not.toBeInTheDocument()
  })

  it('既有 Jellyfin 上沒有任何安裝插件或重啟的動作', async () => {
    stubApi({ [STATUS]: { body: NAS }, [JELLYFIN]: { body: CONNECTED } })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByText('Films')).toBeInTheDocument()
    // 12.x 原生合併多版本，Berth 不再碰別人的插件，也就不會重啟別人的 Jellyfin（票 14b）。
    expect(screen.queryByRole('button', { name: /MergeVersions/ })).not.toBeInTheDocument()
    expect(screen.queryByText(/重啟 Jellyfin/)).not.toBeInTheDocument()
  })

  it('加路徑失敗時就地顯示原文與手動步驟', async () => {
    stubApi({
      [STATUS]: { body: NAS },
      [JELLYFIN]: {
        body: {
          ...CONNECTED,
          steps: [
            ...CONNECTED.steps,
            step('libraries', 'failed', 'Films', 'POST /Library/VirtualFolders/Paths: 404'),
          ],
        },
      },
    })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByText('POST /Library/VirtualFolders/Paths: 404')).toBeInTheDocument()
    expect(screen.getByText(/同一個宿主目錄掛在同一個容器路徑/)).toBeInTheDocument()
    expect(screen.getByText('http://nas:8096/web/#/dashboard/libraries')).toBeInTheDocument()
  })

  it('一個媒體庫都沒有時說清楚下一步', async () => {
    stubApi({
      [STATUS]: { body: NAS },
      [JELLYFIN]: { body: { ...CONNECTED, libraries: [] } },
    })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByText('沒有媒體庫')).toBeInTheDocument()
    expect(screen.getByText(/先在 Jellyfin 建一個媒體庫再回來/)).toBeInTheDocument()
  })
})
