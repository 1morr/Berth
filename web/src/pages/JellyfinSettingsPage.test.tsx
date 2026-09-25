import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { HEALTHY, stubApi, type StubRoute } from '../test/fetch'
import {
  ALL_BUNDLED,
  detection,
  healthDetail,
  jellyfinSetup,
  setupStatus,
  withFailedService,
} from '../test/fixtures'
import { expectCurrentByStateOnly } from '../test/navState'
import { renderApp } from '../test/render'

afterEach(() => {
  vi.unstubAllGlobals()
})

const SERVICES = 'GET /api/settings/services'
const TEST = 'POST /api/settings/services/jellyfin/test'
const STATUS = 'GET /api/setup/status'
const SETUP = 'GET /api/setup/jellyfin'
const CONNECT = 'POST /api/setup/services/jellyfin'
const SIGN_IN = 'POST /api/setup/jellyfin/connect'
const ADDRESS = 'GET /api/settings/jellyfin'
const SAVE_ADDRESS = 'POST /api/settings/jellyfin'

/** 使用者自己的 Jellyfin：精靈第 2 步填過位址、第 3 步登入過。 */
const EXISTING = setupStatus({
  completed: true,
  current_step: 8,
  admin_created: true,
  services: [
    detection({
      origin: 'existing',
      reason: 'connected',
      base_url: 'http://192.168.1.10:8096',
      configured: true,
    }),
    ...ALL_BUNDLED.slice(1),
  ],
})

function render(routes: Record<string, StubRoute | (() => StubRoute)> = {}) {
  return stubApi({
    'GET /api/health': { body: HEALTHY },
    'GET /api/auth/me': { body: { name: 'skipper', role: 'admin' } },
    [SERVICES]: { body: healthDetail() },
    [STATUS]: { body: setupStatus({ completed: true, current_step: 8, services: ALL_BUNDLED }) },
    [SETUP]: { body: jellyfinSetup({ origin: 'existing', api_key_present: true }) },
    // 套件內的 Jellyfin、對外網址沒填：深連結開在瀏覽器的主機名上。
    [ADDRESS]: { body: { public_url: '', url: '', port: 8096 } },
    ...routes,
  })
}

