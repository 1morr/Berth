import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { stubApi, type StubRoute } from '../test/fetch'
import { renderInRoute } from '../test/render'
import {
  ALL_BUNDLED,
  CHECKS_PASSED,
  SEQUENCE_DONE,
  chosen,
  jellyfinSetup,
  routeSetup,
  routeView,
  setupStatus,
  step,
} from '../test/fixtures'
import { type JellyfinSetup } from '../api/setup'
import { type RouteView } from '../api/schemas'
import { SetupPage } from './SetupPage'

/**
 * 頁 3 套件內進頁自動建立並檢查、顯示進度（M4 票 43，`.scratch/m4/route-auto-run-shape.md`）。
 *
 * 只在「什麼都還沒做」時自動送一次：清單是預設、沒有建好的媒體庫、沒有 Route、建媒體庫那一步從沒跑過。
 * 其餘一律是按鍵（票 08 的「進頁不送寫入」只留給既有與跑過一次之後）。
 */

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

const STATUS = 'GET /api/setup/status'
const ROUTES = 'GET /api/setup/routes'
const BUILD = 'POST /api/setup/routes'
const REREAD = 'POST /api/setup/routes/libraries'
const JELLYFIN = 'GET /api/setup/jellyfin'
const SAVE = 'PUT /api/setup/jellyfin/bundled'
const BOOTSTRAP = 'POST /api/setup/jellyfin/bootstrap'

const AT_ROUTES = setupStatus({
  current_step: 3,
  owner: 'skipper',
  services: ALL_BUNDLED.slice(0, 2),
})

/** 頁 1 剛做完：擁有者與 key 都有了，建媒體庫那一步還沒跑過。 */
const OWNER_DONE = SEQUENCE_DONE.filter((row) => row.step !== 'libraries')

/** 第一次走到頁 3 的套件內 Jellyfin：預設清單、一個都還沒建。 */
const FRESH = jellyfinSetup({ steps: OWNER_DONE, api_key_present: true, bundled_default: true })

const BUILT_LIST = jellyfinSetup({
  steps: SEQUENCE_DONE,
  api_key_present: true,
  bundled_default: true,
  bundled: FRESH.bundled.map((row) => ({ ...row, built: true })),
})

const BUILT = routeSetup({
  routes: [
    routeView({ id: 1, library: 'Movies', slug: 'movies', collection_type: 'movies' }),
    routeView({ id: 2, library: 'TV', slug: 'tv' }),
    routeView({ id: 3, library: 'Anime', slug: 'anime' }),
  ],
  libraries: routeSetup().libraries.map((row) => ({ ...row, has_route: true })),
  ready: true,
})

function page(
  jellyfin: JellyfinSetup,
  extra: Record<string, StubRoute | (() => StubRoute | Promise<StubRoute>)> = {},
) {
  return stubApi({
    [STATUS]: { body: AT_ROUTES },
    [JELLYFIN]: { body: jellyfin },
    [ROUTES]: { body: routeSetup() },
    [REREAD]: { body: routeSetup() },
    [SAVE]: { body: jellyfin },
    [BOOTSTRAP]: { body: BUILT_LIST },
    [BUILD]: { body: BUILT },
    ...extra,
  })
}

/** 送出去的寫入（非 GET），依序；重讀媒體庫不算（它只換 Berth 自己的快照，M4 票 19）。 */
function writes(fetch: ReturnType<typeof stubApi>): string[] {
  return fetch.mock.calls
    .filter(([, init]) => (init?.method ?? 'GET') !== 'GET')
    .map(([input, init]) => `${init?.method} ${String(input)}`)
    .filter((call) => call !== REREAD)
}

/** 跑到第 `at` 條纜繩（0 起算）的一條 Route：前面的過了、這一條 `running`、後面 `pending`。 */
function checking(route: RouteView, at: number): RouteView {
  return {
    ...route,
    health: 'unknown',
    checks: CHECKS_PASSED.map((row, index) =>
      index < at ? row : step(row.step, index === at ? 'running' : 'pending'),
    ),
  }
}

