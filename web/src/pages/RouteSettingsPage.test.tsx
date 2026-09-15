import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { HEALTHY, stubApi, type StubRoute } from '../test/fetch'
import { CHECKS_PASSED, libraryOption, managedRoute, routeView, step } from '../test/fixtures'
import { renderApp } from '../test/render'

afterEach(() => {
  vi.unstubAllGlobals()
})

const ROUTES = 'GET /api/routes'
const LIBRARIES = 'GET /api/jellyfin/libraries'

/** 第二顆碟上的 TV：建立時 Jellyfin 看不到它，所以停用著（票 14）。 */
const SECOND_DISK = managedRoute({
  route: routeView({
    id: 4,
    slug: 'tv-2',
    name: 'TV 2',
    library: 'TV',
    target_path: '/mnt/disk2/tv',
    enabled: false,
    health: 'failed',
    checks: [
      ...CHECKS_PASSED.slice(0, 3),
      step('probe_visible', 'failed', '', 'Jellyfin cannot see /mnt/disk2/tv'),
      step('hardlink', 'pending'),
    ],
  }),
})

function render(routes: Record<string, StubRoute | (() => StubRoute)> = {}, role = 'admin') {
  return stubApi({
    'GET /api/health': { body: HEALTHY },
    'GET /api/auth/me': { body: { name: 'skipper', role } },
    [ROUTES]: { body: [managedRoute({ jobs: 3, ledger_entries: 12, in_use: true }), SECOND_DISK] },
    ...routes,
  })
}

/** 一條 Route 那一列（原生 `<details>`），以名稱找。 */
async function row(name: string) {
  return (await screen.findByText(name, { selector: 'summary *' })).closest('details')!
}