describe('設定 → Jellyfin', () => {
  it('頁標題是這一頁唯一的 h1', async () => {
    render()
    renderApp('/settings/jellyfin')

    expect(await screen.findByRole('heading', { level: 1, name: 'Jellyfin 設定' })).toBeVisible()
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
  })

  it('分頁列照泊位板的順序列出五頁，當前頁是 Jellyfin（票 06i）', async () => {
    render()
    renderApp('/settings/jellyfin')

    const tabs = within(await screen.findByRole('navigation', { name: '設定' }))
    expect(
      tabs.getAllByRole('link').map((link) => [link.textContent, link.getAttribute('href')]),
    ).toEqual([
      ['Jellyfin', '/settings/jellyfin'],
      ['qBittorrent', '/settings/qbittorrent'],
      ['媒體庫路徑', '/settings/routes'],
      ['索引站', '/settings/indexers'],
      ['TMDB', '/settings/tmdb'],
    ])
    expectCurrentByStateOnly(
      tabs.getByRole('link', { name: 'Jellyfin' }),
      tabs.getByRole('link', { name: 'TMDB' }),
    )
  })

  it('只有 Jellyfin 那一張健康卡，「重新檢查」的結果立刻顯示', async () => {
    render({ [TEST]: { body: withFailedService('jellyfin', 'connection refused') } })
    renderApp('/settings/jellyfin')

    const card = within(await screen.findByRole('region', { name: 'Jellyfin' }))
    expect(screen.queryByRole('region', { name: 'qBittorrent' })).not.toBeInTheDocument()
    await userEvent.click(card.getByRole('button', { name: '重新檢查' }))

    expect(await screen.findByText('connection refused')).toBeInTheDocument()
    // 已經在它的設定頁上：紅燈的修正不再連到自己。
    expect(screen.queryByRole('link', { name: /前往設定/ })).not.toBeInTheDocument()
  })

  it('套件內的 Jellyfin 沒有位址表單：位址是 compose 決定的', async () => {
    render()
    renderApp('/settings/jellyfin')

    expect(await screen.findByText(/這一套 compose 起的/)).toBeInTheDocument()
    expect(screen.queryByLabelText('位址')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '重新登入' })).not.toBeInTheDocument()
  })

  it('既有的 Jellyfin 可以換位址：跑精靈第 2 步的同一支命令，然後重測健康', async () => {
    const stub = render({
      [STATUS]: { body: EXISTING },
      [CONNECT]: { body: EXISTING },
      [TEST]: { body: healthDetail() },
    })
    const user = userEvent.setup()
    renderApp('/settings/jellyfin')

    const address = await screen.findByLabelText('位址')
    expect(address).toHaveValue('http://192.168.1.10:8096')
    await user.clear(address)
    await user.type(address, 'http://192.168.1.20:8096')
    await user.click(screen.getByRole('button', { name: '測試連線' }))

    await waitFor(() =>
      expect(stub.mock.calls.some(([url]) => url === '/api/settings/services/jellyfin/test')).toBe(
        true,
      ),
    )
    const call = stub.mock.calls.find(([url]) => url === '/api/setup/services/jellyfin')!
    expect(JSON.parse(String(call[1]?.body))).toMatchObject({
      base_url: 'http://192.168.1.20:8096',
    })
  })

  it('既有的 Jellyfin 可以重新登入換一把 API key', async () => {
    const stub = render({
      [STATUS]: { body: EXISTING },
      [SIGN_IN]: { body: jellyfinSetup({ origin: 'existing', api_key_present: true }) },
      [TEST]: { body: healthDetail() },
    })
    const user = userEvent.setup()
    renderApp('/settings/jellyfin')

    await user.type(await screen.findByLabelText('Jellyfin 管理員帳號'), 'root')
    await user.type(screen.getByLabelText('Jellyfin 管理員密碼'), 'hunter2')
    await user.click(screen.getByRole('button', { name: '重新登入' }))

    await waitFor(() =>
      expect(stub.mock.calls.some(([url]) => url === '/api/setup/jellyfin/connect')).toBe(true),
    )
    const call = stub.mock.calls.find(([url]) => url === '/api/setup/jellyfin/connect')!
    expect(JSON.parse(String(call[1]?.body))).toEqual({ username: 'root', password: 'hunter2' })
  })

  it('對外網址空著時，說得出深連結會開在哪（票 13）', async () => {
    render()
    renderApp('/settings/jellyfin')

    expect(
      await screen.findByText('現在沒有填：深連結開在這個瀏覽器目前的主機名，port 8096。'),
    ).toBeInTheDocument()
  })

  it('存下對外網址之後，說明換成填進去的那一個', async () => {
    const stub = render({
      [SAVE_ADDRESS]: {
        body: { public_url: 'https://jf.example.com', url: 'https://jf.example.com', port: null },
      },
    })
    renderApp('/settings/jellyfin')

    await userEvent.type(await screen.findByLabelText('對外網址'), 'https://jf.example.com')
    await userEvent.click(screen.getByRole('button', { name: '儲存' }))

    expect(await screen.findByText('深連結開在 https://jf.example.com。')).toBeInTheDocument()
    const call = stub.mock.calls.find(
      ([url, init]) => url === '/api/settings/jellyfin' && init?.method === 'POST',
    )
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({ public_url: 'https://jf.example.com' })
  })

  it('不是 http 的網址，欄位自己說不行', async () => {
    render({
      [SAVE_ADDRESS]: { status: 422, body: { detail: "'jf' is not an http(s) address" } },
    })
    renderApp('/settings/jellyfin')

    await userEvent.type(await screen.findByLabelText('對外網址'), 'jf')
    await userEvent.click(screen.getByRole('button', { name: '儲存' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      '要是一個 http:// 或 https:// 開頭的網址。',
    )
  })
})
