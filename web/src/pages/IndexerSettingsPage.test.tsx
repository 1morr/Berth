import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { IndexerSetup, SiteSearch } from '../api/setup'
import { HEALTHY, stubApi, type StubRoute } from '../test/fetch'
import {
  ALL_BUNDLED,
  DEFAULT_OPTIONS,
  added,
  healthDetail,
  indexerSetup,
  setupStatus,
  step,
} from '../test/fixtures'
import { renderApp } from '../test/render'

afterEach(() => {
  vi.unstubAllGlobals()
})

const INDEXERS = 'GET /api/setup/indexers'
const ADD = 'POST /api/setup/indexers/apply'
const CONNECT = 'POST /api/setup/indexers/connect'
const SEARCH = 'GET /api/setup/indexers/search'
const REMOVE_YTS = 'DELETE /api/setup/indexers/3'
const LOGIN = 'PUT /api/setup/indexers/login'

/** 精靈加過 dmhy、Mikan、YTS 三站的套件內 Prowlarr。 */
function withSites(ids: Record<string, number> = { dmhy: 1, mikan: 2, yts: 3 }): IndexerSetup {
  return indexerSetup({
    options: DEFAULT_OPTIONS.map((row) =>
      row.definition_name in ids ? added(row, ids[row.definition_name]) : row,
    ),
    steps: [step('dmhy', 'ok'), step('mikan', 'ok'), step('yts', 'ok')],
  })
}

function siteSearch(indexer_id: number | null, name: string, count: number): SiteSearch {
  return { indexer_id, definition_name: name.toLowerCase(), name, count, titles: [], error: '' }
}

/** 介面登入那一區。擁有者讀回來之前欄位不畫，所以等勾選出現。 */
async function loginSection() {
  const section = within(
    (await screen.findByRole('heading', { name: '介面登入' })).closest('section')!,
  )
  await section.findByRole('checkbox', { name: '沿用 Jellyfin 帳密（skipper）' })
  return section
}

function render(routes: Record<string, StubRoute | (() => StubRoute)> = {}) {
  return stubApi({
    'GET /api/health': { body: HEALTHY },
    'GET /api/auth/me': { body: { name: 'skipper', role: 'admin' } },
    'GET /api/settings/services': { body: healthDetail() },
    'GET /api/setup/status': {
      body: setupStatus({
        completed: true,
        current_step: 6,
        owner: 'skipper',
        services: ALL_BUNDLED,
      }),
    },
    [INDEXERS]: { body: withSites() },
    ...routes,
  })
}

