import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { session, stubApi } from '../test/fetch'
import { renderApp, renderWithProviders } from '../test/render'
import {
  ALL_BUNDLED,
  CHECKS_PASSED,
  SEQUENCE_DONE,
  chosen,
  discoverWall,
  indexerSetup,
  jellyfinSetup,
  libraryChoice,
  routeSetup,
  routeView,
  setupStatus,
  site,
  step,
  tmdbSetup,
} from '../test/fixtures'
import { type RouteView } from '../api/schemas'
import { SetupPage } from './SetupPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

const STATUS = 'GET /api/setup/status'
const ROUTES = 'GET /api/setup/routes'
const BUILD = 'POST /api/setup/routes'
const REREAD = 'POST /api/setup/routes/libraries'
const COMPLETE = 'POST /api/setup/complete'
const INDEXERS = 'GET /api/setup/indexers'
const TMDB = 'GET /api/setup/tmdb'

const JELLYFIN = 'GET /api/setup/jellyfin'

/**
 * 頁 3 的假後端。進頁與按下「建立並檢查」之前都向 Jellyfin 重讀（M4 票 19、24）；沒另外給的話，
 * 重讀回的是與 `GET /setup/routes` 同一份——Jellyfin 在這段時間裡沒有變。
 */
function stubPage(routes: Parameters<typeof stubApi>[0]) {
  return stubApi({ [REREAD]: routes[ROUTES], ...routes })
}

/**
 * 送出去的每一個寫入請求（非 GET），依序。**頁 3 進頁的重讀不算**（M4 票 19）：它向 Jellyfin 讀、
 * 換的是 Berth 自己的媒體庫快照，不寫任何服務——票 08 的「進頁不送寫入」說的是對服務的寫入。
 */
function writes(fetch: ReturnType<typeof stubApi>): string[] {
  return fetch.mock.calls
    .filter(([, init]) => (init?.method ?? 'GET') !== 'GET')
    .map(([input, init]) => `${init?.method} ${String(input)}`)
    .filter((call) => call !== REREAD)
}

/** Jellyfin 與 qBittorrent 都接好了，精靈在媒體庫與路徑（頁 3，票 06d 移到 qBittorrent 之後）。 */
const AT_ROUTES = setupStatus({
  current_step: 3,
  owner: 'skipper',
  services: ALL_BUNDLED.slice(0, 2),
})

/** 每個泊位都接好了，剩下按完成。 */
const AT_THE_END = setupStatus({ ...AT_ROUTES, current_step: 6, services: ALL_BUNDLED })

/** 頁 3、套件內 Jellyfin、清單上的媒體庫都建好了：按下只建 Route（M4 票 08）。 */
const BUNDLED_PAGE = {
  [STATUS]: { body: AT_ROUTES },
  [JELLYFIN]: {
    body: jellyfinSetup({
      steps: SEQUENCE_DONE,
      api_key_present: true,
      bundled: jellyfinSetup().bundled.map((row) => ({ ...row, built: true })),
    }),
  },
  'PUT /api/setup/jellyfin/bundled': {
    body: jellyfinSetup({
      steps: SEQUENCE_DONE,
      api_key_present: true,
      bundled: jellyfinSetup().bundled.map((row) => ({ ...row, built: true })),
    }),
  },
}

/** 頁 3、既有 Jellyfin：沒有清單，直接是 Route 的勾選。 */
const EXISTING_PAGE = {
  [STATUS]: {
    body: setupStatus({
      ...AT_ROUTES,
      services: [
        chosen({ origin: 'existing', base_url: 'http://nas:8096', reason: 'setup_completed' }),
        ...ALL_BUNDLED.slice(1, 2),
      ],
    }),
  },
  [JELLYFIN]: {
    body: jellyfinSetup({ origin: 'existing', base_url: 'http://nas:8096', api_key_present: true }),
  },
}

/** 後端過了頁 3（Route 全綠、清單建完）：精靈在頁 4。 */
const PAST_ROUTES = {
  [STATUS]: { body: setupStatus({ ...AT_ROUTES, current_step: 4, services: ALL_BUNDLED }) },
  [INDEXERS]: { body: indexerSetup() },
}

const BUILT = routeSetup({
  routes: [
    routeView({ library: 'Movies', slug: 'movies', collection_type: 'movies' }),
    routeView({ library: 'TV', slug: 'tv' }),
    routeView({ library: 'Anime', slug: 'anime' }),
  ],
  libraries: routeSetup().libraries.map((row) => ({ ...row, has_route: true })),
  ready: true,
})