describe('Route 設定頁', () => {
  it('每條 Route 一列：狀態、名稱、寫入目標，以及有多少東西用著它', async () => {
    render()
    renderApp('/settings/routes')

    // 摘要那一行就要說得完：收起來的纜繩裡也有這條路徑（實測值），那不算。
    const summary = within((await row('TV')).querySelector('summary')!)
    expect(summary.getByText('已繫上')).toBeInTheDocument()
    expect(summary.getByText('/data/library/tv')).toBeInTheDocument()
    expect(summary.getByText('3 筆下載')).toBeInTheDocument()
    expect(summary.getByText('12 個入庫檔案')).toBeInTheDocument()
  })

  it('綠燈收起；紅燈或停用的就地展開，斷掉的那條纜繩說出原文（shape brief §6）', async () => {
    render()
    renderApp('/settings/routes')

    expect(await row('TV')).not.toHaveAttribute('open')
    const second = await row('TV 2')
    expect(second).toHaveAttribute('open')
    expect(within(second).getByText('停用')).toBeInTheDocument()
    expect(within(second).getByText('Jellyfin cannot see /mnt/disk2/tv')).toBeInTheDocument()
  })

  it('改名稱、profile 與啟用：送出去的就是那三個欄位', async () => {
    const fetch = render({ 'PUT /api/routes/2': { body: routeView({ name: '電視' }) } })
    renderApp('/settings/routes')

    const tv = within(await row('TV'))
    const name = tv.getByRole('textbox', { name: '名稱' })
    await userEvent.clear(name)
    await userEvent.type(name, '電視')
    await userEvent.click(tv.getByRole('radio', { name: '動漫' }))
    await userEvent.click(tv.getByRole('button', { name: '儲存' }))

    await waitFor(() => {
      const call = fetch.mock.calls.find(([, init]) => init?.method === 'PUT')
      expect(call).toBeDefined()
      expect(JSON.parse(String(call![1]?.body))).toEqual({
        name: '電視',
        profile: 'anime',
        enabled: true,
      })
    })
  })

  it('紅的 Route 啟用不了：留在停用，並指向斷掉的那條纜繩（票 14 驗收）', async () => {
    render({
      'PUT /api/routes/4': {
        status: 409,
        body: { detail: { reason: 'route_unhealthy', detail: 'tv-2' } },
      },
    })
    renderApp('/settings/routes')

    const second = within(await row('TV 2'))
    await userEvent.click(second.getByRole('checkbox', { name: '啟用' }))
    await userEvent.click(second.getByRole('button', { name: '儲存' }))

    expect(await second.findByText(/維持停用/)).toBeInTheDocument()
  })

  it('重新檢查只重跑這一條', async () => {
    const fetch = render({ 'POST /api/routes/2/check': { body: routeView() } })
    renderApp('/settings/routes')

    await userEvent.click(within(await row('TV')).getByRole('button', { name: '重新檢查' }))

    await waitFor(() =>
      expect(
        fetch.mock.calls.some(
          ([input, init]) => init?.method === 'POST' && String(input) === '/api/routes/2/check',
        ),
      ).toBe(true),
    )
  })

  it('沒有東西指著它的 Route：二次確認之後才刪（票 14 驗收）', async () => {
    const fetch = render({ 'DELETE /api/routes/4': { status: 204, body: null } })
    renderApp('/settings/routes')

    const second = within(await row('TV 2'))
    await userEvent.click(second.getByRole('button', { name: '刪除這條 Route' }))
    expect(fetch.mock.calls.some(([, init]) => init?.method === 'DELETE')).toBe(false)
    await userEvent.click(second.getByRole('button', { name: '確定刪除' }))

    await waitFor(() =>
      expect(
        fetch.mock.calls.some(
          ([input, init]) => init?.method === 'DELETE' && String(input) === '/api/routes/4',
        ),
      ).toBe(true),
    )
  })

  it('被下載或入庫檔案指著的 Route 不給刪除鍵，說出原因與出路', async () => {
    render()
    renderApp('/settings/routes')

    const tv = within(await row('TV'))
    expect(tv.queryByRole('button', { name: '刪除這條 Route' })).not.toBeInTheDocument()
    expect(tv.getByText(/刪不得/)).toHaveTextContent('3 筆下載')
    expect(tv.getByText(/刪不得/)).toHaveTextContent('停用')
  })

  it('刪除時才發現被引用（清單之後有人送了單）：說出原因，列留著', async () => {
    render({
      'DELETE /api/routes/4': {
        status: 409,
        body: { detail: { reason: 'route_in_use', detail: 'jobs=1 · ledger_entries=0' } },
      },
    })
    renderApp('/settings/routes')

    const second = within(await row('TV 2'))
    await userEvent.click(second.getByRole('button', { name: '刪除這條 Route' }))
    await userEvent.click(second.getByRole('button', { name: '確定刪除' }))

    expect(await second.findByText(/刪不得/)).toBeInTheDocument()
  })

  it('新增 Route：按下才向 Jellyfin 問，已經有 Route 的路徑選不了，送出去的就是選的那一條', async () => {
    const fetch = render({
      [LIBRARIES]: { body: [libraryOption()] },
      'POST /api/routes': { body: routeView({ id: 5, slug: 'tv-2', name: 'TV 2' }) },
    })
    renderApp('/settings/routes')

    await row('TV')
    // 這一頁多數時候是在看狀態：還沒按之前不去問 Jellyfin（shape brief §3）。
    expect(fetch.mock.calls.some(([input]) => String(input) === '/api/jellyfin/libraries')).toBe(
      false,
    )
    await userEvent.click(screen.getByRole('button', { name: '新增 Route' }))
    const form = within(await screen.findByRole('region', { name: '新增 Route' }))

    await userEvent.click(await form.findByRole('radio', { name: 'TV' }))
    expect(form.getByRole('radio', { name: '/data/library/tv' })).toBeDisabled()
    expect(form.getByText('已是「TV」')).toBeInTheDocument()
    await userEvent.click(form.getByRole('radio', { name: '/mnt/disk2/tv' }))
    const name = form.getByRole('textbox', { name: '名稱' })
    await userEvent.clear(name)
    await userEvent.type(name, 'TV 2')
    await userEvent.click(form.getByRole('radio', { name: '動漫' }))
    await userEvent.click(form.getByRole('button', { name: '建立並檢查' }))

    await waitFor(() => {
      const call = fetch.mock.calls.find(
        ([input, init]) => init?.method === 'POST' && String(input) === '/api/routes',
      )
      expect(call).toBeDefined()
      expect(JSON.parse(String(call![1]?.body))).toEqual({
        library_id: 'item-1',
        target_path: '/mnt/disk2/tv',
        name: 'TV 2',
        profile: 'anime',
      })
    })
  })

  it('建立出來是紅的：說清楚它維持停用，下一步是修好之後重新檢查再啟用', async () => {
    render({
      [LIBRARIES]: { body: [libraryOption()] },
      'POST /api/routes': {
        body: routeView({ id: 5, slug: 'tv-2', name: 'TV 2', enabled: false, health: 'failed' }),
      },
    })
    renderApp('/settings/routes')

    await userEvent.click(await screen.findByRole('button', { name: '新增 Route' }))
    const form = within(await screen.findByRole('region', { name: '新增 Route' }))
    await userEvent.click(await form.findByRole('radio', { name: 'TV' }))
    await userEvent.click(form.getByRole('radio', { name: '/mnt/disk2/tv' }))
    await userEvent.click(form.getByRole('button', { name: '建立並檢查' }))

    expect(await screen.findByText(/已建立「TV 2」.*維持停用/)).toBeInTheDocument()
  })

  it('問不到 Jellyfin：新增區塊說出原文，清單照常', async () => {
    render({
      [LIBRARIES]: {
        status: 503,
        body: { detail: { reason: 'jellyfin_unreachable', detail: 'connection refused' } },
      },
    })
    renderApp('/settings/routes')

    await userEvent.click(await screen.findByRole('button', { name: '新增 Route' }))
    const form = within(await screen.findByRole('region', { name: '新增 Route' }))

    expect(await form.findByText('connection refused')).toBeInTheDocument()
    expect(await row('TV')).toBeInTheDocument()
  })

  it('與服務設定頁共用一條子分頁列，當前頁標出來（shape brief 的決定 1）', async () => {
    render()
    renderApp('/settings/routes')

    const tabs = within(await screen.findByRole('navigation', { name: '設定' }))
    expect(tabs.getByRole('link', { name: '媒體庫路徑' })).toHaveAttribute('aria-current', 'page')
    expect(tabs.getByRole('link', { name: '服務' })).toHaveAttribute('href', '/settings/services')
  })

  it('只有 admin 進得來：一般使用者被帶回健康頁', async () => {
    render({}, 'user')
    const { router } = renderApp('/settings/routes')

    await waitFor(() => expect(router.state.location.pathname).toBe('/health'))
  })
})