describe('設定 → 索引站', () => {
  it('頁標題是這一頁唯一的 h1，健康卡是 Prowlarr 那一張', async () => {
    render()
    renderApp('/settings/indexers')

    expect(await screen.findByRole('heading', { level: 1, name: '索引站設定' })).toBeVisible()
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    expect(await screen.findByRole('region', { name: 'Prowlarr' })).toBeInTheDocument()
  })

  it('已經加進來的站打勾、拿掉的沒勾；沒有「之後再說」——這裡不是 onboarding', async () => {
    render()
    renderApp('/settings/indexers')

    const picks = within((await screen.findByText('要加入哪些站')).closest('fieldset')!)
    expect(picks.getByRole('checkbox', { name: /dmhy/ })).toBeChecked()
    expect(picks.getByRole('checkbox', { name: /Mikan/ })).toBeChecked()
    expect(picks.getByRole('checkbox', { name: /Nyaa\.si/ })).not.toBeChecked()
    expect(screen.queryByRole('button', { name: '之後再說' })).not.toBeInTheDocument()
  })

  it('加一個站：勾它、按加入，送的是精靈第 6 步的同一支命令（票 06i 驗收）', async () => {
    const stub = render({
      [ADD]: { body: withSites({ dmhy: 1, mikan: 2, yts: 3, nyaasi: 4 }) },
    })
    const user = userEvent.setup()
    renderApp('/settings/indexers')

    const picks = within((await screen.findByText('要加入哪些站')).closest('fieldset')!)
    await user.click(picks.getByRole('checkbox', { name: /Nyaa\.si/ }))
    await user.click(screen.getByRole('button', { name: '加入這 4 個站' }))

    await waitFor(() =>
      expect(stub.mock.calls.some(([url]) => url === '/api/setup/indexers/apply')).toBe(true),
    )
    const call = stub.mock.calls.find(([url]) => url === '/api/setup/indexers/apply')!
    expect(JSON.parse(String(call[1]?.body)).indexers.sort()).toEqual(
      ['dmhy', 'mikan', 'nyaasi', 'yts'].sort(),
    )
    // 加站不帶登入：介面登入在它自己的那一區改（M4 票 07）。
    expect(JSON.parse(String(call[1]?.body)).login).toBeNull()
    // 加進來之後它就在試搜的清單上。
    const trial = within(await screen.findByTestId('trial'))
    expect(await trial.findByText('Nyaa.si')).toBeInTheDocument()
  })

  it('試搜：逐站說出搜到幾筆', async () => {
    render({
      [`${SEARCH}?query=`]: {
        body: {
          query: '',
          error: '',
          sites: [siteSearch(1, 'dmhy', 12), siteSearch(2, 'Mikan', 3), siteSearch(3, 'YTS', 0)],
        },
      },
    })
    const user = userEvent.setup()
    renderApp('/settings/indexers')

    const trial = within((await screen.findByRole('heading', { name: '試搜' })).closest('section')!)
    await user.click(trial.getByRole('button', { name: '試搜' }))

    const rows = within(await screen.findByTestId('trial'))
    expect(await rows.findByText('12 筆')).toBeInTheDocument()
    expect(rows.getByText('0 筆')).toBeInTheDocument()
  })

  it('移除一站：就地確認之後才送出，送的是精靈的同一支命令（票 06i 驗收）', async () => {
    const stub = render({ [REMOVE_YTS]: { body: withSites({ dmhy: 1, mikan: 2 }) } })
    const user = userEvent.setup()
    renderApp('/settings/indexers')

    const trial = await screen.findByTestId('trial')
    const yts = within(within(trial).getByText('YTS').closest('li')!)
    await user.click(yts.getByRole('button', { name: '移除' }))
    await user.click(yts.getByRole('button', { name: '確定移除' }))

    await waitFor(() => {
      expect(within(screen.getByTestId('trial')).queryByText('YTS')).not.toBeInTheDocument()
    })
    const call = stub.mock.calls.find(([, init]) => init?.method === 'DELETE')!
    expect(String(call[0])).toMatch(/\/setup\/indexers\/3$/)
    // 移除之後它不再打勾：下一次按「加入」不會把它加回來。
    const picks = within(screen.getByText('要加入哪些站').closest('fieldset')!)
    expect(picks.getByRole('checkbox', { name: /YTS/ })).not.toBeChecked()
  })

  it('既有的 Torznab 換網址或 key：沒有「之後再說」，接上之後照樣試搜', async () => {
    const existing = indexerSetup({
      origin: 'existing',
      kind: 'torznab',
      base_url: 'http://jackett:9117/api',
      options: [],
      steps: [step('torznab', 'ok', 'Jackett · TV')],
      web_ui_login: false,
    })
    const stub = render({
      [INDEXERS]: { body: existing },
      [CONNECT]: { body: existing },
    })
    const user = userEvent.setup()
    renderApp('/settings/indexers')

    const address = await screen.findByLabelText('位址')
    expect(address).toHaveValue('http://jackett:9117/api')
    expect(screen.queryByRole('button', { name: '之後再說' })).not.toBeInTheDocument()
    await user.clear(address)
    await user.type(address, 'http://jackett:9117/api/v2')
    await user.type(screen.getByLabelText('API key'), 'new-key')
    await user.click(screen.getByRole('button', { name: '測試連線' }))

    await waitFor(() =>
      expect(stub.mock.calls.some(([url]) => url === '/api/setup/indexers/connect')).toBe(true),
    )
    const call = stub.mock.calls.find(([url]) => url === '/api/setup/indexers/connect')!
    expect(JSON.parse(String(call[1]?.body))).toEqual({
      kind: 'torznab',
      base_url: 'http://jackett:9117/api/v2',
      api_key: 'new-key',
    })
    expect(screen.getByRole('button', { name: '試搜' })).toBeInTheDocument()
    // 既有的索引站沒有介面登入那一區（M4 票 07）。
    expect(screen.queryByRole('heading', { name: '介面登入' })).not.toBeInTheDocument()
  })

  it('改 Prowlarr 介面登入：預設沿用 Jellyfin 帳密，只送登入那一支（M4 票 07、15）', async () => {
    const stub = render({
      [INDEXERS]: { body: { ...withSites(), web_ui_username: 'skipper' } },
      [LOGIN]: {
        body: {
          ...withSites(),
          web_ui_username: 'skipper',
          steps: [step('dmhy', 'ok'), step('prowlarr_login', 'ok', 'skipper')],
        },
      },
      'POST /api/settings/services/prowlarr/test': { body: healthDetail() },
    })
    const user = userEvent.setup()
    renderApp('/settings/indexers')

    const login = await loginSection()
    expect(login.getByRole('checkbox', { name: '沿用 Jellyfin 帳密（skipper）' })).toBeChecked()
    await user.type(login.getByLabelText('skipper 的 Jellyfin 密碼'), 'hunter2')
    await user.click(login.getByRole('button', { name: '更新登入' }))

    expect(await login.findByText(/之後用 skipper 登入，舊的那一組不能再用/)).toBeInTheDocument()
    const call = stub.mock.calls.find(([url]) => url === '/api/setup/indexers/login')!
    expect(call[1]?.method).toBe('PUT')
    expect(JSON.parse(String(call[1]?.body))).toEqual({
      username: '',
      password: 'hunter2',
      reuse_owner: true,
    })
    expect(stub.mock.calls.some(([url]) => url === '/api/setup/indexers/apply')).toBe(false)
  })

  it('Prowlarr 沒有確認到設成功：說出原文，不說舊的照舊有效（M4 票 07）', async () => {
    render({
      [LOGIN]: {
        body: {
          ...withSites(),
          steps: [
            step('dmhy', 'ok'),
            { step: 'prowlarr_login', status: 'failed', detail: '', error: 'connection refused' },
          ],
        },
      },
      'POST /api/settings/services/prowlarr/test': { body: healthDetail() },
    })
    const user = userEvent.setup()
    renderApp('/settings/indexers')

    const login = await loginSection()
    expect(login.getByText(/還沒有設過/)).toBeInTheDocument()
    await user.type(login.getByLabelText('skipper 的 Jellyfin 密碼'), 'hunter2')
    await user.click(login.getByRole('button', { name: '更新登入' }))

    expect(await login.findByText('connection refused')).toBeInTheDocument()
    expect(login.getByText(/沒有確認到新的登入生效/)).toBeInTheDocument()
  })
})