describe('頁 3：媒體庫路徑（套件內）', () => {
  it('進頁不送任何寫入：一顆「建立並檢查」，按下才建（M4 票 08）', async () => {
    const fetch = stubPage({ ...BUNDLED_PAGE, [ROUTES]: { body: routeSetup() } })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByRole('button', { name: '建立並檢查' })).toBeEnabled()
    await new Promise((resolve) => setTimeout(resolve, 900))
    expect(writes(fetch)).toEqual([])
  })

  it('按下之後每條 Route 逐項顯示檢查結果，含硬鏈接的 inode；送出的是空的勾選', async () => {
    const fetch = stubPage({
      ...BUNDLED_PAGE,
      [ROUTES]: { body: routeSetup() },
      [BUILD]: { body: BUILT },
    })

    renderWithProviders(<SetupPage />)
    await userEvent.click(await screen.findByRole('button', { name: '建立並檢查' }))

    const sequences = await screen.findAllByTestId('checks')
    expect(sequences).toHaveLength(3)
    expect(within(sequences[1]).getByText('硬鏈接與 inode 比對')).toBeInTheDocument()
    // 實測值留在那一行：這是「三個容器看到同一個檔案系統」唯一的證據。
    expect(
      within(sequences[1]).getByText('dev=70 · inode=8162774324533690 · 137.4 GB free'),
    ).toBeInTheDocument()
    expect(within(sequences[1]).getAllByText('已完成')).toHaveLength(6)
    const build = fetch.mock.calls.find(
      ([input, init]) => init?.method === 'POST' && String(input) === '/api/setup/routes',
    )!
    expect(JSON.parse(String(build[1]?.body))).toEqual({ selections: [] })
  })

  it('每條 Route 收成一列說「6 / 6 通過」，全過的收起、紅的那一條自己打開', async () => {
    const oneRed = routeSetup({
      ...BUILT,
      ready: false,
      routes: [
        ...BUILT.routes.slice(0, 2),
        routeView({
          id: 4,
          library: 'Anime',
          slug: 'anime',
          health: 'failed',
          checks: [
            ...CHECKS_PASSED.slice(0, 4),
            step('probe_visible', 'failed', '', 'Jellyfin cannot see /data/library/anime'),
            step('hardlink', 'pending'),
          ],
        }),
        routeView({ id: 5, library: 'Docs', slug: 'docs', collection_type: 'movies' }),
      ],
    })
    stubPage({ ...BUNDLED_PAGE, [ROUTES]: { body: oneRed } })

    renderWithProviders(<SetupPage />)
    const list = await screen.findByRole('list', { name: '這一頁的 Route' })
    // 技術細節也是 `<details>`（M4 票 21），只數 Route 列那一層。
    const rows = within(list)
      .getAllByRole('group')
      .filter((row) => row.dataset.testid !== 'technical-details')

    expect(rows).toHaveLength(4)
    expect(within(list).getAllByText('6 / 6 通過')).toHaveLength(3)
    expect(within(list).getByText('4 / 6 通過')).toBeInTheDocument()
    expect(rows.map((row) => row.hasAttribute('open'))).toEqual([false, false, true, false])
  })

  it('請求沒走完時說出來，鍵還在，再按一次', async () => {
    stubPage({
      ...BUNDLED_PAGE,
      [ROUTES]: { body: routeSetup() },
      [BUILD]: { status: 500, body: { detail: 'boom' } },
    })

    renderWithProviders(<SetupPage />)
    await userEvent.click(await screen.findByRole('button', { name: '建立並檢查' }))

    // 500 是後端自己出錯，不是「可能沒在跑」（M4 票 21）；原文收進技術細節。
    expect(await screen.findByText(/後端出錯了/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '建立並檢查' })).toBeEnabled()
  })

  it('三條都建好之後，剖面不再說「將建立」那三條（票 14、14e 留給票 15 的兩條）', async () => {
    stubPage({ ...BUNDLED_PAGE, [ROUTES]: { body: BUILT } })

    renderWithProviders(<SetupPage />)
    await screen.findByRole('button', { name: '重新檢查 3 條 Route' })

    expect(screen.queryByText('將建立')).not.toBeInTheDocument()
  })

  it('三條都建好之後再按一次是全部重驗，不會多建（票 14：精靈只新增）', async () => {
    stubPage({ ...BUNDLED_PAGE, [ROUTES]: { body: BUILT } })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByRole('button', { name: '重新檢查 3 條 Route' })).toBeEnabled()
  })

  it('每條 Route 底下都有刪除：二次確認之後打精靈自己的 DELETE，刪完列消失並播報（票 14、14a）', async () => {
    let deleted = false
    const withoutMovies = routeSetup({
      ...BUILT,
      routes: BUILT.routes.filter((route) => route.slug !== 'movies'),
    })
    const fetch = stubPage({
      ...BUNDLED_PAGE,
      [ROUTES]: () => ({ body: deleted ? withoutMovies : BUILT }),
      'DELETE /api/setup/routes/2': () => {
        deleted = true
        return { status: 204, body: null }
      },
    })

    renderWithProviders(<SetupPage />)
    const [first] = await screen.findAllByRole('button', { name: '刪除這條 Route' })
    await userEvent.click(first)
    await userEvent.click(screen.getByRole('button', { name: '確定刪除' }))

    expect(await screen.findByText('已刪除「Movies」。')).toBeInTheDocument()
    await waitFor(() =>
      expect(screen.getAllByRole('button', { name: '刪除這條 Route' })).toHaveLength(2),
    )
    // `/routes/*` 永遠只有 admin；精靈跑完之前沒有人登入得了，所以精靈走 `setup/*` 那一支。
    expect(
      fetch.mock.calls.some(
        ([input, init]) => init?.method === 'DELETE' && String(input) === '/api/setup/routes/2',
      ),
    ).toBe(true)
  })

  it('刪的那一刻被引用：說出數字（票 14a）', async () => {
    stubPage({
      ...BUNDLED_PAGE,
      [ROUTES]: { body: BUILT },
      'DELETE /api/setup/routes/2': {
        status: 409,
        body: {
          detail: {
            reason: 'route_in_use',
            detail: 'jobs=1 · ledger_entries=0',
            jobs: 1,
            ledger_entries: 0,
          },
        },
      },
    })

    renderWithProviders(<SetupPage />)
    const [first] = await screen.findAllByRole('button', { name: '刪除這條 Route' })
    await userEvent.click(first)
    await userEvent.click(screen.getByRole('button', { name: '確定刪除' }))

    expect(await screen.findByText(/刪不得/)).toHaveTextContent('1 筆下載、0 個入庫檔案')
  })

  it('409 沒帶數字時仍說刪不得，不說後端沒在跑', async () => {
    stubPage({
      ...BUNDLED_PAGE,
      [ROUTES]: { body: BUILT },
      'DELETE /api/setup/routes/2': {
        status: 409,
        body: { detail: { reason: 'route_in_use', detail: 'jobs=1 · ledger_entries=0' } },
      },
    })

    renderWithProviders(<SetupPage />)
    const [first] = await screen.findAllByRole('button', { name: '刪除這條 Route' })
    await userEvent.click(first)
    await userEvent.click(screen.getByRole('button', { name: '確定刪除' }))

    expect(await screen.findByText(/刪不得/)).toBeInTheDocument()
    expect(screen.queryByText(/沒在跑/)).not.toBeInTheDocument()
  })

  it('停用中的紅燈 Route 不讓媒體庫路徑那一格變紅：它不是目的地，完成條件也不算它（票 14）', async () => {
    const withDisabledRed = routeSetup({
      ...BUILT,
      routes: [
        ...BUILT.routes,
        routeView({ id: 9, library: 'TV', slug: 'tv-2', enabled: false, health: 'failed' }),
      ],
    })
    stubPage({ ...PAST_ROUTES, [ROUTES]: { body: withDisabledRed } })

    renderWithProviders(<SetupPage />)
    const board = await screen.findByRole('region', { name: '泊位板' })

    await waitFor(() =>
      expect(within(board).getByText('BTH 3').closest('li')).toHaveTextContent('已完成'),
    )
  })

  /** 後端過了這一頁才是已繫上：套件內的清單也要建完（後端 `libraries_built`）。 */
  it('泊位板的媒體庫路徑那一格在後端過了頁 3 之後標成已繫上', async () => {
    stubPage({ ...PAST_ROUTES, [ROUTES]: { body: BUILT } })

    renderWithProviders(<SetupPage />)
    const board = await screen.findByRole('region', { name: '泊位板' })

    await waitFor(() =>
      expect(within(board).getByText('BTH 3').closest('li')).toHaveTextContent('已完成'),
    )
  })

  it('Route 全綠但後端還停在頁 3 時，那一格仍是待靠泊', async () => {
    stubPage({ ...BUNDLED_PAGE, [ROUTES]: { body: BUILT } })

    renderWithProviders(<SetupPage />)
    await screen.findByRole('button', { name: '重新檢查 3 條 Route' })
    const board = screen.getByRole('region', { name: '泊位板' })

    expect(within(board).getByText('BTH 3').closest('li')).toHaveTextContent('待靠泊')
  })
})

