import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { stubApi } from '../test/fetch'
import { boardCells, findBoardCells } from '../test/board'
import { renderInRoute } from '../test/render'
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
const REREAD = 'POST /api/setup/routes/libraries'

/**
 * 頁 3 的假後端。進頁與按下「建立並檢查」之前都向 Jellyfin 重讀（M4 票 19、24）；沒另外給的話，
 * 重讀回的是與 `GET /setup/routes` 同一份——Jellyfin 在這段時間裡沒有變。
 */
function stubPage(routes: Parameters<typeof stubApi>[0]) {
  return stubApi({ [REREAD]: routes[ROUTES], ...routes })
}

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

/** 清單上的三列都在 Jellyfin 上建好了。 */
const LIST_BUILT_ALL = jellyfinSetup({
  steps: SEQUENCE_DONE,
  api_key_present: true,
  bundled: jellyfinSetup().bundled.map((row) => ({ ...row, built: true })),
})

/** 三條 Route 都建好、全綠了。 */
const ROUTES_BUILT = routeSetup({
  libraries: routeSetup().libraries.map((row) => ({ ...row, has_route: true })),
  routes: [
    routeView({ id: 1, library: 'Movies', slug: 'movies' }),
    routeView({ id: 2, library: 'TV', slug: 'tv' }),
    routeView({ id: 3, library: 'Anime', slug: 'anime' }),
  ],
  ready: true,
})

/**
 * 送出去的每一個寫入請求（非 GET），依序。**頁 3 進頁的重讀不算**（M4 票 19）：它向 Jellyfin 讀、
 * 換的是 Berth 自己的媒體庫快照，不寫任何服務——票 08 的「進頁不送寫入」說的是對服務的寫入。
 */
function writes(fetchStub: ReturnType<typeof stubApi>): string[] {
  return fetchStub.mock.calls
    .filter(([, init]) => (init?.method ?? 'GET') !== 'GET')
    .map(([url, init]) => `${init?.method} ${String(url)}`)
    .filter((call) => call !== REREAD)
}