function routeList(): HTMLElement {
  return screen.getByRole('list', { name: '這一頁的 Route' })
}

function fresh(route: RouteView): RouteView {
  return { ...route, health: 'unknown', checks: [], checked_at: null, last_ok_at: null }
}

describe('頁 3 套件內：什麼都還沒做時進頁自動建立並檢查（M4 票 43）', () => {
  it('預設清單、一個都還沒建：不必按，照順序存清單、建媒體庫、建 Route 與檢查', async () => {
    const fetch = page(FRESH)

    renderInRoute(<SetupPage />)

    await waitFor(() => expect(writes(fetch)).toEqual([SAVE, BOOTSTRAP, BUILD]))
    expect(await screen.findAllByText('6 / 6 通過')).toHaveLength(3)
    // 為什麼沒按就開始了，說一句；讀屏念得到。
    expect(screen.getByText(/預設清單沒改過/)).toBeInTheDocument()
  })

  it('跑完之後清單收成一列，要加一個再展開', async () => {
    page(FRESH, { [JELLYFIN]: { body: FRESH } })

    renderInRoute(<SetupPage />)

    expect(await screen.findAllByText('6 / 6 通過')).toHaveLength(3)
    const list = screen.getByText('媒體庫清單').closest('details')!
    expect(list).not.toHaveAttribute('open')
  })

  it('清單被改過：不自動跑，等人按「建立並檢查」', async () => {
    const fetch = page({ ...FRESH, bundled_default: false })

    renderInRoute(<SetupPage />)

    expect(await screen.findByRole('button', { name: '建立並檢查' })).toBeEnabled()
    await new Promise((resolve) => setTimeout(resolve, 900))
    expect(writes(fetch)).toEqual([])
  })

  it('跑過一次（建媒體庫那一步紅了）之後回到這一頁：不再自動送，按鍵還在', async () => {
    const failedOnce = {
      ...FRESH,
      steps: [...OWNER_DONE, step('libraries', 'failed', '', 'POST /Library/VirtualFolders: 500')],
    }
    const fetch = page(failedOnce)

    renderInRoute(<SetupPage />)

    expect(await screen.findByRole('button', { name: '建立並檢查' })).toBeEnabled()
    await new Promise((resolve) => setTimeout(resolve, 900))
    expect(writes(fetch)).toEqual([])
  })

  it('已經有 Route（建過、重新整理回來）：不自動送', async () => {
    const fetch = page(BUILT_LIST, { [ROUTES]: { body: BUILT }, [REREAD]: { body: BUILT } })

    renderInRoute(<SetupPage />)

    expect(await screen.findAllByText('6 / 6 通過')).toHaveLength(3)
    await new Promise((resolve) => setTimeout(resolve, 900))
    expect(writes(fetch)).toEqual([])
  })

  it('既有 Jellyfin：照舊不自動跑', async () => {
    const fetch = stubApi({
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
        body: jellyfinSetup({
          origin: 'existing',
          base_url: 'http://nas:8096',
          api_key_present: true,
          steps: OWNER_DONE,
          bundled_default: true,
        }),
      },
      [ROUTES]: { body: routeSetup({ origin: 'existing' }) },
      [REREAD]: { body: routeSetup({ origin: 'existing' }) },
    })

    renderInRoute(<SetupPage />)

    expect(await screen.findByRole('button', { name: '建立並檢查' })).toBeInTheDocument()
    await new Promise((resolve) => setTimeout(resolve, 900))
    expect(writes(fetch)).toEqual([])
  })
})