describe('頁 3 的前進條件跟畫面一致（M4 票 24）', () => {
  const RED_OLD = routeView({ id: 9, library: 'Old', slug: 'old', health: 'failed' })

  it('刪掉紅的 Route 之後重讀進度：後端過了頁 3 就出現前往下一個泊位，畫面不跳頁、不必重新整理', async () => {
    let deleted = false
    const withRed = routeSetup({ ...BUILT, routes: [...BUILT.routes, RED_OLD], ready: false })
    const routes = () => ({ body: deleted ? BUILT : withRed })
    stubPage({
      ...BUNDLED_PAGE,
      ...PAST_ROUTES,
      [STATUS]: () => ({ body: deleted ? PAST_ROUTES[STATUS].body : AT_ROUTES }),
      [ROUTES]: routes,
      [REREAD]: routes,
      'DELETE /api/setup/routes/9': () => {
        deleted = true
        return { status: 204, body: null }
      },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    const buttons = await screen.findAllByRole('button', { name: '刪除這條 Route' })
    expect(screen.queryByRole('button', { name: '前往下一個泊位' })).not.toBeInTheDocument()
    await user.click(buttons[buttons.length - 1])
    await user.click(screen.getByRole('button', { name: '確定刪除' }))

    expect(await screen.findByRole('button', { name: '前往下一個泊位' })).toBeVisible()
    // 停在結果上（票 06d）：後端已到頁 4，畫面仍是這一頁，按了才走。
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('媒體庫路徑')
  })

  it('既有：刪掉 Route 之後，它的媒體庫在勾選表上取消勾選，不會在下一次又被送出去', async () => {
    const nas = routeSetup({
      origin: 'existing',
      libraries: [
        libraryChoice({ name: '影集', target_path: '/data/library/影集', listed: false }),
      ],
    })
    const routed = routeSetup({
      ...nas,
      libraries: [{ ...nas.libraries[0], has_route: true }],
      routes: [routeView({ library: '影集', slug: '影集', health: 'failed' })],
    })
    let state = nas
    const routes = () => ({ body: state })
    stubPage({
      ...EXISTING_PAGE,
      [ROUTES]: routes,
      [REREAD]: routes,
      [BUILD]: () => {
        state = routed
        return { body: routed }
      },
      'DELETE /api/setup/routes/2': () => {
        state = nas
        return { status: 204, body: null }
      },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await user.click(await screen.findByRole('checkbox', { name: '影集' }))
    await user.click(screen.getByRole('button', { name: '建立並檢查' }))
    await user.click(await screen.findByRole('button', { name: '刪除這條 Route' }))
    await user.click(screen.getByRole('button', { name: '確定刪除' }))

    await waitFor(() =>
      expect(screen.queryByRole('button', { name: '刪除這條 Route' })).not.toBeInTheDocument(),
    )
    expect(screen.getByRole('checkbox', { name: '影集' })).not.toBeChecked()
  })

  it('套件內進頁也向 Jellyfin 重讀；不在清單上的媒體庫不列進這一輪要建的 Route', async () => {
    const withOld = routeSetup({
      libraries: [
        ...routeSetup().libraries,
        libraryChoice({
          name: 'Old',
          collection_type: 'movies',
          locations: ['/mnt/old'],
          listed: false,
        }),
      ],
    })
    const fetch = stubPage({
      ...BUNDLED_PAGE,
      [ROUTES]: { body: withOld },
      [REREAD]: { body: withOld },
    })

    renderWithProviders(<SetupPage />)

    const plan = (await screen.findByRole('heading', { name: '將建立' })).closest('section')!
    expect(within(plan).getByText('Anime')).toBeInTheDocument()
    expect(within(plan).queryByText('Old')).not.toBeInTheDocument()
    expect(screen.queryByText('/mnt/old')).not.toBeInTheDocument()
    await waitFor(() =>
      expect(
        fetch.mock.calls.some(
          ([input, init]) => init?.method === 'POST' && input === '/api/setup/routes/libraries',
        ),
      ).toBe(true),
    )
  })

  it('套件內按下之後先重讀再存清單：Jellyfin 裡少了清單上的一列，就先把它建回來', async () => {
    const animeGone = jellyfinSetup({
      steps: SEQUENCE_DONE,
      api_key_present: true,
      bundled: jellyfinSetup().bundled.map((row) => ({ ...row, built: row.name !== 'Anime' })),
    })
    const fetch = stubPage({
      ...BUNDLED_PAGE,
      [ROUTES]: { body: routeSetup() },
      [REREAD]: { body: routeSetup() },
      'PUT /api/setup/jellyfin/bundled': { body: animeGone },
      'POST /api/setup/jellyfin/bootstrap': { body: BUNDLED_PAGE[JELLYFIN].body },
      [BUILD]: { body: BUILT },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await user.click(await screen.findByRole('button', { name: '建立並檢查' }))

    await waitFor(() => expect(writes(fetch)).toContain(BUILD))
    const posts = fetch.mock.calls
      .filter(([, init]) => (init?.method ?? 'GET') !== 'GET')
      .map(([input, init]) => `${init?.method} ${String(input)}`)
    expect(posts.slice(-4)).toEqual([
      REREAD,
      'PUT /api/setup/jellyfin/bundled',
      'POST /api/setup/jellyfin/bootstrap',
      BUILD,
    ])
  })
})

describe('頁 3 的失敗', () => {
  it('EXDEV 指出兩個目錄是不同掛載，並附三個容器的 compose 片段', async () => {
    const blocked = routeSetup({
      routes: [
        routeView({
          library: 'TV',
          health: 'failed',
          cross_device: true,
          checks: [
            ...CHECKS_PASSED.slice(0, 5),
            step('hardlink', 'failed', '', '[Errno 18] Invalid cross-device link'),
          ],
        }),
      ],
    })
    stubPage({ ...BUNDLED_PAGE, [ROUTES]: { body: blocked } })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByText('[Errno 18] Invalid cross-device link')).toBeInTheDocument()
    expect(screen.getByText(/EXDEV/)).toBeInTheDocument()
    expect(screen.getByText(/berth:\s+volumes:/)).toBeInTheDocument()
  })

  it('Jellyfin 看不到探測檔時說的是 jellyfin 少了掛載', async () => {
    const blocked = routeSetup({
      routes: [
        routeView({
          library: 'TV',
          health: 'failed',
          checks: [
            ...CHECKS_PASSED.slice(0, 3),
            step('probe_visible', 'failed', '', 'Jellyfin cannot see /data/library/tv'),
            step('hardlink', 'pending'),
          ],
        }),
      ],
    })
    stubPage({ ...BUNDLED_PAGE, [ROUTES]: { body: blocked } })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByText('Jellyfin cannot see /data/library/tv')).toBeInTheDocument()
    expect(screen.getByText(/jellyfin 容器少了這條路徑的掛載/)).toBeInTheDocument()
    // 套件內的那一台就在 compose 裡：不說「多半在另一台主機」（那一句只給既有的，雙向）。
    expect(screen.queryByText(/另一台主機/)).not.toBeInTheDocument()
  })

  it('category 已存在但路徑不同時說明不覆寫的理由', async () => {
    const blocked = routeSetup({
      routes: [
        routeView({
          library: 'TV',
          health: 'failed',
          checks: [
            step('category', 'failed', '', "category 'berth-tv' already points at '/mnt/old/tv'"),
            ...CHECKS_PASSED.slice(1).map((row) => step(row.step, 'pending')),
          ],
        }),
      ],
    })
    stubPage({ ...BUNDLED_PAGE, [ROUTES]: { body: blocked } })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByText(/already points at/)).toBeInTheDocument()
    expect(screen.getByText(/autoTMM/)).toBeInTheDocument()
  })

  /**
   * 票 02a。這一步順帶重跑既有 Route 的檢查，途中被另一個分頁刪掉的那一條是 404
   * `route_missing`（票 01）。原本這裡只吃 `build.isError`，畫面因此說「後端可能沒在跑」
   * ——既不是原因也不是下一步（PRODUCT 原則 4）。
   */
  it('建立途中有 Route 被刪掉：說出是哪一種失敗與下一步，不說後端沒在跑', async () => {
    stubPage({
      ...BUNDLED_PAGE,
      [ROUTES]: { body: routeSetup() },
      [BUILD]: {
        status: 404,
        body: { detail: { reason: 'route_missing', detail: '2' } },
      },
    })

    renderWithProviders(<SetupPage />)
    await userEvent.click(await screen.findByRole('button', { name: '建立並檢查' }))

    const notice = await screen.findByText(/被刪掉了/)
    expect(notice).toHaveTextContent('重新檢查了既有的 Route')
    expect(notice).toHaveTextContent('重新整理這一步')
    expect(screen.queryByText(/後端可能沒在跑/)).not.toBeInTheDocument()
  })

  it('認不得的失敗仍落回那句通用的話：只有說得出原因時才換掉它', async () => {
    stubPage({
      ...BUNDLED_PAGE,
      [ROUTES]: { body: routeSetup() },
      [BUILD]: { status: 500, body: { detail: 'boom' } },
    })

    renderWithProviders(<SetupPage />)
    await userEvent.click(await screen.findByRole('button', { name: '建立並檢查' }))

    expect(await screen.findByText(/後端出錯了/)).toBeInTheDocument()
    expect(screen.queryByText(/被刪掉了/)).not.toBeInTheDocument()
  })
})

describe('頁 3 的失敗：既有服務說出怎麼改掛載（M4 票 08）', () => {
  /** 既有 Jellyfin、既有 qBittorrent，一條紅的 Route。 */
  function yours(route: RouteView) {
    return {
      [STATUS]: {
        body: setupStatus({
          ...AT_ROUTES,
          services: [
            chosen({ origin: 'existing', base_url: 'http://nas:8096', reason: 'setup_completed' }),
            chosen({ kind: 'qbittorrent', origin: 'existing', base_url: 'http://nas:8080' }),
          ],
        }),
      },
      [JELLYFIN]: EXISTING_PAGE[JELLYFIN],
      [ROUTES]: {
        body: routeSetup({
          origin: 'existing',
          libraries: [libraryChoice({ name: 'TV', has_route: true })],
          routes: [route],
        }),
      },
    }
  }

  it('Jellyfin 看不到探測檔：補法與片段是你那一台 Jellyfin 的，不是 berth（票 19）', async () => {
    stubApi(
      yours(
        routeView({
          health: 'failed',
          checks: [
            ...CHECKS_PASSED.slice(0, 4),
            step('probe_visible', 'failed', '', 'Jellyfin cannot see /data/library/tv'),
            step('hardlink', 'pending'),
          ],
        }),
      ),
    )

    renderWithProviders(<SetupPage />)

    expect(await screen.findByText(/你的 Jellyfin 看不到 Berth 剛寫的檔案/)).toBeInTheDocument()
    expect(screen.getByText(/不做 remote path mapping/)).toBeInTheDocument()
    expect(screen.getByText(/jellyfin:\s+volumes:/)).toBeInTheDocument()
    expect(screen.queryByText(/berth:\s+volumes:/)).not.toBeInTheDocument()
  })

  it('qBittorrent 讀不到 Berth 寫的探測檔：紅在那一條、說它少了 /data，片段是 qBittorrent 的', async () => {
    stubApi(
      yours(
        routeView({
          health: 'failed',
          checks: [
            ...CHECKS_PASSED.slice(0, 2),
            step(
              'download_visible',
              'failed',
              '',
              'qBittorrent cannot see /data/torrent/complete/tv: it checked the file Berth had just written there and found none of it (0% after a recheck)',
            ),
            ...CHECKS_PASSED.slice(3).map((row) => step(row.step, 'pending')),
          ],
        }),
      ),
    )

    renderWithProviders(<SetupPage />)

    expect(
      await screen.findByText(/qBittorrent cannot see \/data\/torrent\/complete\/tv/),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/你的 qBittorrent 看不到這個分類路徑：它多半沒掛 \/data/),
    ).toBeInTheDocument()
    expect(screen.getByText(/qbittorrent:\s+volumes:/)).toBeInTheDocument()
  })

  it('EXDEV：你的服務多半分開掛載，改成同一個父目錄', async () => {
    stubApi(
      yours(
        routeView({
          health: 'failed',
          cross_device: true,
          checks: [
            ...CHECKS_PASSED.slice(0, 5),
            step('hardlink', 'failed', '', '[Errno 18] Invalid cross-device link'),
          ],
        }),
      ),
    )

    renderWithProviders(<SetupPage />)

    expect(await screen.findByText(/分開掛（\/downloads、\/tv 各一條）/)).toBeInTheDocument()
  })

  it('Berth 看不到 qBittorrent 報的路徑：說同一台主機、同一個容器路徑', async () => {
    stubApi(
      yours(
        routeView({
          health: 'failed',
          checks: [
            CHECKS_PASSED[0],
            step(
              'download_path',
              'failed',
              '',
              '/downloads/tv is not visible from the Berth container',
            ),
            ...CHECKS_PASSED.slice(2).map((row) => step(row.step, 'pending')),
          ],
        }),
      ),
    )

    renderWithProviders(<SetupPage />)

    expect(await screen.findByText(/這是你自己的 qBittorrent/)).toBeInTheDocument()
    expect(screen.queryByText(/這是你自己的 Jellyfin/)).not.toBeInTheDocument()
  })
})

describe('頁 3：媒體庫路徑（既有 Jellyfin）', () => {
  const NAS = routeSetup({
    origin: 'existing',
    libraries: [
      libraryChoice({
        name: '影集',
        locations: ['/volume1/media/tv', '/data/library/影集'],
        berth_path: '/data/library/影集',
        target_path: '',
      }),
      libraryChoice({ name: '音樂', collection_type: 'music', supported: false, locations: [] }),
    ],
  })

  it('一個都沒勾時建立鍵按不下去', async () => {
    stubPage({ ...EXISTING_PAGE, [ROUTES]: { body: NAS } })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByRole('button', { name: '建立並檢查' })).toBeDisabled()
  })

  it('勾了媒體庫再選一條路徑，送出去的就是那一條', async () => {
    const fetch = stubPage({
      ...EXISTING_PAGE,
      [ROUTES]: { body: NAS },
      [BUILD]: { body: NAS },
    })

    renderWithProviders(<SetupPage />)
    await userEvent.click(await screen.findByRole('checkbox', { name: '影集' }))
    await userEvent.click(screen.getByRole('radio', { name: '/data/library/影集' }))
    await userEvent.click(screen.getByRole('button', { name: '建立並檢查' }))

    await waitFor(() => {
      const call = fetch.mock.calls.find(
        ([input, init]) => init?.method === 'POST' && input === '/api/setup/routes',
      )
      expect(call).toBeDefined()
      expect(JSON.parse(String(call![1]?.body))).toEqual({
        selections: [{ library: '影集', target_path: '/data/library/影集' }],
      })
    })
  })

  it('不是電影或劇集的媒體庫不給勾，並說明理由', async () => {
    stubPage({ ...EXISTING_PAGE, [ROUTES]: { body: NAS } })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByText('音樂')).toBeInTheDocument()
    expect(screen.queryByRole('checkbox', { name: '音樂' })).not.toBeInTheDocument()
    expect(screen.getByText(/只寫入電影與劇集/)).toBeInTheDocument()
  })

  /**
   * 票 03 第 6 條。已經被佔用的路徑本來得按下「建立並檢查」被後端退回來（422）才知道，
   * 而那時候畫面只說得出「請求沒有走完」。`/settings/routes` 的新增表早就是這樣做的。
   */
  it('已經被別條 Route 佔用的路徑在勾選表上就標出來，選不了', async () => {
    const shared = routeSetup({
      origin: 'existing',
      libraries: [
        libraryChoice({
          name: '影集',
          locations: ['/volume1/media/tv', '/data/library/影集'],
          target_path: '',
        }),
      ],
      routes: [routeView({ name: '舊影集', library: '別的庫', target_path: '/volume1/media/tv' })],
    })
    stubPage({ ...EXISTING_PAGE, [ROUTES]: { body: shared } })

    renderWithProviders(<SetupPage />)
    await userEvent.click(await screen.findByRole('checkbox', { name: '影集' }))

    const taken = screen.getByRole('radio', { name: /\/volume1\/media\/tv/ })
    expect(taken).toBeDisabled()
    // 佔著它的那條 Route 的名字就在那一行上，而且掛進了這顆 radio 的可存取描述。
    expect(taken).toHaveAccessibleDescription('已是「舊影集」')
    // 沒被佔的那一條照樣選得起來。
    expect(screen.getByRole('radio', { name: /\/data\/library\/影集/ })).toBeEnabled()
  })

  it('已經有 Route 的媒體庫在勾選表上鎖住：重跑不改也不刪它（票 14）', async () => {
    const routed = routeSetup({
      origin: 'existing',
      libraries: [
        libraryChoice({ name: '影集', has_route: true, target_path: '/data/library/影集' }),
      ],
      routes: [routeView({ library: '影集', slug: '影集', target_path: '/data/library/影集' })],
    })
    stubPage({ ...EXISTING_PAGE, [ROUTES]: { body: routed } })

    renderWithProviders(<SetupPage />)

    const box = await screen.findByRole('checkbox', { name: '影集' })
    expect(box).toBeChecked()
    expect(box).toBeDisabled()
    expect(screen.getByText(/精靈只新增/)).toBeInTheDocument()
    // 沒有新勾的東西時，這一顆是「全部重驗」而不是一顆按不下去的建立鍵。
    expect(screen.getByRole('button', { name: '重新檢查 1 條 Route' })).toBeEnabled()
  })
})

