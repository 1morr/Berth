import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { IndexerSetup, SiteSearch } from '../api/setup'
import { HEALTHY, stubApi, type StubRoute } from '../test/fetch'
import {
  ALL_BUNDLED,
  RECOMMENDED,
  check,
  healthDetail,
  indexerSetup,
  setupStatus,
  site,
  step,
} from '../test/fixtures'
import { renderApp } from '../test/render'

afterEach(() => {
  vi.unstubAllGlobals()
})

const INDEXERS = 'GET /api/setup/indexers'
const ADD = 'POST /api/setup/indexers/apply'
const TEST = 'POST /api/setup/indexers/test'
const CONNECT = 'POST /api/setup/indexers/connect'
const SEARCH = 'GET /api/setup/indexers/search'
const REMOVE_YTS = 'DELETE /api/setup/indexers/3'
const LOGIN = 'PUT /api/setup/indexers/login'

/** 精靈加過 dmhy、Mikan、YTS 三站的套件內 Prowlarr。 */
function withSites(ids: Record<string, number> = { dmhy: 1, mikan: 2, yts: 3 }): IndexerSetup {
  return indexerSetup({
    sites: RECOMMENDED.filter((row) => row.definition_name in ids).map((row) =>
      site(row, ids[row.definition_name]),
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

  it('進來只讀：不測任何一站、不送任何寫入；已加入的站在上面，沒有「之後再說」', async () => {
    const stub = render()
    renderApp('/settings/indexers')

    const added = within(await screen.findByTestId('added'))
    expect(added.getByText('dmhy')).toBeInTheDocument()
    expect(added.getByText('3 站')).toBeInTheDocument()
    // 加進來的站不在加站清單上；還沒加的一站都沒勾，也勾不起來。
    expect(screen.queryByRole('checkbox', { name: 'dmhy' })).not.toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'Nyaa.si' })).toBeDisabled()
    expect(screen.queryByRole('button', { name: '之後再說' })).not.toBeInTheDocument()
    expect(stub.mock.calls.every(([, init]) => (init?.method ?? 'GET') === 'GET')).toBe(true)
  })

  it('加一個站：測過、勾它、按加入，送的是精靈頁 4 的同一支命令（票 06i 驗收）', async () => {
    const stub = render({
      [TEST]: { body: { checks: [check('nyaasi')] } },
      [ADD]: { body: withSites({ dmhy: 1, mikan: 2, yts: 3, nyaasi: 4 }) },
    })
    const user = userEvent.setup()
    renderApp('/settings/indexers')

    await user.click(await screen.findByRole('button', { name: '測試 Nyaa.si' }))
    const nyaa = screen.getByRole('checkbox', { name: 'Nyaa.si' })
    await waitFor(() => expect(nyaa).toBeEnabled())
    await user.click(nyaa)
    await user.click(screen.getByRole('button', { name: '加入 1 個站' }))

    await waitFor(() =>
      expect(stub.mock.calls.some(([url]) => url === '/api/setup/indexers/apply')).toBe(true),
    )
    const call = stub.mock.calls.find(([url]) => url === '/api/setup/indexers/apply')!
    // 只送還沒加的那一站：已經在的不重加（M4 票 09）。加站不帶登入：介面登入在它自己的那一區改
    // （M4 票 07、20）。
    expect(JSON.parse(String(call[1]?.body))).toEqual({ indexers: ['nyaasi'] })
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

    const added = within(await screen.findByTestId('added'))
    await user.click(added.getByRole('button', { name: '搜尋全部' }))

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
    // 移除之後它回到加站清單，沒勾：要用得再測一次、再加。
    expect(screen.getByRole('checkbox', { name: 'YTS' })).not.toBeChecked()
  })

  it('既有的 Torznab 換網址或 key：沒有「之後再說」，接上之後照樣試搜', async () => {
    const existing = indexerSetup({
      origin: 'existing',
      kind: 'torznab',
      base_url: 'http://jackett:9117/api',
      candidates: [],
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
    expect(screen.getByRole('button', { name: '搜尋全部' })).toBeInTheDocument()
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

describe('既有 Prowlarr 測不過時的補法（M4 票 17）', () => {
  function failed(overrides: Partial<IndexerSetup>): IndexerSetup {
    return indexerSetup({
      origin: 'existing',
      candidates: [],
      web_ui_login: false,
      reason: 'unreachable',
      steps: [step('prowlarr', 'failed', '', 'GET /api/v1/system/status: connection refused')],
      ...overrides,
    })
  }

  it.each([
    [
      '比下限舊：叫人升級，不叫人改位址',
      {
        base_url: 'http://localhost:9696',
        reason: 'version_unsupported',
        steps: [
          step(
            'prowlarr',
            'failed',
            '1.2.2.2699',
            'Prowlarr 1.2.2.2699 is older than 1.3.2, the oldest version Berth supports',
          ),
        ],
      },
      '至少要 Prowlarr 1.3.2，這一台是 1.2.2.2699',
    ],
    [
      '測過的是 localhost：說 Berth 在容器裡',
      { base_url: 'http://127.0.0.1:9696' },
      'Berth 在容器裡，這個位址指的是 Berth 自己',
    ],
    [
      'key 不對：說去哪裡複製，不說連不上（M4 票 20）',
      {
        base_url: 'http://192.168.1.10:9696',
        reason: 'auth_required',
        steps: [step('prowlarr', 'failed', '', 'GET /api/v1/system/status: 401')],
      },
      'API key 不對：在 Prowlarr 的「設定 → 一般」複製',
    ],
    [
      'https 打到講 http 的 port：說改成 http://，不叫人查 port（M4 票 25）',
      {
        base_url: 'https://192.168.1.10:9696',
        reason: 'scheme_mismatch',
        steps: [step('prowlarr', 'failed', '', 'GET /api/v1/system/status: WRONG_VERSION_NUMBER')],
      },
      '這個 port 講的是 http，不是 https',
    ],
    [
      '其他：一般的那一句',
      { base_url: 'http://192.168.1.10:9696' },
      '確認位址、port 與 API key 都對',
    ],
  ] as const)('%s', async (_, overrides, fix) => {
    render({ [INDEXERS]: { body: failed(overrides as Partial<IndexerSetup>) } })
    renderApp('/settings/indexers')

    const line = (await screen.findByTestId('sites')).querySelector('li')!
    expect(line).toHaveTextContent(fix)
  })
})
