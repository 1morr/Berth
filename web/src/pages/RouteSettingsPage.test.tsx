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

/** Anime 媒體庫唯一的一條路徑已經是 Anime 那條 Route 的：沒有空路徑可以選。 */
const ANIME_FULL = libraryOption({
  item_id: 'item-2',
  name: 'Anime',
  paths: [{ path: '/data/library/anime', route_name: 'Anime' }],
})

/** TV：3 筆下載與 12 個入庫檔案指著它，刪不得。 */
const IN_USE_TV = managedRoute({ jobs: 3, ledger_entries: 12, in_use: true })

function render(routes: Record<string, StubRoute | (() => StubRoute)> = {}, role = 'admin') {
  return stubApi({
    'GET /api/health': { body: HEALTHY },
    'GET /api/auth/me': { body: { name: 'skipper', role } },
    [ROUTES]: { body: [IN_USE_TV, SECOND_DISK] },
    ...routes,
  })
}

/** 一條 Route 那一列（原生 `<details>`），以名稱找。 */
async function row(name: string) {
  return (await screen.findByText(name, { selector: 'summary *' })).closest('details')!
}

describe('Route 設定頁', () => {
  it('頁標題是這一頁唯一的 h1（票 15 audit）', async () => {
    render()
    renderApp('/settings/routes')

    expect(await screen.findByRole('heading', { level: 1, name: '媒體庫路徑' })).toBeInTheDocument()
  })

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

  it('改名稱與啟用：送出去的就是那兩個欄位', async () => {
    const fetch = render({ 'PUT /api/routes/2': { body: routeView({ name: '電視' }) } })
    renderApp('/settings/routes')

    const tv = within(await row('TV'))
    const name = tv.getByRole('textbox', { name: '名稱' })
    await userEvent.clear(name)
    await userEvent.type(name, '電視')
    await userEvent.click(tv.getByRole('button', { name: '儲存' }))

    await waitFor(() => {
      const call = fetch.mock.calls.find(([, init]) => init?.method === 'PUT')
      expect(call).toBeDefined()
      expect(JSON.parse(String(call![1]?.body))).toEqual({ name: '電視', enabled: true })
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

  it('沒有東西指著它的 Route：二次確認之後才刪，刪完列消失並播報（票 14 驗收、票 14a）', async () => {
    let deleted = false
    const fetch = render({
      [ROUTES]: () => ({ body: deleted ? [IN_USE_TV] : [IN_USE_TV, SECOND_DISK] }),
      'DELETE /api/routes/4': () => {
        deleted = true
        return { status: 204, body: null }
      },
    })
    renderApp('/settings/routes')

    const second = within(await row('TV 2'))
    await userEvent.click(second.getByRole('button', { name: '刪除這條 Route' }))
    expect(fetch.mock.calls.some(([, init]) => init?.method === 'DELETE')).toBe(false)
    await userEvent.click(second.getByRole('button', { name: '確定刪除' }))

    // 那一列不在了，說「刪掉了」的是頁面那一層：元件跟著列一起卸載，播不出來。
    expect(await screen.findByText('已刪除「TV 2」。')).toBeInTheDocument()
    await waitFor(() =>
      expect(screen.queryByText('TV 2', { selector: 'summary *' })).not.toBeInTheDocument(),
    )
    expect(
      fetch.mock.calls.some(
        ([input, init]) => init?.method === 'DELETE' && String(input) === '/api/routes/4',
      ),
    ).toBe(true)
  })

  it('被下載或入庫檔案指著的 Route 不給刪除鍵，說出原因與出路', async () => {
    render()
    renderApp('/settings/routes')

    const tv = within(await row('TV'))
    expect(tv.queryByRole('button', { name: '刪除這條 Route' })).not.toBeInTheDocument()
    expect(tv.getByText(/刪不得/)).toHaveTextContent('3 筆下載')
    expect(tv.getByRole('button', { name: '停用這條 Route' })).toBeInTheDocument()
  })

  it('被引用而且還啟用著：一鍵停用，送的是存下來的名稱，沒存的編輯不跟著送（票 14a）', async () => {
    let disabled = false
    const fetch = render({
      [ROUTES]: () => ({
        body: [
          disabled ? { ...IN_USE_TV, route: routeView({ enabled: false }) } : IN_USE_TV,
          SECOND_DISK,
        ],
      }),
      'PUT /api/routes/2': () => {
        disabled = true
        return { body: routeView({ enabled: false }) }
      },
    })
    renderApp('/settings/routes')

    const tv = within(await row('TV'))
    // 名稱改到一半還沒存：停用是另一個動作，不該把它一起送出去。
    const name = tv.getByRole('textbox', { name: '名稱' })
    await userEvent.clear(name)
    await userEvent.type(name, '改到一半')
    await userEvent.click(tv.getByRole('button', { name: '停用這條 Route' }))

    expect(await screen.findByText('已停用「TV」：新的送單不會再選到它。')).toBeInTheDocument()
    const call = fetch.mock.calls.find(([, init]) => init?.method === 'PUT')
    expect(JSON.parse(String(call![1]?.body))).toEqual({ name: 'TV', enabled: false })
    await waitFor(() =>
      expect(tv.queryByRole('button', { name: '停用這條 Route' })).not.toBeInTheDocument(),
    )
    expect(
      within((await row('TV')).querySelector('summary')!).getByText('停用'),
    ).toBeInTheDocument()
    // 上面的勾選框跟著存下來的狀態走，不留著「啟用」讓下一次儲存又把它打開。
    expect(tv.getByRole('checkbox', { name: '啟用' })).not.toBeChecked()
  })

  it('刪除時才發現被引用（清單之後有人送了單）：說出數字與原因，列留著', async () => {
    render({
      'DELETE /api/routes/4': {
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
    renderApp('/settings/routes')

    const second = within(await row('TV 2'))
    await userEvent.click(second.getByRole('button', { name: '刪除這條 Route' }))
    await userEvent.click(second.getByRole('button', { name: '確定刪除' }))

    expect(await second.findByText(/刪不得/)).toHaveTextContent('1 筆下載、0 個入庫檔案')
  })

  it('重新檢查之後說一句「檢查跑完了」——全綠時纜繩列什麼都沒變，沒有這一句就沒有回饋（票 14a）', async () => {
    render({ 'POST /api/routes/2/check': { body: routeView() } })
    renderApp('/settings/routes')

    const tv = within(await row('TV'))
    await userEvent.click(tv.getByRole('button', { name: '重新檢查' }))

    expect(await tv.findByText('檢查跑完了。')).toBeInTheDocument()
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

  it('建立時撞上同一時間建立的另一條：說再按一次就好（票 14a）', async () => {
    render({
      [LIBRARIES]: { body: [libraryOption()] },
      'POST /api/routes': {
        status: 409,
        body: {
          detail: { reason: 'route_conflict', detail: 'UNIQUE constraint failed: routes.slug' },
        },
      },
    })
    renderApp('/settings/routes')

    await userEvent.click(await screen.findByRole('button', { name: '新增 Route' }))
    const form = within(await screen.findByRole('region', { name: '新增 Route' }))
    await userEvent.click(await form.findByRole('radio', { name: 'TV' }))
    await userEvent.click(form.getByRole('radio', { name: '/mnt/disk2/tv' }))
    await userEvent.click(form.getByRole('button', { name: '建立並檢查' }))

    expect(await form.findByText(/同一時間/)).toBeInTheDocument()
  })

  it('媒體庫的路徑都有 Route 了：給一條到 Jellyfin 媒體庫設定的連結（票 14a）', async () => {
    render({
      [LIBRARIES]: { body: [ANIME_FULL] },
      'GET /api/settings/jellyfin': {
        body: { public_url: '', url: 'http://nas.local:8096', port: null },
      },
    })
    renderApp('/settings/routes')

    await userEvent.click(await screen.findByRole('button', { name: '新增 Route' }))
    const form = within(await screen.findByRole('region', { name: '新增 Route' }))
    await userEvent.click(await form.findByRole('radio', { name: 'Anime' }))

    expect(await form.findByRole('link', { name: '到 Jellyfin 替媒體庫加路徑' })).toHaveAttribute(
      'href',
      'http://nas.local:8096/web/#/dashboard/libraries',
    )
  })

  it('不知道 Jellyfin 開在哪裡時只留文字，不給一條死連結', async () => {
    const fetch = render({
      [LIBRARIES]: { body: [ANIME_FULL] },
      'GET /api/settings/jellyfin': { body: { public_url: '', url: '', port: null } },
    })
    renderApp('/settings/routes')

    await userEvent.click(await screen.findByRole('button', { name: '新增 Route' }))
    const form = within(await screen.findByRole('region', { name: '新增 Route' }))
    await userEvent.click(await form.findByRole('radio', { name: 'Anime' }))

    expect(await form.findByText(/都已經有 Route 了/)).toBeInTheDocument()
    await waitFor(() =>
      expect(fetch.mock.calls.some(([input]) => String(input) === '/api/settings/jellyfin')).toBe(
        true,
      ),
    )
    expect(form.queryByRole('link')).not.toBeInTheDocument()
  })

  it('已經有 Route 的路徑說出是哪一條：名字由後端帶來，不拿清單反查（票 14a）', async () => {
    render({
      [ROUTES]: { body: [] },
      [LIBRARIES]: { body: [libraryOption()] },
    })
    renderApp('/settings/routes')

    await userEvent.click(await screen.findByRole('button', { name: '新增 Route' }))
    const form = within(await screen.findByRole('region', { name: '新增 Route' }))
    await userEvent.click(await form.findByRole('radio', { name: 'TV' }))

    expect(form.getByText('已是「TV」')).toBeInTheDocument()
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