describe('頁 3：套件內 Jellyfin 的媒體庫清單與「建立並檢查」（M4 票 08）', () => {
  it('進頁不送任何寫入：按之前先列出會建哪幾個媒體庫、幾個分類、寫幾個測試檔', async () => {
    const fetchStub = stubPage({
      [STATUS]: { body: AT_PAGE_THREE },
      [JELLYFIN]: { body: jellyfinSetup({ api_key_present: true }) },
      [ROUTES]: { body: routeSetup() },
    })

    renderInRoute(<SetupPage />)

    expect(await screen.findByRole('button', { name: '建立並檢查' })).toBeEnabled()
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('媒體庫路徑')
    const preview = screen.getByRole('region', { name: '按下之後會' })
    // 預設三列加上已經在 Jellyfin 上、還沒有 Route 的三個：這一輪的數字照目前的清單算。
    expect(within(preview).getByText(/在 Jellyfin 建 3 個媒體庫：Movies/)).toBeInTheDocument()
    expect(within(preview).getByText(/建或核對 6 個 berth- 分類/)).toBeInTheDocument()
    expect(
      within(preview).getByText(/在 6 條 Route 的分類路徑與寫入目標各寫一個探測檔/),
    ).toBeInTheDocument()
    await quietFor(900)
    expect(writes(fetchStub)).toEqual([])
  })

  it('剖面只放 Route 列沒有的：兩個根目錄與將建立的寫入目標，不列端點、不列數量', async () => {
    stubPage({
      [STATUS]: { body: AT_PAGE_THREE },
      [JELLYFIN]: { body: jellyfinSetup({ api_key_present: true }) },
      [ROUTES]: { body: routeSetup({ libraries: [] }) },
    })

    renderInRoute(<SetupPage />)
    const plan = (await screen.findByText('將建立')).closest('section')!

    expect(within(plan).getByText('/data/library/anime')).toBeInTheDocument()
    expect(screen.queryByText('POST /Startup/User')).not.toBeInTheDocument()
    expect(screen.queryByText('POST /Library/VirtualFolders')).not.toBeInTheDocument()
    expect(screen.queryByText('這一輪要建的 Route')).not.toBeInTheDocument()
  })

  it('按下之後照順序：存清單 → 建媒體庫 → 建 Route；三條都綠之後主要動作是前往下一個泊位', async () => {
    let docked = false
    const fetchStub = stubPage({
      [STATUS]: () => ({
        body: docked ? setupStatus({ ...AT_PAGE_THREE, current_step: 4 }) : AT_PAGE_THREE,
      }),
      [JELLYFIN]: () => ({ body: docked ? LIST_BUILT_ALL : jellyfinSetup() }),
      [SAVE]: { body: jellyfinSetup() },
      [BOOTSTRAP]: { body: LIST_BUILT_ALL },
      [ROUTES]: () => ({ body: docked ? ROUTES_BUILT : routeSetup({ libraries: [] }) }),
      [BUILD]: () => {
        docked = true
        return { body: ROUTES_BUILT }
      },
      'GET /api/setup/indexers': { body: indexerSetup() },
    })
    const user = userEvent.setup()

    renderInRoute(<SetupPage />)
    await user.click(await screen.findByRole('button', { name: '建立並檢查' }))

    const next = await screen.findByRole('button', { name: '前往下一個泊位' })
    expect(writes(fetchStub)).toEqual([
      'PUT /api/setup/jellyfin/bundled',
      'POST /api/setup/jellyfin/bootstrap',
      'POST /api/setup/routes',
    ])
    const build = fetchStub.mock.calls.find(
      ([url, init]) => url === '/api/setup/routes' && init?.method === 'POST',
    )!
    expect(JSON.parse(String(build[1]?.body))).toEqual({ selections: [] })
    // 停在結果上（票 06d）：每屏一顆 `assigned` 主鈕，就是前往下一個泊位；重新檢查降成次要。
    expect(next).toHaveClass('bg-assigned')
    expect(screen.getByRole('button', { name: '重新檢查 3 條 Route' })).not.toHaveClass(
      'bg-assigned',
    )
    // 清單建好了：收成一列。
    expect(screen.getByText('3 個已建立').closest('details')).not.toHaveAttribute('open')
  })

  it('建媒體庫那一步失敗就停：不建 Route，就地附原文與可複製的手動步驟', async () => {
    const broken = jellyfinSetup({
      api_key_present: true,
      steps: [
        ...SEQUENCE_DONE.slice(0, 3),
        step('libraries', 'failed', '', 'POST /Library/VirtualFolders: 500'),
      ],
    })
    const fetchStub = stubPage({
      [STATUS]: { body: AT_PAGE_THREE },
      [JELLYFIN]: { body: jellyfinSetup() },
      [SAVE]: { body: jellyfinSetup() },
      [BOOTSTRAP]: { body: broken },
      [ROUTES]: { body: routeSetup({ libraries: [] }) },
    })
    const user = userEvent.setup()

    renderInRoute(<SetupPage />)
    await user.click(await screen.findByRole('button', { name: '建立並檢查' }))

    expect(await screen.findByText(/POST \/Library\/VirtualFolders: 500/)).toBeInTheDocument()
    expect(screen.getByText('http://jellyfin:8096/web/#/dashboard/libraries')).toBeInTheDocument()
    expect(screen.getByText(/再按一次「建立並檢查」/)).toBeInTheDocument()
    expect(writes(fetchStub)).not.toContain('POST /api/setup/routes')
  })

  it('清單早就建好、Route 被刪光：按下只建 Route，不再建媒體庫', async () => {
    const fetchStub = stubPage({
      [STATUS]: { body: AT_PAGE_THREE },
      [JELLYFIN]: { body: LIST_BUILT_ALL },
      [SAVE]: { body: LIST_BUILT_ALL },
      [ROUTES]: { body: routeSetup() },
      [BUILD]: { body: ROUTES_BUILT },
    })
    const user = userEvent.setup()

    renderInRoute(<SetupPage />)
    const preview = await screen.findByRole('region', { name: '按下之後會' })
    expect(within(preview).queryByText(/個媒體庫/)).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '建立並檢查' }))

    await waitFor(() => expect(writes(fetchStub)).toContain('POST /api/setup/routes'))
    expect(writes(fetchStub)).not.toContain('POST /api/setup/jellyfin/bootstrap')
  })

  it('清單那一步失敗時，泊位板的 BTH 3 是阻擋', async () => {
    stubPage({
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

    renderInRoute(<SetupPage />)
    const board = await findBoardCells()

    await waitFor(() =>
      expect(within(board).getByText('BTH 3').closest('li')).toHaveTextContent('失敗'),
    )
  })

  it('上一次建媒體庫失敗、之後在 Jellyfin 補建好了：那次失敗不再掛著，BTH 3 不是阻擋（M4 票 24）', async () => {
    const fixedByHand = jellyfinSetup({
      steps: [
        ...SEQUENCE_DONE.slice(0, 3),
        step('libraries', 'failed', '', 'POST /Library/VirtualFolders: 500'),
      ],
      bundled: jellyfinSetup().bundled.map((row) => ({ ...row, built: true })),
    })
    stubPage({
      [STATUS]: { body: AT_PAGE_THREE },
      [JELLYFIN]: { body: fixedByHand },
      [ROUTES]: { body: routeSetup() },
    })

    renderInRoute(<SetupPage />)
    await screen.findByText('3 個已建立')
    const board = boardCells()

    expect(screen.queryByText(/POST \/Library\/VirtualFolders: 500/)).not.toBeInTheDocument()
    expect(within(board).getByText('BTH 3').closest('li')).not.toHaveTextContent('失敗')
  })

  it('版本低於 12 時說出目前版本與升級前要做的事', async () => {
    stubPage({
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

    renderInRoute(<SetupPage />)

    expect(await screen.findByText(/這台 Jellyfin 是 10.11.11/)).toBeInTheDocument()
    expect(screen.getByText(/完整備份/)).toBeInTheDocument()
    expect(screen.getByText(/移除第三方插件/)).toBeInTheDocument()
  })
})

describe('GET /api/setup/jellyfin 只在頁 3 讀', () => {
  it.each([
    [1, setupStatus({ services: [chosen()] }), {}, '建立 Jellyfin 管理員'],
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
    const fetchStub = stubPage({
      [STATUS]: { body: status },
      [JELLYFIN]: { body: LIST_BUILT },
      ...routes,
    })

    renderInRoute(<SetupPage />)

    expect(await screen.findByRole('heading', { level: 2, name: title })).toBeVisible()
    await quietFor(50)
    expect(jellyfinReads(fetchStub)).toBe(0)
  })

  it('從頁 4 點回 BTH 3 才讀', async () => {
    const fetchStub = stubPage({
      [STATUS]: {
        body: setupStatus({ current_step: 4, owner: 'skipper', services: ALL_BUNDLED }),
      },
      [JELLYFIN]: { body: LIST_BUILT },
      [ROUTES]: { body: ROUTES_BUILT },
      'GET /api/setup/indexers': { body: indexerSetup() },
    })
    const user = userEvent.setup()

    renderInRoute(<SetupPage />)
    const board = await findBoardCells()
    await user.click(await within(board).findByRole('button', { name: /BTH 3/ }))

    await waitFor(() => expect(jellyfinReads(fetchStub)).toBeGreaterThan(0))
  })
})

describe('頁 3 做完之後回頭補建（票 08 code-review）', () => {
  /** 後端已經過了頁 3，清單三列都建好、三條 Route 全綠；從頁 4 點回 BTH 3。 */
  async function revisit() {
    stubPage({
      [STATUS]: { body: setupStatus({ ...AT_PAGE_THREE, current_step: 4 }) },
      [JELLYFIN]: { body: LIST_BUILT_ALL },
      [SAVE]: { body: LIST_BUILT_ALL },
      [ROUTES]: { body: ROUTES_BUILT },
      'GET /api/setup/indexers': { body: indexerSetup() },
    })
    const user = userEvent.setup()
    renderInRoute(<SetupPage />)
    const board = await findBoardCells()
    await user.click(await within(board).findByRole('button', { name: /BTH 3/ }))
    await user.click(await screen.findByText('3 個已建立'))
    await user.click(screen.getByRole('button', { name: '加一個媒體庫' }))
    return user
  }

  it('在收起的清單裡加一列：焦點落在新的那一列，不掉回 body', async () => {
    await revisit()

    const added = screen.getByRole('group', { name: '第 4 個媒體庫' })
    expect(within(added).getByLabelText('名稱')).toHaveFocus()
  })

  it('加了一列要建：主鈕是「建立並檢查」但降成次要，一屏只有「前往下一個泊位」一顆主鈕', async () => {
    await revisit()

    const build = screen.getByRole('button', { name: '建立並檢查' })
    expect(build).not.toHaveClass('bg-assigned')
    expect(build.parentElement).not.toHaveClass('sticky')
    const painted = screen.getAllByRole('button').filter((button) => button.matches('.bg-assigned'))
    expect(painted.map((button) => button.textContent)).toEqual(['前往下一個泊位'])
  })
})

describe('頁 3：套件內 Jellyfin 的媒體庫清單（票 06f）', () => {
  it('改名、改類型、改資料夾、刪列、加列，停手就存下來', async () => {
    const fetchStub = stubPage({
      [STATUS]: { body: AT_PAGE_THREE },
      [JELLYFIN]: { body: jellyfinSetup() },
      [SAVE]: { body: jellyfinSetup() },
      [ROUTES]: { body: routeSetup() },
    })
    const user = userEvent.setup()

    renderInRoute(<SetupPage />)
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
    stubPage({
      [STATUS]: { body: AT_PAGE_THREE },
      [JELLYFIN]: { body: jellyfinSetup() },
      [SAVE]: { body: jellyfinSetup() },
      [ROUTES]: { body: routeSetup() },
    })
    const user = userEvent.setup()

    renderInRoute(<SetupPage />)
    await screen.findByRole('group', { name: 'Movies' })
    await user.click(screen.getByRole('button', { name: '移除「TV」' }))

    expect(screen.getByRole('article', { name: 'Anime' })).toHaveFocus()
  })

  it('重名、重複資料夾、跳出根目錄、空清單各有擋下的說法，而且不存、不讓靠泊', async () => {
    const fetchStub = stubPage({
      [STATUS]: { body: AT_PAGE_THREE },
      [JELLYFIN]: { body: jellyfinSetup() },
      [SAVE]: { body: jellyfinSetup() },
      [ROUTES]: { body: routeSetup() },
    })
    const user = userEvent.setup()

    renderInRoute(<SetupPage />)
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
    expect(screen.getByRole('button', { name: '建立並檢查' })).toBeDisabled()
    expect(screen.getByText('清單有標紅的格子，改好才能建立。')).toBeInTheDocument()

    for (const row of ['Movies', 'MOVIES', 'Anime']) {
      await user.click(screen.getByRole('button', { name: `移除「${row}」` }))
    }

    expect(screen.getByText('至少要一個媒體庫。')).toBeInTheDocument()
    await quietFor(900)
    expect(savedLists(fetchStub)).toEqual([])
  })

  it('按下之前先存畫面上的那一份，再建媒體庫', async () => {
    const fetchStub = stubPage({
      [STATUS]: { body: AT_PAGE_THREE },
      [JELLYFIN]: { body: jellyfinSetup() },
      [SAVE]: { body: jellyfinSetup() },
      [BOOTSTRAP]: { body: LIST_BUILT },
      [ROUTES]: { body: routeSetup() },
      [BUILD]: { body: ROUTES_BUILT },
    })
    const user = userEvent.setup()

    renderInRoute(<SetupPage />)
    const anime = await screen.findByRole('group', { name: 'Anime' })
    await user.click(within(anime).getByRole('button', { name: '移除「Anime」' }))
    await user.click(screen.getByRole('button', { name: '建立並檢查' }))

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
    stubPage({
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

    // 精靈已經走到頁 4；從泊位板回頭看頁 3。還有一列沒建，所以清單是展開的。
    renderInRoute(<SetupPage />)
    const board = await findBoardCells()
    await user.click(await within(board).findByRole('button', { name: /BTH 3/ }))
    const list = (await screen.findByRole('heading', { name: '要建的媒體庫' })).closest('section')!

    expect(within(list).getAllByText('已建立')).toHaveLength(2)
    expect(within(list).getByText('/data/library/films')).toBeInTheDocument()
    expect(within(list).queryByRole('group', { name: '電影' })).not.toBeInTheDocument()
    expect(within(list).queryByRole('button', { name: '移除「電影」' })).not.toBeInTheDocument()
    expect(within(list).getByText(/到 Jellyfin 的「控制台 → 媒體庫」/)).toBeInTheDocument()
    const documentaries = within(list).getByRole('group', { name: '紀錄片' })
    expect(within(documentaries).getByLabelText('名稱')).toBeEnabled()
    expect(
      within(screen.getByRole('region', { name: '按下之後會' })).getByText(
        /在 Jellyfin 建 1 個媒體庫：紀錄片/,
      ),
    ).toBeInTheDocument()
  })

  it('後端擋下來的清單就地說出理由', async () => {
    stubPage({
      [STATUS]: { body: AT_PAGE_THREE },
      [JELLYFIN]: { body: jellyfinSetup() },
      [SAVE]: {
        status: 422,
        body: { detail: { reason: 'built_changed', detail: "'Movies' already exists" } },
      },
      [ROUTES]: { body: routeSetup() },
    })
    const user = userEvent.setup()

    renderInRoute(<SetupPage />)
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
    stubPage({
      [STATUS]: { body: AT_PAGE_THREE },
      [JELLYFIN]: { body: jellyfinSetup() },
      // 另一個分頁先存了一份：這一份在後端看來第二列撞名。
      [SAVE]: { status: 422, body: { detail: { reason: 'name_taken', detail: "'TV'", row: 1 } } },
      [ROUTES]: { body: routeSetup() },
    })
    const user = userEvent.setup()

    renderInRoute(<SetupPage />)
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
    stubPage({
      [STATUS]: { body: NAS },
      [JELLYFIN]: { body: CONNECTED },
      [ROUTES]: { body: PICKER },
    })

    renderInRoute(<SetupPage />)

    expect(await screen.findByRole('checkbox', { name: '影集' })).toBeVisible()
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('媒體庫路徑')
    expect(screen.queryByLabelText('Jellyfin 管理員帳號')).not.toBeInTheDocument()
    // 紅線：既有 Jellyfin 上不會出現任何「建立媒體庫」的動作——套件內那一份清單也不在。
    expect(screen.queryByText('要建的媒體庫')).not.toBeInTheDocument()
    expect(screen.queryByText(/個媒體庫：/)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '加一個媒體庫' })).not.toBeInTheDocument()
  })

  // 使用者拍板：Berth 路徑併進「建立並檢查」——選它不送任何東西，按下時先加路徑、再建 Route。
  // 沒有「確認加入」那種做了一半、走得過去的狀態（M4 票 08 第 3 條）。
  it('Berth 路徑是寫入目標的一個選項：選它不送，按下時先加路徑再建 Route', async () => {
    const withPath = routeSetup({
      ...PICKER,
      libraries: [
        { ...PICKER.libraries[0], locations: ['/volume1/media/tv', '/data/library/影集'] },
      ],
    })
    let added = false
    const fetchStub = stubPage({
      [STATUS]: { body: NAS },
      [JELLYFIN]: { body: CONNECTED },
      [ROUTES]: () => ({ body: added ? withPath : PICKER }),
      [PATHS]: () => {
        added = true
        return { body: CONNECTED }
      },
      [BUILD]: { body: withPath },
    })
    const user = userEvent.setup()

    renderInRoute(<SetupPage />)
    await user.click(await screen.findByRole('checkbox', { name: '影集' }))
    const fresh = screen.getByRole('radio', { name: '/data/library/影集' })
    expect(fresh).toHaveAccessibleDescription(/按「建立並檢查」時加到這個媒體庫/)
    await user.click(fresh)

    expect(
      within(screen.getByRole('region', { name: '按下之後會' })).getByText(
        /在 Jellyfin 的「影集」加入路徑 \/data\/library\/影集（原本的路徑不動/,
      ),
    ).toBeInTheDocument()
    await quietFor(50)
    expect(writes(fetchStub)).toEqual([])

    await user.click(screen.getByRole('button', { name: '建立並檢查' }))

    await waitFor(() =>
      expect(writes(fetchStub)).toEqual([
        'POST /api/setup/jellyfin/libraries/paths',
        'POST /api/setup/routes',
      ]),
    )
    const [addCall, buildCall] = fetchStub.mock.calls.filter(
      ([url, init]) => (init?.method ?? 'GET') !== 'GET' && `POST ${String(url)}` !== REREAD,
    )
    expect(JSON.parse(String(addCall[1]?.body))).toEqual({ libraries: ['影集'] })
    expect(JSON.parse(String(buildCall[1]?.body))).toEqual({
      selections: [{ library: '影集', target_path: '/data/library/影集' }],
    })
  })

  it('加路徑沒加上就停：不建 Route，逐個說出 Jellyfin 看不到哪條路徑、沒掛哪個目錄（票 19）', async () => {
    const error =
      'Jellyfin cannot see /data/library/影集: POST /Environment/ValidatePath answered 404 for a file Berth had just written there'
    const fetchStub = stubPage({
      [STATUS]: { body: NAS },
      [JELLYFIN]: { body: CONNECTED },
      [ROUTES]: { body: PICKER },
      [PATHS]: {
        body: {
          ...CONNECTED,
          steps: [...CONNECTED.steps, step('libraries', 'failed', '', `影集: ${error}`)],
          berth_paths: [
            {
              library: '影集',
              path: '/data/library/影集',
              status: 'failed',
              reason: 'jellyfin_cannot_see',
              error,
            },
          ],
        },
      },
    })
    const user = userEvent.setup()

    renderInRoute(<SetupPage />)
    await user.click(await screen.findByRole('checkbox', { name: '影集' }))
    await user.click(screen.getByRole('radio', { name: '/data/library/影集' }))
    await user.click(screen.getByRole('button', { name: '建立並檢查' }))

    expect(await screen.findByText(error)).toBeInTheDocument()
    expect(screen.getByText('「影集」沒加上 Berth 路徑')).toBeInTheDocument()
    expect(
      screen.getByText(/Jellyfin 看不到 \/data\/library\/影集：它沒掛 \/data。/),
    ).toBeInTheDocument()
    expect(screen.getByText(/jellyfin:\s+volumes:/)).toBeInTheDocument()
    // 不再叫人去 Jellyfin 手動加（同樣會失敗），也不給 Berth 連它用的位址（瀏覽器開不了）。
    expect(screen.queryByText(/手動加/)).not.toBeInTheDocument()
    expect(screen.queryByText(/nas:8096/)).not.toBeInTheDocument()
    expect(writes(fetchStub)).toEqual(['POST /api/setup/jellyfin/libraries/paths'])
  })

  it('勾了媒體庫、還沒選寫入目標：主鈕擋住並說出還差哪一步', async () => {
    stubPage({
      [STATUS]: { body: NAS },
      [JELLYFIN]: { body: CONNECTED },
      [ROUTES]: {
        body: routeSetup({
          origin: 'existing',
          libraries: [
            libraryChoice({
              name: '影集',
              locations: ['/volume1/media/tv', '/volume2/tv'],
              has_berth_path: false,
              berth_path: '/data/library/影集',
              target_path: '',
            }),
          ],
        }),
      },
    })
    const user = userEvent.setup()

    renderInRoute(<SetupPage />)
    expect(await screen.findByText('還差一步：勾一個媒體庫。')).toBeInTheDocument()
    await user.click(screen.getByRole('checkbox', { name: '影集' }))

    expect(screen.getByText('還差一步：替「影集」選一條寫入目標。')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '建立並檢查' })).toBeDisabled()
    await user.click(screen.getByRole('radio', { name: '/volume2/tv' }))
    expect(screen.getByRole('button', { name: '建立並檢查' })).toBeEnabled()
  })

  it('名稱帶空白的媒體庫，「新的 Berth 路徑」的說明照樣掛在那顆 radio 上', async () => {
    stubPage({
      [STATUS]: { body: NAS },
      [JELLYFIN]: { body: CONNECTED },
      [ROUTES]: {
        body: routeSetup({
          origin: 'existing',
          libraries: [
            libraryChoice({
              name: 'TV Shows',
              locations: ['/volume1/media/tv'],
              berth_path: '/data/library/tv-shows',
              has_berth_path: false,
              target_path: '/volume1/media/tv',
            }),
          ],
        }),
      },
    })
    const user = userEvent.setup()

    renderInRoute(<SetupPage />)
    await user.click(await screen.findByRole('checkbox', { name: 'TV Shows' }))

    // id 用名字拼的話，`aria-describedby="target-TV Shows-…"` 會斷成兩個 id，說明就掛不上。
    expect(
      screen.getByRole('radio', { name: '/data/library/tv-shows' }),
    ).toHaveAccessibleDescription(/按「建立並檢查」時加到這個媒體庫/)
  })

  it('已經有 Berth 路徑的媒體庫不再多一個「新的」選項', async () => {
    stubPage({
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

    renderInRoute(<SetupPage />)
    await user.click(await screen.findByRole('checkbox', { name: '影集' }))

    expect(screen.getAllByRole('radio')).toHaveLength(2)
    expect(screen.queryByText(/時加到這個媒體庫/)).not.toBeInTheDocument()
  })

  it('掛 TVDB 的媒體庫給警告', async () => {
    stubPage({
      [STATUS]: { body: NAS },
      [JELLYFIN]: { body: CONNECTED },
      [ROUTES]: {
        body: routeSetup({
          origin: 'existing',
          libraries: [libraryChoice({ name: 'Anime', uses_tvdb: true })],
        }),
      },
    })

    renderInRoute(<SetupPage />)

    expect(await screen.findByText(/這個媒體庫掛了 TVDB 的 metadata fetcher/)).toBeInTheDocument()
  })

  it('既有 Jellyfin 上沒有任何安裝插件或重啟的動作', async () => {
    stubPage({
      [STATUS]: { body: NAS },
      [JELLYFIN]: { body: CONNECTED },
      [ROUTES]: { body: PICKER },
    })

    renderInRoute(<SetupPage />)

    expect(await screen.findByRole('checkbox', { name: '影集' })).toBeInTheDocument()
    // 12.x 原生合併多版本，Berth 不再碰別人的插件，也就不會重啟別人的 Jellyfin（票 14b）。
    expect(screen.queryByRole('button', { name: /MergeVersions/ })).not.toBeInTheDocument()
    expect(screen.queryByText(/重啟 Jellyfin/)).not.toBeInTheDocument()
  })

  it('一個媒體庫都沒有時說清楚下一步', async () => {
    stubPage({
      [STATUS]: { body: NAS },
      [JELLYFIN]: { body: { ...CONNECTED, libraries: [] } },
      [ROUTES]: { body: routeSetup({ origin: 'existing', libraries: [] }) },
    })

    renderInRoute(<SetupPage />)

    expect(await screen.findByText(/先在 Jellyfin 建一個再回來/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '建立並檢查' })).toBeDisabled()
  })
})
