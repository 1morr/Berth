import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { RouteView } from '../api/schemas'
import { HEALTHY, stubApi, type StubRoute } from '../test/fetch'
import {
  ALL_BUNDLED,
  CHECKS_PASSED,
  chosen,
  healthDetail,
  managedRoute,
  qbittorrentSetup,
  routeView,
  setupStatus,
  step,
} from '../test/fixtures'
import { renderApp } from '../test/render'

/**
 * 健康頁不再假綠、換台之後自動重查、「全部重新檢查」（M4 票 59，審計 P1-3）。每一條都雙向：該說「要重新
 * 檢查」的說了，該說「已繫上」的沒被拖下水。
 */

afterEach(() => {
  vi.unstubAllGlobals()
})

const RECHECK_ALL = 'POST /api/routes/check'

/** 換台之後作廢的那一種：檢查清空、從沒檢查過。 */
const VOIDED = routeView({
  health: 'unknown',
  checks: [],
  checked_at: null,
  last_ok_at: null,
  probed_at: null,
})

/** 探針從沒問過：其餘五條綠，那一條 `pending`（審計 S4 換回套件內的 5/6）。 */
const UNASKED = routeView({
  health: 'unknown',
  checks: CHECKS_PASSED.map((row) =>
    row.step === 'download_visible' ? step('download_visible', 'pending') : row,
  ),
  probed_at: null,
})

function boardSlot(code: string) {
  const board = screen.getByRole('region', { name: '泊位板' })
  return within(within(board).getByText(code).closest('li')!)
}

function routesWith(...routes: RouteView[]) {
  return routes.map((route, index) =>
    managedRoute({ route: { ...route, id: index + 1, slug: `r${index}`, name: `R${index}` } }),
  )
}

describe('健康頁的 Route 那一格說真話', () => {
  function render(routes: RouteView[], status: 'ok' | 'unknown', role = 'admin') {
    return stubApi({
      'GET /api/health': { body: HEALTHY },
      'GET /api/auth/me': { body: { name: 'skipper', role } },
      'GET /api/health/detail': {
        body: healthDetail({ routes_status: status, routes }),
      },
      [RECHECK_ALL]: { body: routes.map((route) => ({ ...route, health: 'ok' })) },
    })
  }

  it('換台之後的 Route 沒檢查過：BTH 3 說「要重新檢查」，不說「已繫上」，旁邊有一顆全部重新檢查', async () => {
    const stub = render([VOIDED, { ...VOIDED, id: 3, slug: 'movies' }], 'unknown')
    const user = userEvent.setup()
    renderApp('/health')

    await screen.findByRole('region', { name: '泊位板' })
    expect(boardSlot('BTH 3').getByText('要重新檢查')).toBeVisible()
    expect(boardSlot('BTH 3').queryByText('已繫上')).not.toBeInTheDocument()
    const section = within(screen.getByRole('region', { name: '媒體庫路徑' }))
    expect(section.getAllByText('要重新檢查')[0]).toBeVisible()

    await user.click(section.getByRole('button', { name: '全部重新檢查' }))

    await waitFor(() =>
      expect(
        stub.mock.calls.some(
          ([url, init]) => url === '/api/routes/check' && init?.method === 'POST',
        ),
      ).toBe(true),
    )
  })

  it('全綠時 BTH 3 是「已繫上」，沒有全部重新檢查那一顆', async () => {
    render([routeView()], 'ok')
    renderApp('/health')

    await screen.findByRole('region', { name: '泊位板' })
    expect(boardSlot('BTH 3').getByText('已繫上')).toBeVisible()
    expect(screen.queryByText('要重新檢查')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '全部重新檢查' })).not.toBeInTheDocument()
  })

  it('一般使用者看得到「要重新檢查」，但沒有那一顆（它打的是管理員的 /routes）', async () => {
    render([VOIDED], 'unknown', 'user')
    renderApp('/health')

    await screen.findByRole('region', { name: '泊位板' })
    expect(boardSlot('BTH 3').getByText('要重新檢查')).toBeVisible()
    expect(screen.queryByRole('button', { name: '全部重新檢查' })).not.toBeInTheDocument()
    expect(screen.getByText('設定頁只有管理員進得去，請管理員來看。')).toBeVisible()
  })

  it('Route 全部停用：不算進總結，還是「尚未檢查」，不叫人重新檢查', async () => {
    render([{ ...VOIDED, enabled: false }], 'unknown')
    renderApp('/health')

    await screen.findByRole('region', { name: '泊位板' })
    expect(boardSlot('BTH 3').getByText('尚未檢查')).toBeVisible()
    expect(screen.queryByRole('button', { name: '全部重新檢查' })).not.toBeInTheDocument()
  })

  it('一條 Route 都沒有：還是「尚未檢查」，不叫人重新檢查', async () => {
    render([], 'unknown')
    renderApp('/health')

    await screen.findByRole('region', { name: '泊位板' })
    expect(boardSlot('BTH 3').getByText('尚未檢查')).toBeVisible()
    expect(screen.queryByText('要重新檢查')).not.toBeInTheDocument()
  })

  it('探針從沒問過：那一條說還沒問過、去哪裡問，這條 Route 是「要重新檢查」', async () => {
    render([UNASKED], 'unknown')
    renderApp('/health')

    const section = within(await screen.findByRole('region', { name: '媒體庫路徑' }))
    expect(section.getAllByText('要重新檢查')).toHaveLength(2)
    expect(section.getByText('還沒問過這一台 qBittorrent')).toBeInTheDocument()
    expect(section.getByText(/到 Route 設定按「重新檢查」或「全部重新檢查」/)).toBeInTheDocument()
  })

  it('斷在前面的 Route 不說探針「還沒問過」：它是沒輪到，不是沒問', async () => {
    const broken = routeView({
      health: 'failed',
      checks: [
        step('category', 'failed', '', 'Forbidden'),
        ...CHECKS_PASSED.slice(1).map((row) => step(row.step, 'pending')),
      ],
    })
    render([broken], 'unknown')
    renderApp('/health')

    const section = within(await screen.findByRole('region', { name: '媒體庫路徑' }))
    expect(section.getAllByText('阻擋')[0]).toBeVisible()
    expect(section.queryByText('還沒問過這一台 qBittorrent')).not.toBeInTheDocument()
  })
})