describe('頁 3 的進度：逐條 Route、逐條纜繩（M4 票 43）', () => {
  it('建媒體庫時說在建；Route 先畫成等待中，跑到哪一條就說哪一條，跑完是通過', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const [movies, tv, anime] = BUILT.routes as [RouteView, RouteView, RouteView]
    const building = {
      ...FRESH,
      steps: [...OWNER_DONE, step('libraries', 'running')],
    }
    let finishBootstrap: (value: StubRoute) => void = () => {}
    let finishBuild: (value: StubRoute) => void = () => {}
    const polls: RouteView[][] = [
      [checking(movies, 4), fresh(tv), fresh(anime)],
      [{ ...movies }, checking(tv, 2), fresh(anime)],
    ]
    // Jellyfin 上還沒有任何媒體庫；建好之後輪詢才讀得到 Route，一次比一次跑得遠。
    let bootstrapping = false
    let bootstrapped = false
    let routeReads = 0
    const nothingYet = routeSetup({ libraries: [] })
    page(FRESH, {
      [JELLYFIN]: () => ({ body: bootstrapped ? BUILT_LIST : bootstrapping ? building : FRESH }),
      [REREAD]: { body: nothingYet },
      [ROUTES]: () => {
        if (!bootstrapped) return { body: nothingYet }
        routeReads += 1
        return { body: routeSetup({ routes: polls[Math.min(routeReads - 1, polls.length - 1)] }) }
      },
      [BOOTSTRAP]: () => {
        bootstrapping = true
        return new Promise<StubRoute>((resolve) => (finishBootstrap = resolve))
      },
      [BUILD]: () => new Promise<StubRoute>((resolve) => (finishBuild = resolve)),
    })

    renderInRoute(<SetupPage />)

    // 建媒體庫那一段：Jellyfin 那一條纜繩在跑，三條 Route 先畫成等待中。
    await vi.advanceTimersByTimeAsync(1500)
    expect(await screen.findByText('建立清單上的媒體庫')).toBeInTheDocument()
    expect(within(routeList()).getAllByText('等待中')).toHaveLength(3)

    bootstrapped = true
    finishBootstrap({ body: BUILT_LIST })
    // 建完媒體庫、Route 還沒讀到的那一下：等待列不消失。
    await vi.advanceTimersByTimeAsync(10)
    expect(within(routeList()).getAllByText('等待中')).toHaveLength(3)
    await vi.advanceTimersByTimeAsync(1500)
    expect(
      await screen.findByText('第 5 / 6 條 · Jellyfin 看得到 Berth 寫的檔案'),
    ).toBeInTheDocument()
    expect(within(routeList()).getAllByText('等待中')).toHaveLength(2)

    await vi.advanceTimersByTimeAsync(1500)
    expect(
      await screen.findByText('第 3 / 6 條 · qBittorrent 讀得到 Berth 寫的檔案'),
    ).toBeInTheDocument()
    expect(screen.getAllByText('6 / 6 通過')).toHaveLength(1)

    finishBuild({ body: BUILT })
    await waitFor(() => expect(screen.getAllByText('6 / 6 通過')).toHaveLength(3))
    expect(screen.queryByText('等待中')).not.toBeInTheDocument()
    expect(screen.queryByText('檢查中')).not.toBeInTheDocument()
    expect(screen.queryByText(/^第 \d \/ 6 條/)).not.toBeInTheDocument()
  })

  it('跑到一半重新整理：不再送一次，照伺服器的狀態接著輪詢到跑完', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const [movies, tv, anime] = BUILT.routes as [RouteView, RouteView, RouteView]
    let routeReads = 0
    const fetch = page(BUILT_LIST, {
      [ROUTES]: () => {
        routeReads += 1
        return {
          body:
            routeReads < 3
              ? routeSetup({ routes: [{ ...movies }, checking(tv, 1), fresh(anime)] })
              : BUILT,
        }
      },
      [REREAD]: { body: routeSetup({ routes: [{ ...movies }, checking(tv, 1), fresh(anime)] }) },
    })

    renderInRoute(<SetupPage />)

    expect(
      await screen.findByText('第 2 / 6 條 · qBittorrent 的路徑 Berth 看得到'),
    ).toBeInTheDocument()
    // 這一頁沒有送出中的請求，但伺服器那一輪還在跑：還沒輪到的照樣說等待中。
    expect(within(routeList()).getAllByText('等待中')).toHaveLength(1)
    await vi.advanceTimersByTimeAsync(3000)
    await waitFor(() => expect(screen.getAllByText('6 / 6 通過')).toHaveLength(3))
    expect(writes(fetch)).toEqual([])
  })
})
