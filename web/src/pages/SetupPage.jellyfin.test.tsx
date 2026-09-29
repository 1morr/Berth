import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { stubApi } from '../test/fetch'
import { renderWithProviders } from '../test/render'
import {
  ALL_BUNDLED,
  SEQUENCE_DONE,
  chosen,
  indexerSetup,
  jellyfinSetup,
  library,
  libraryChoice,
  qbittorrentSetup,
  routeSetup,
  routeView,
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
const PATHS = 'POST /api/setup/jellyfin/libraries/paths'
const SAVE = 'PUT /api/setup/jellyfin/bundled'
const ROUTES = 'GET /api/setup/routes'
const BUILD = 'POST /api/setup/routes'

/** 送出去的每一份清單，依序（票 06f）。 */
function savedLists(fetchStub: ReturnType<typeof stubApi>): unknown[] {
  return fetchStub.mock.calls
    .filter(([url, init]) => url === '/api/setup/jellyfin/bundled' && init?.method === 'PUT')
    .map(([, init]) => JSON.parse(String(init?.body)) as unknown)
}

/** 讀過幾次 `GET /api/setup/jellyfin`。 */
function jellyfinReads(fetchStub: ReturnType<typeof stubApi>): number {
  return fetchStub.mock.calls.filter(
    ([url, init]) => url === '/api/setup/jellyfin' && (init?.method ?? 'GET') === 'GET',
  ).length
}

/** 比停手存檔的等待再久一點：拿來證明「沒有存」。 */
function quietFor(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/** 頁 1–2 都做完了，精靈在頁 3（媒體庫與路徑）。Prowlarr 在頁 4 才選。 */
const AT_PAGE_THREE = setupStatus({
  current_step: 3,
  owner: 'skipper',
  services: ALL_BUNDLED.slice(0, 2),
})

/** 清單建完了：`libraries` 那一步有結論。 */
const LIST_BUILT = jellyfinSetup({ steps: SEQUENCE_DONE, api_key_present: true })

/** 三條 Route 都建好了：清單建完之後回到頁 3 不會再自動建。 */
const ROUTES_BUILT = routeSetup({
  libraries: routeSetup().libraries.map((row) => ({ ...row, has_route: true })),
  routes: [
    routeView({ id: 1, library: 'Movies', slug: 'movies' }),
    routeView({ id: 2, library: 'TV', slug: 'tv' }),
    routeView({ id: 3, library: 'Anime', slug: 'anime' }),
  ],
  ready: true,
})

describe('頁 3：套件內 Jellyfin 先畫媒體庫清單與靠泊序列', () => {
  // M4 票 06：前六步在頁 1（擁有者）就有結論了，頁 3 還沒做的是建媒體庫。
  it('頁 1 做完的那幾步不算清單建完：仍然是「開始靠泊」', async () => {
    const owned = (
      [
        'public_info',
        'configuration',
        'admin_user',
        'remote_access',
        'complete',
        'api_key',
      ] as const
    ).map((step) => ({ step, status: 'ok' as const, detail: '', error: '' }))
    stubApi({
      [STATUS]: { body: AT_PAGE_THREE },
      [JELLYFIN]: { body: jellyfinSetup({ steps: owned, api_key_present: true }) },
      [ROUTES]: { body: routeSetup() },
    })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByRole('button', { name: '開始靠泊' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('建立媒體庫')
    expect(screen.queryByRole('button', { name: '重新跑一次' })).not.toBeInTheDocument()
    // 還沒建完就沒有 Route 那一半可去。
    expect(screen.queryByRole('button', { name: '前往 Route 與檢查' })).not.toBeInTheDocument()
  })

  it('剖面在按之前就列出七支端點', async () => {
    stubApi({
      [STATUS]: { body: AT_PAGE_THREE },
      [JELLYFIN]: { body: jellyfinSetup() },
      [ROUTES]: { body: routeSetup() },
    })

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
      [STATUS]: { body: AT_PAGE_THREE },
      [JELLYFIN]: { body: jellyfinSetup() },
      [SAVE]: { body: jellyfinSetup() },
      [BOOTSTRAP]: { body: LIST_BUILT },
      [ROUTES]: { body: routeSetup() },
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

  it('按下靠泊之後停在清單的結果上，不自動跳去 Route；按「前往 Route 與檢查」才去', async () => {
    let built = false
    const fetchStub = stubApi({
      [STATUS]: { body: AT_PAGE_THREE },
      [JELLYFIN]: () => ({ body: built ? LIST_BUILT : jellyfinSetup() }),
      [SAVE]: { body: jellyfinSetup() },
      [BOOTSTRAP]: () => {
        built = true
        return { body: LIST_BUILT }
      },
      [ROUTES]: { body: routeSetup() },
      [BUILD]: { body: ROUTES_BUILT },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await user.click(await screen.findByRole('button', { name: '開始靠泊' }))

    const toRoutes = await screen.findByRole('button', { name: '前往 Route 與檢查' })
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('建立媒體庫')
    expect(screen.getByTestId('sequence')).toBeInTheDocument()
    // Route 讀是可以的（泊位板要畫），建是不行的。
    expect(
      fetchStub.mock.calls.some(
        ([url, init]) => url === '/api/setup/routes' && init?.method === 'POST',
      ),
    ).toBe(false)

    await user.click(toRoutes)

    expect(await screen.findByRole('heading', { level: 2, name: '媒體庫路徑' })).toBeVisible()
    await waitFor(() =>
      expect(
        fetchStub.mock.calls.some(
          ([url, init]) => url === '/api/setup/routes' && init?.method === 'POST',
        ),
      ).toBe(true),
    )
  })

  it('清單建完之後一進頁 3 就是 Route；「媒體庫清單」切得回去，重按過的那幾步標成「已經是這樣」', async () => {
    stubApi({
      [STATUS]: { body: AT_PAGE_THREE },
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
      [ROUTES]: { body: ROUTES_BUILT },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    expect(await screen.findByRole('heading', { level: 2, name: '媒體庫路徑' })).toBeVisible()
    expect(screen.queryByTestId('sequence')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '媒體庫清單' }))

    expect(await screen.findByRole('heading', { level: 2, name: '建立媒體庫' })).toBeVisible()
    const sequence = screen.getByTestId('sequence')
    await waitFor(() => expect(within(sequence).getAllByText('已經是這樣')).toHaveLength(6))
    expect(screen.getByRole('button', { name: '重新跑一次' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '前往 Route 與檢查' }))
    expect(await screen.findByRole('heading', { level: 2, name: '媒體庫路徑' })).toBeVisible()
  })

  it('失敗的那一步就地變紅，附原文與可複製的手動步驟', async () => {
    stubApi({
      [STATUS]: { body: AT_PAGE_THREE },
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
      [ROUTES]: { body: routeSetup() },
    })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByText(/POST \/Library\/VirtualFolders: 500/)).toBeInTheDocument()
    expect(screen.getByText('http://jellyfin:8096/web/#/dashboard/libraries')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '重試失敗的那一步' })).toBeInTheDocument()
    const sequence = screen.getByTestId('sequence')
    // 失敗那一步之後的都沒跑到——序列停在那裡，而不是跳過它繼續。
    expect(within(sequence).getAllByText('尚未執行')).toHaveLength(3)
  })

  it('清單那一步失敗時，泊位板的 BTH 3 是阻擋', async () => {
    stubApi({
      [STATUS]: { body: AT_PAGE_THREE },
      [JELLYFIN]: {
        body: jellyfinSetup({
          steps: [
            ...SEQUENCE_DONE.slice(0, 3),
            step('libraries', 'failed', '', 'POST /Library/VirtualFolders: 500'),
          ],
        }),
      },
      [ROUTES]: { body: routeSetup() },
    })

    renderWithProviders(<SetupPage />)
    const board = await screen.findByRole('region', { name: '泊位板' })

    await waitFor(() =>
      expect(within(board).getByText('BTH 3').closest('li')).toHaveTextContent('失敗'),
    )
  })

  it('版本低於 12 時說出目前版本與升級前要做的事', async () => {
    stubApi({
      [STATUS]: { body: AT_PAGE_THREE },
      [JELLYFIN]: {
        body: jellyfinSetup({
          version: '10.11.11',
          version_supported: false,
          steps: [
            step('public_info', 'failed', '10.11.11', 'Jellyfin 10.11.11 is older than 12.0'),
          ],
        }),
      },
      [ROUTES]: { body: routeSetup() },
    })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByText(/這台 Jellyfin 是 10.11.11/)).toBeInTheDocument()
    expect(screen.getByText(/完整備份/)).toBeInTheDocument()
    expect(screen.getByText(/移除第三方插件/)).toBeInTheDocument()
  })
})

describe('GET /api/setup/jellyfin 只在頁 3 讀', () => {
  it.each([
    [
      1,
      setupStatus({ services: [chosen()] }),
      {},
      '建立 Jellyfin 管理員',
    ],
    [
      2,
      setupStatus({ current_step: 2, owner: 'skipper', services: ALL_BUNDLED.slice(0, 2) }),
      { 'GET /api/setup/qbittorrent/diff': { body: qbittorrentSetup() } },
      '套用建議的 qBittorrent 設定',
    ],
    [
      4,
      setupStatus({ current_step: 4, owner: 'skipper', services: ALL_BUNDLED }),
      { [ROUTES]: { body: ROUTES_BUILT }, 'GET /api/setup/indexers': { body: indexerSetup() } },
      '索引站',
    ],
  ])('頁 %i 不讀', async (_, status, routes, title) => {
    const fetchStub = stubApi({
      [STATUS]: { body: status },
      [JELLYFIN]: { body: LIST_BUILT },
      ...routes,
    })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByRole('heading', { level: 2, name: title })).toBeVisible()
    await quietFor(50)
    expect(jellyfinReads(fetchStub)).toBe(0)
  })

  it('從頁 4 點回 BTH 3 才讀', async () => {
    const fetchStub = stubApi({
      [STATUS]: {
        body: setupStatus({ current_step: 4, owner: 'skipper', services: ALL_BUNDLED }),
      },
      [JELLYFIN]: { body: LIST_BUILT },
      [ROUTES]: { body: ROUTES_BUILT },
      'GET /api/setup/indexers': { body: indexerSetup() },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    const board = await screen.findByRole('region', { name: '泊位板' })
    await user.click(await within(board).findByRole('button', { name: /BTH 3/ }))

    await waitFor(() => expect(jellyfinReads(fetchStub)).toBeGreaterThan(0))
  })
})

describe('頁 3：套件內 Jellyfin 的媒體庫清單（票 06f）', () => {
  it('改名、改類型、改資料夾、刪列、加列，停手就存下來', async () => {
    const fetchStub = stubApi({
      [STATUS]: { body: AT_PAGE_THREE },
      [JELLYFIN]: { body: jellyfinSetup() },
      [SAVE]: { body: jellyfinSetup() },
      [ROUTES]: { body: routeSetup() },
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
      [STATUS]: { body: AT_PAGE_THREE },
      [JELLYFIN]: { body: jellyfinSetup() },
      [SAVE]: { body: jellyfinSetup() },
      [ROUTES]: { body: routeSetup() },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await screen.findByRole('group', { name: 'Movies' })
    await user.click(screen.getByRole('button', { name: '移除「TV」' }))

    expect(screen.getByRole('article', { name: 'Anime' })).toHaveFocus()
  })

  it('重名、重複資料夾、跳出根目錄、空清單各有擋下的說法，而且不存、不讓靠泊', async () => {
    const fetchStub = stubApi({
      [STATUS]: { body: AT_PAGE_THREE },
      [JELLYFIN]: { body: jellyfinSetup() },
      [SAVE]: { body: jellyfinSetup() },
      [ROUTES]: { body: routeSetup() },
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
      [STATUS]: { body: AT_PAGE_THREE },
      [JELLYFIN]: { body: jellyfinSetup() },
      [SAVE]: { body: jellyfinSetup() },
      [BOOTSTRAP]: { body: LIST_BUILT },
      [ROUTES]: { body: routeSetup() },
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
      [STATUS]: { body: setupStatus({ ...AT_PAGE_THREE, current_step: 4 }) },
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
      [ROUTES]: { body: ROUTES_BUILT },
      'GET /api/setup/indexers': { body: indexerSetup() },
    })
    const user = userEvent.setup()

    // 精靈已經走到頁 4；從泊位板回頭看頁 3，清單建完了所以先是 Route，切回清單。
    renderWithProviders(<SetupPage />)
    const board = await screen.findByRole('region', { name: '泊位板' })
    await user.click(await within(board).findByRole('button', { name: /BTH 3/ }))
    await user.click(await screen.findByRole('button', { name: '媒體庫清單' }))
    const list = (await screen.findByRole('heading', { name: '要建的媒體庫' })).closest('section')!

    expect(within(list).getAllByText('已建立')).toHaveLength(2)
    expect(within(list).getByText('/data/library/films')).toBeInTheDocument()
    expect(within(list).queryByRole('group', { name: '電影' })).not.toBeInTheDocument()
    expect(within(list).queryByRole('button', { name: '移除「電影」' })).not.toBeInTheDocument()
    expect(within(list).getByText(/到 Jellyfin 的「控制台 → 媒體庫」/)).toBeInTheDocument()
    const documentaries = within(list).getByRole('group', { name: '紀錄片' })
    expect(within(documentaries).getByLabelText('名稱')).toBeEnabled()
    expect(screen.getByText(/Jellyfin 有擁有者的管理員帳號、2 個媒體庫/)).toBeInTheDocument()
  })

  it('後端擋下來的清單就地說出理由', async () => {
    stubApi({
      [STATUS]: { body: AT_PAGE_THREE },
      [JELLYFIN]: { body: jellyfinSetup() },
      [SAVE]: {
        status: 422,
        body: { detail: { reason: 'built_changed', detail: "'Movies' already exists" } },
      },
      [ROUTES]: { body: routeSetup() },
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

describe('頁 3：清單的拒絕帶著列號', () => {
  it('後端說得出是第幾列就說第幾個', async () => {
    stubApi({
      [STATUS]: { body: AT_PAGE_THREE },
      [JELLYFIN]: { body: jellyfinSetup() },
      // 另一個分頁先存了一份：這一份在後端看來第二列撞名。
      [SAVE]: { status: 422, body: { detail: { reason: 'name_taken', detail: "'TV'", row: 1 } } },
      [ROUTES]: { body: routeSetup() },
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

describe('頁 3：既有 Jellyfin 直接是 Route', () => {
  const NAS = setupStatus({
    ...AT_PAGE_THREE,
    services: [
      chosen({
        origin: 'existing',
        base_url: 'http://nas:8096',
        reason: 'setup_completed',
        detail: '12.0.0',
      }),
      ...ALL_BUNDLED.slice(1, 2),
    ],
  })

  const CONNECTED = jellyfinSetup({
    origin: 'existing',
    base_url: 'http://nas:8096',
    api_key_present: true,
    version: '12.0.0',
    steps: [step('public_info', 'ok', '12.0.0'), step('api_key', 'ok', 'Berth')],
    libraries: [library()],
  })

  const PICKER = routeSetup({
    origin: 'existing',
    libraries: [
      libraryChoice({
        name: '影集',
        locations: ['/volume1/media/tv'],
        berth_path: '/data/library/影集',
        has_berth_path: false,
        target_path: '/volume1/media/tv',
      }),
    ],
  })

  // M4 票 06：登入與 API key 在頁 1（擁有者）就做完了；既有的那一台 Berth 不建媒體庫（brief §16.4）。
  it('不要帳密、沒有靠泊、沒有清單可切：直接是 Route 的勾選', async () => {
    stubApi({ [STATUS]: { body: NAS }, [JELLYFIN]: { body: CONNECTED }, [ROUTES]: { body: PICKER } })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByRole('checkbox', { name: '影集' })).toBeVisible()
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('媒體庫路徑')
    expect(screen.queryByLabelText('Jellyfin 管理員帳號')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '開始靠泊' })).not.toBeInTheDocument()
    // 紅線：既有 Jellyfin 上不會出現任何「建立媒體庫」的動作——套件內那一份清單也不在。
    expect(screen.queryByText('要建的媒體庫')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '媒體庫清單' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '加一個媒體庫' })).not.toBeInTheDocument()
  })

  it('「加入 Berth 路徑」要二次確認才送出，先說出會加哪一條；加完 Route 的清單重讀', async () => {
    const fetchStub = stubApi({
      [STATUS]: { body: NAS },
      [JELLYFIN]: { body: CONNECTED },
      [ROUTES]: { body: PICKER },
      [PATHS]: { body: CONNECTED },
    })
    const user = userEvent.setup()
    const routeReads = () =>
      fetchStub.mock.calls.filter(
        ([url, init]) => url === '/api/setup/routes' && (init?.method ?? 'GET') === 'GET',
      ).length

    renderWithProviders(<SetupPage />)
    await user.click(await screen.findByRole('checkbox', { name: '影集' }))
    await user.click(screen.getByRole('button', { name: '加入 Berth 路徑' }))

    // 還沒送出，先說清楚加哪一條、舊路徑不動。
    expect(
      fetchStub.mock.calls.some(([url]) => url === '/api/setup/jellyfin/libraries/paths'),
    ).toBe(false)
    expect(screen.getByText(/會對媒體庫「影集」加上 \/data\/library\/影集。舊路徑不動/)).toBeVisible()
    const before = routeReads()

    await user.click(screen.getByRole('button', { name: '確認加入' }))

    await waitFor(() => {
      const call = fetchStub.mock.calls.find(
        ([url]) => url === '/api/setup/jellyfin/libraries/paths',
      )
      expect(call && JSON.parse(String(call[1]?.body))).toEqual({ library: '影集' })
    })
    await waitFor(() => expect(routeReads()).toBeGreaterThan(before))
  })

  it('已經有 Berth 路徑的媒體庫不再顯示那顆按鈕', async () => {
    stubApi({
      [STATUS]: { body: NAS },
      [JELLYFIN]: { body: CONNECTED },
      [ROUTES]: {
        body: routeSetup({
          origin: 'existing',
          libraries: [
            libraryChoice({
              name: '影集',
              locations: ['/volume1/media/tv', '/data/library/影集'],
              berth_path: '/data/library/影集',
              has_berth_path: true,
            }),
          ],
        }),
      },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await user.click(await screen.findByRole('checkbox', { name: '影集' }))

    expect(screen.getByRole('radio', { name: '/data/library/影集' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '加入 Berth 路徑' })).not.toBeInTheDocument()
  })

  it('掛 TVDB 的媒體庫給警告', async () => {
    stubApi({
      [STATUS]: { body: NAS },
      [JELLYFIN]: { body: CONNECTED },
      [ROUTES]: {
        body: routeSetup({
          origin: 'existing',
          libraries: [libraryChoice({ name: 'Anime', uses_tvdb: true })],
        }),
      },
    })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByText(/這個媒體庫掛了 TVDB 的 metadata fetcher/)).toBeInTheDocument()
  })

  it('既有 Jellyfin 上沒有任何安裝插件或重啟的動作', async () => {
    stubApi({ [STATUS]: { body: NAS }, [JELLYFIN]: { body: CONNECTED }, [ROUTES]: { body: PICKER } })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByRole('checkbox', { name: '影集' })).toBeInTheDocument()
    // 12.x 原生合併多版本，Berth 不再碰別人的插件，也就不會重啟別人的 Jellyfin（票 14b）。
    expect(screen.queryByRole('button', { name: /MergeVersions/ })).not.toBeInTheDocument()
    expect(screen.queryByText(/重啟 Jellyfin/)).not.toBeInTheDocument()
  })

  it('一個媒體庫都沒有時說清楚下一步', async () => {
    stubApi({
      [STATUS]: { body: NAS },
      [JELLYFIN]: { body: { ...CONNECTED, libraries: [] } },
      [ROUTES]: { body: routeSetup({ origin: 'existing', libraries: [] }) },
    })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByText(/先在 Jellyfin 建一個再回來/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Route 並檢查/ })).toBeDisabled()
  })
})