describe('Route 設定頁的全部重新檢查', () => {
  function render(routes: ReturnType<typeof managedRoute>[]) {
    return stubApi({
      'GET /api/health': { body: HEALTHY },
      'GET /api/auth/me': { body: { name: 'skipper', role: 'admin' } },
      'GET /api/routes': { body: routes },
      'GET /api/setup/status': { body: setupStatus({ completed: true, services: ALL_BUNDLED }) },
      [RECHECK_ALL]: { body: routes.map((row) => row.route) },
    })
  }

  it('一次重跑每一條，跑完說一句', async () => {
    const stub = render(routesWith(VOIDED, VOIDED, VOIDED))
    const user = userEvent.setup()
    renderApp('/settings/routes')

    await user.click(await screen.findByRole('button', { name: '全部重新檢查' }))

    expect(await screen.findByText('3 條 Route 都重新檢查過了。')).toBeVisible()
    expect(
      stub.mock.calls.filter(
        ([url, init]) => url === '/api/routes/check' && init?.method === 'POST',
      ),
    ).toHaveLength(1)
  })

  it('一條 Route 都沒有就沒有那一顆', async () => {
    render([])
    renderApp('/settings/routes')

    expect(await screen.findByText(/還沒有 Route/)).toBeVisible()
    expect(screen.queryByRole('button', { name: '全部重新檢查' })).not.toBeInTheDocument()
  })
})