describe('頁 6：完成', () => {
  it('列出跑出來的 Route 與跳過的索引站、在哪裡補', async () => {
    stubPage({
      [STATUS]: { body: AT_THE_END },
      [ROUTES]: { body: BUILT },
      [INDEXERS]: { body: indexerSetup({ skipped: true }) },
      [TMDB]: { body: tmdbSetup() },
    })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByRole('button', { name: '完成設定' })).toBeInTheDocument()
    expect(screen.getByText('/data/torrent/complete/tv')).toBeInTheDocument()
    expect(screen.getByText(/索引站還沒接/)).toBeInTheDocument()
    expect(screen.getByText(/五個泊位/)).toBeInTheDocument()
    // 之後拿什麼登入：擁有者的 Jellyfin 帳號（M4 票 06），套件內與既有同一句。
    expect(screen.getByText(/你是 skipper/)).toBeInTheDocument()
  })

  it('跳過索引站但 Prowlarr 上已經有站：照實際站數說，不說搜尋不到任何東西（M4 票 27）', async () => {
    stubPage({
      [STATUS]: { body: AT_THE_END },
      [ROUTES]: { body: BUILT },
      [INDEXERS]: {
        body: indexerSetup({
          skipped: true,
          sites: [site({ definition_name: 'nyaasi', name: 'Nyaa.si' }, 1)],
        }),
      },
      [TMDB]: { body: tmdbSetup() },
    })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByRole('button', { name: '完成設定' })).toBeInTheDocument()
    expect(screen.getByText(/Prowlarr 上已經有 1 個站/)).toBeInTheDocument()
    expect(screen.queryByText(/搜尋不到任何東西/)).not.toBeInTheDocument()
  })

  /**
   * 票 03 第 5 條。後端的 422 是「不可跳的那幾步還沒做完」（`services/setup.py` 的兩個
   * `ValueError`），不是後端掛了——原本兩種都說「Berth 後端可能沒在跑」，把使用者送去看容器。
   */
  it('缺 TMDB 憑證時說的是 TMDB 那一步沒做完，不是後端出錯', async () => {
    stubPage({
      [STATUS]: { body: AT_THE_END },
      [ROUTES]: { body: BUILT },
      [INDEXERS]: { body: indexerSetup() },
      [TMDB]: { body: tmdbSetup({ api_key_present: false, verified: false }) },
      [COMPLETE]: { status: 422, body: { detail: 'finish step 7 first: TMDB needs a credential' } },
    })

    renderWithProviders(<SetupPage />)
    await userEvent.click(await screen.findByRole('button', { name: '完成設定' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/TMDB/)
    expect(alert).not.toHaveTextContent(/後端/)
    // 修的地方在 TMDB 那一頁（頁 5），所以出口也在這裡。
    expect(screen.getByRole('button', { name: '回去填 TMDB key' })).toBeInTheDocument()
  })

  /**
   * 票 03 code review：`tmdb.verified` 還沒載回來時原本會一律說「TMDB 那一步」，
   * 即使真正卡住的是 Route。兩份狀態都說沒問題卻仍被擋，就別指名。
   */
  it('422 但手上這份看不出是哪一步時，不硬指一步也不怪後端', async () => {
    stubPage({
      [STATUS]: { body: AT_THE_END },
      [ROUTES]: { body: BUILT },
      [INDEXERS]: { body: indexerSetup() },
      [TMDB]: { body: tmdbSetup({ api_key_present: true, verified: true }) },
      [COMPLETE]: { status: 422, body: { detail: 'some newer precondition' } },
    })

    renderWithProviders(<SetupPage />)
    await userEvent.click(await screen.findByRole('button', { name: '完成設定' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/看不出是哪一步/)
    expect(alert).not.toHaveTextContent(/後端/)
    expect(screen.queryByRole('button', { name: '回去填 TMDB key' })).not.toBeInTheDocument()
  })

  it('後端真的掛了時才說是後端', async () => {
    stubPage({
      [STATUS]: { body: AT_THE_END },
      [ROUTES]: { body: BUILT },
      [INDEXERS]: { body: indexerSetup() },
      [TMDB]: { body: tmdbSetup({ api_key_present: true, verified: true }) },
      [COMPLETE]: { status: 500, body: { detail: 'boom' } },
    })

    renderWithProviders(<SetupPage />)
    await userEvent.click(await screen.findByRole('button', { name: '完成設定' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/後端/)
  })

  // M4 票 06：擁有者從第 1 步起就登入著，精靈跑完直接落在探索（媒體庫這時必然是空的，
  // 第一件事是找片，brief §19 2026-09-26），不必再登入一次，也不再被導回精靈。
  it('按下完成之後精靈關閉，擁有者直接落在探索', async () => {
    let completed = false
    const backend = session({ name: 'skipper', role: 'admin' })
    stubPage({
      'GET /api/health': () => ({
        body: {
          status: 'ok',
          version: '0.1.0',
          setup_completed: completed,
          owner_established: true,
        },
      }),
      [STATUS]: { body: AT_THE_END },
      [ROUTES]: { body: BUILT },
      [INDEXERS]: { body: indexerSetup() },
      [TMDB]: { body: tmdbSetup() },
      [COMPLETE]: () => {
        completed = true
        return { body: { ...AT_THE_END, completed: true } }
      },
      'GET /api/auth/me': () => backend.me(),
      'GET /api/discover/trending': discoverWall(),
      'GET /api/discover/popular': discoverWall(),
    })

    const { router } = renderApp('/setup')
    await userEvent.click(await screen.findByRole('button', { name: '完成設定' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/'))
    expect(screen.queryByLabelText('Jellyfin 帳號')).not.toBeInTheDocument()
  })

  it('擁有者成立之後、精靈跑完之前沒有 session 的人被送去登入，登入之後回到精靈', async () => {
    const backend = session()
    stubPage({
      'GET /api/health': {
        body: { status: 'ok', version: '0.1.0', setup_completed: false, owner_established: true },
      },
      [STATUS]: { body: AT_THE_END },
      [ROUTES]: { body: BUILT },
      [INDEXERS]: { body: indexerSetup() },
      [TMDB]: { body: tmdbSetup() },
      'GET /api/auth/me': () => backend.me(),
      'POST /api/auth/login': backend.signIn({ name: 'skipper', role: 'admin' }),
    })

    const { router } = renderApp('/setup')

    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    expect(router.state.location.search).toEqual({ redirect: '/setup' })
    await userEvent.type(await screen.findByLabelText('Jellyfin 帳號'), 'skipper')
    await userEvent.type(screen.getByLabelText('密碼'), 'harbour')
    await userEvent.click(screen.getByRole('button', { name: '登入' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/setup'))
    expect(await screen.findByRole('button', { name: '完成設定' })).toBeInTheDocument()
  })
})