describe('換了一台 qBittorrent 之後自動重查', () => {
  const EXISTING = setupStatus({
    completed: true,
    current_step: 6,
    owner: 'skipper',
    services: ALL_BUNDLED.map((row) =>
      row.kind === 'qbittorrent'
        ? chosen({
            kind: 'qbittorrent',
            origin: 'existing',
            reason: 'connected',
            base_url: 'http://nas:8080',
          })
        : row,
    ),
  })
  /** 換到 `changeAddress` 填的那一台之後：位址變了，Route 的檢查作廢。 */
  const MOVED = setupStatus({
    ...EXISTING,
    services: EXISTING.services.map((row) =>
      row.kind === 'qbittorrent' ? { ...row, base_url: 'http://other-nas:8080' } : row,
    ),
  })
  const NOT_YET = setupStatus({
    ...MOVED,
    services: MOVED.services.map((row) =>
      row.kind === 'qbittorrent' ? { ...row, state: 'timeout', reason: 'starting' } : row,
    ),
  })

  function render(extra: Record<string, StubRoute | (() => StubRoute | Promise<StubRoute>)>) {
    return stubApi({
      'GET /api/health': { body: HEALTHY },
      'GET /api/auth/me': { body: { name: 'skipper', role: 'admin' } },
      'GET /api/settings/services': { body: healthDetail() },
      'POST /api/settings/services/qbittorrent/test': { body: healthDetail() },
      'GET /api/setup/status': { body: EXISTING },
      'GET /api/setup/qbittorrent/diff': {
        body: qbittorrentSetup({ origin: 'existing', web_ui_login: false, web_ui_username: '' }),
      },
      'GET /api/settings/disk': { body: { min_free_gb: 10 } },
      'GET /api/routes': { body: routesWith(VOIDED, VOIDED) },
      ...extra,
    })
  }

  async function changeAddress(user: ReturnType<typeof userEvent.setup>) {
    const connection = within(await screen.findByRole('region', { name: '位址與憑證' }))
    await user.click(await connection.findByRole('button', { name: '改位址或憑證' }))
    await user.clear(connection.getByLabelText('位址'))
    await user.type(connection.getByLabelText('位址'), 'http://other-nas:8080')
    await user.click(connection.getByRole('button', { name: '測試連線' }))
  }

  function rechecks(stub: ReturnType<typeof render>) {
    return stub.mock.calls.filter(
      ([url, init]) => url === '/api/routes/check' && init?.method === 'POST',
    ).length
  }

  it('新那一台測過了：送一次全部重新檢查，跑著說「正在重新檢查 N 條」，跑完說幾條過了', async () => {
    let finish: (route: StubRoute) => void = () => {}
    const stub = render({
      'POST /api/setup/services/qbittorrent': { body: MOVED },
      [RECHECK_ALL]: () => new Promise<StubRoute>((resolve) => (finish = resolve)),
    })
    const user = userEvent.setup()
    renderApp('/settings/qbittorrent')

    await changeAddress(user)

    const section = within(await screen.findByRole('region', { name: 'Route 重新檢查' }))
    expect(await section.findByText(/正在重新檢查 2 條 Route/)).toBeVisible()
    expect(section.getByText(/結果出來之前送單照舊/)).toBeVisible()
    expect(rechecks(stub)).toBe(1)

    finish({ body: [routeView({ id: 1 }), routeView({ id: 2, slug: 'movies' })] })

    expect(await section.findByText('2 / 2 條 Route 通過，都接上新的這一台了。')).toBeVisible()
  })

  it('沒過的指去媒體庫路徑', async () => {
    render({
      'POST /api/setup/services/qbittorrent': { body: MOVED },
      [RECHECK_ALL]: {
        body: [routeView({ id: 1 }), routeView({ id: 2, slug: 'movies', health: 'failed' })],
      },
    })
    const user = userEvent.setup()
    renderApp('/settings/qbittorrent')

    await changeAddress(user)

    const section = within(await screen.findByRole('region', { name: 'Route 重新檢查' }))
    expect(await section.findByText(/有 1 條 Route 沒過/)).toBeVisible()
    expect(section.getByRole('link', { name: '到 Route 設定' })).toHaveAttribute(
      'href',
      '/settings/routes',
    )
  })

  it('新那一台還沒測過：不重查，等重新測試轉綠才送', async () => {
    const stub = render({
      'POST /api/setup/services/qbittorrent': { body: NOT_YET },
      'POST /api/setup/services/qbittorrent/test': { body: MOVED },
      [RECHECK_ALL]: { body: [routeView({ id: 1 }), routeView({ id: 2, slug: 'movies' })] },
    })
    const user = userEvent.setup()
    renderApp('/settings/qbittorrent')

    await changeAddress(user)
    const connection = within(screen.getByRole('region', { name: '位址與憑證' }))
    const retest = await connection.findByRole('button', { name: '重新測試' })
    expect(rechecks(stub)).toBe(0)
    expect(screen.queryByRole('region', { name: 'Route 重新檢查' })).not.toBeInTheDocument()

    await user.click(retest)

    await waitFor(() => expect(rechecks(stub)).toBe(1))
  })

  it('同一台只改帳密：不重查（不作廢 Route 的檢查，重查會白問探針）', async () => {
    const stub = render({ 'POST /api/setup/services/qbittorrent': { body: EXISTING } })
    const user = userEvent.setup()
    renderApp('/settings/qbittorrent')

    const connection = within(await screen.findByRole('region', { name: '位址與憑證' }))
    await user.click(await connection.findByRole('button', { name: '改位址或憑證' }))
    await user.type(connection.getByLabelText('密碼'), 'new-secret')
    await user.click(connection.getByRole('button', { name: '測試連線' }))

    await waitFor(() =>
      expect(
        stub.mock.calls.some(([url]) => url === '/api/settings/services/qbittorrent/test'),
      ).toBe(true),
    )
    expect(rechecks(stub)).toBe(0)
    expect(screen.queryByRole('region', { name: 'Route 重新檢查' })).not.toBeInTheDocument()
  })

  it('只是重新測試同一台：不重查', async () => {
    const stub = render({
      'GET /api/setup/status': { body: NOT_YET },
      'POST /api/setup/services/qbittorrent/test': { body: EXISTING },
    })
    const user = userEvent.setup()
    renderApp('/settings/qbittorrent')

    const connection = within(await screen.findByRole('region', { name: '位址與憑證' }))
    await user.click(await connection.findByRole('button', { name: '重新測試' }))

    await waitFor(() =>
      expect(stub.mock.calls.some(([url]) => url === '/api/setup/services/qbittorrent/test')).toBe(
        true,
      ),
    )
    expect(rechecks(stub)).toBe(0)
  })
})
