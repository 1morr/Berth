import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { SetupStatus } from '../api/setup'
import { stubApi, type StubRoute } from '../test/fetch'
import {
  ALL_BUNDLED,
  CHECKS_PASSED,
  SEQUENCE_DONE,
  detection,
  indexerSetup,
  jellyfinSetup,
  qbittorrentSetup,
  routeSetup,
  routeView,
  setupStatus,
  step,
  tmdbSetup,
} from '../test/fixtures'
import { renderWithProviders } from '../test/render'
import { SetupPage } from './SetupPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

/** 三條 Route 全綠：套件內三個媒體庫都有 Route 了。 */
const ROUTES_DONE = routeSetup({
  libraries: routeSetup().libraries.map((row) => ({ ...row, has_route: true })),
  routes: [
    routeView({ id: 1, library: 'Movies', slug: 'movies' }),
    routeView({ id: 2, library: 'TV', slug: 'tv' }),
    routeView({ id: 3, library: 'Anime', slug: 'anime' }),
  ],
  ready: true,
})

const SITES_DONE = indexerSetup({
  options: indexerSetup().options.map((row) => ({ ...row, present: true })),
  steps: indexerSetup().options.map((row) => step(row.definition_name, 'ok')),
})

const TMDB_DONE = tmdbSetup({
  api_key_present: true,
  verified: true,
  steps: [step('configuration', 'ok', 'image.tmdb.org')],
})

/**
 * 會前進的假後端：步驟由它說了算（plan §9.3「步驟由狀態導出」），每一個動作做完就把
 * `current_step` 推到下一步——正是「做完就被換頁」那個 bug 的條件。
 */
function wizard(start: number, overrides: Record<string, StubRoute | (() => StubRoute)> = {}) {
  let current = start
  const status = (): SetupStatus =>
    setupStatus({
      current_step: current,
      admin_created: true,
      admin_username: 'skipper',
      interface_username: 'skipper',
      services: ALL_BUNDLED,
    })
  const advance =
    (to: number, body: unknown): (() => StubRoute) =>
    () => {
      current = Math.max(current, to)
      return { body }
    }
  const fetchStub = stubApi({
    'GET /api/setup/status': () => ({ body: status() }),
    'POST /api/setup/detect': () => ({ body: status() }),
    'GET /api/setup/jellyfin': () => ({
      body: jellyfinSetup({
        steps: current > 3 ? SEQUENCE_DONE : [],
        api_key_present: current > 3,
      }),
    }),
    // 按下靠泊之前先存剖面上的媒體庫清單（票 06f）。
    'PUT /api/setup/jellyfin/bundled': () => ({ body: jellyfinSetup() }),
    'POST /api/setup/jellyfin/bootstrap': advance(4, jellyfinSetup({ steps: SEQUENCE_DONE })),
    'GET /api/setup/qbittorrent/diff': () => ({ body: qbittorrentSetup() }),
    'POST /api/setup/qbittorrent/apply': advance(
      5,
      qbittorrentSetup({ diffs: [], steps: [step('save_path', 'ok')] }),
    ),
    'GET /api/setup/routes': () => ({ body: current > 5 ? ROUTES_DONE : routeSetup() }),
    'POST /api/setup/routes': advance(6, ROUTES_DONE),
    'GET /api/setup/indexers': () => ({ body: current > 6 ? SITES_DONE : indexerSetup() }),
    'POST /api/setup/indexers/apply': advance(7, SITES_DONE),
    'GET /api/setup/tmdb': () => ({ body: current > 7 ? TMDB_DONE : tmdbSetup() }),
    'POST /api/setup/tmdb/test': advance(8, TMDB_DONE),
    ...overrides,
  })
  return { fetchStub, current: () => current }
}

function heading() {
  return screen.findByRole('heading', { level: 2 })
}

function board() {
  return screen.getByRole('region', { name: '泊位板' })
}

function findBoard() {
  return screen.findByRole('region', { name: '泊位板' })
}

describe('每個泊位做完都停在結果上', () => {
  it('泊位 1：靠泊序列跑完，畫面停在序列上，按了才前往下一個泊位', async () => {
    wizard(3)
    const user = userEvent.setup()
    renderWithProviders(<SetupPage />)

    await user.click(await screen.findByRole('button', { name: '開始靠泊' }))

    expect(await screen.findByRole('button', { name: '前往下一個泊位' })).toBeVisible()
    expect(await heading()).toHaveTextContent('接手這台 Jellyfin')

    await user.click(screen.getByRole('button', { name: '前往下一個泊位' }))
    expect(await heading()).toHaveTextContent('套用建議的 qBittorrent 設定')
  })

  it('泊位 2：套用完停在逐鍵結果上', async () => {
    wizard(4)
    const user = userEvent.setup()
    renderWithProviders(<SetupPage />)

    await user.click(await screen.findByRole('button', { name: /^套用這/ }))

    expect(await screen.findByRole('button', { name: '前往下一個泊位' })).toBeVisible()
    expect(await heading()).toHaveTextContent('套用建議的 qBittorrent 設定')

    await user.click(screen.getByRole('button', { name: '前往下一個泊位' }))
    expect(await heading()).toHaveTextContent('媒體庫路徑')
  })

  it('泊位 3：套件內一走到就自動建 Route，停在五條檢查的結果上，沒有要按的鍵', async () => {
    const { fetchStub } = wizard(5)
    const user = userEvent.setup()
    renderWithProviders(<SetupPage />)

    expect(await screen.findByRole('button', { name: '前往下一個泊位' })).toBeVisible()
    expect(fetchStub.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1)
    expect(await heading()).toHaveTextContent('媒體庫路徑')
    expect(screen.getAllByText('berth-tv').length).toBeGreaterThan(0)
    expect(screen.queryByRole('button', { name: /^建立/ })).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '前往下一個泊位' }))
    expect(await heading()).toHaveTextContent('索引站')
  })

  it('泊位 3：回頭看已經建好的 Route 不重跑', async () => {
    const { fetchStub } = wizard(8)
    const user = userEvent.setup()
    renderWithProviders(<SetupPage />)

    await user.click(await within(await findBoard()).findByRole('button', { name: /BTH 3/ }))

    expect(await heading()).toHaveTextContent('媒體庫路徑')
    expect(fetchStub.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
  })

  it('泊位 3：既有 Jellyfin 仍然要勾媒體庫、自己按', async () => {
    const existing = routeSetup({
      origin: 'existing',
      libraries: routeSetup().libraries.map((row) => ({ ...row, has_berth_path: false })),
    })
    const { fetchStub } = wizard(5, { 'GET /api/setup/routes': { body: existing } })
    renderWithProviders(<SetupPage />)

    expect(await screen.findByRole('checkbox', { name: 'Movies' })).toBeVisible()
    expect(fetchStub.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
  })

  it('泊位 4：加完站停在逐站結果與試搜上，前往下一個是 TMDB', async () => {
    wizard(6)
    const user = userEvent.setup()
    renderWithProviders(<SetupPage />)

    // TMDB 不在這一頁了（票 06e 拆成兩個泊位）。
    expect(await heading()).toHaveTextContent('索引站')
    expect(screen.queryByLabelText(/TMDB API key/)).not.toBeInTheDocument()
    await user.click(await screen.findByRole('button', { name: /^加入這/ }))

    expect(await screen.findByRole('button', { name: '前往下一個泊位' })).toBeVisible()
    expect(await heading()).toHaveTextContent('索引站')
    expect(screen.getByRole('heading', { name: '試搜' })).toBeVisible()

    await user.click(screen.getByRole('button', { name: '前往下一個泊位' }))
    expect(await heading()).toHaveTextContent('TMDB')
  })

  it('泊位 5：測過 TMDB 停在結果上，前往下一個是完成頁', async () => {
    wizard(7)
    const user = userEvent.setup()
    renderWithProviders(<SetupPage />)

    await user.type(await screen.findByLabelText(/TMDB API key/), 'k'.repeat(32))
    await user.click(screen.getByRole('button', { name: '測試 TMDB' }))

    expect(await screen.findByRole('button', { name: '前往下一個泊位' })).toBeVisible()
    expect(await heading()).toHaveTextContent('TMDB')

    await user.click(screen.getByRole('button', { name: '前往下一個泊位' }))
    expect(await heading()).toHaveTextContent('完成設定')
  })
})

describe('上一個泊位', () => {
  it.each([
    [3, '接手這台 Jellyfin', '偵測服務'],
    [4, '套用建議的 qBittorrent 設定', '接手這台 Jellyfin'],
    [5, '媒體庫路徑', '套用建議的 qBittorrent 設定'],
    [6, '索引站', '媒體庫路徑'],
    [7, 'TMDB', '索引站'],
    [8, '完成設定', 'TMDB'],
  ])('第 %i 步有上一個泊位', async (at, here, previous) => {
    wizard(at, at === 5 ? { 'GET /api/setup/routes': { body: ROUTES_DONE } } : {})
    const user = userEvent.setup()
    renderWithProviders(<SetupPage />)

    expect(await heading()).toHaveTextContent(here)
    await user.click(screen.getByRole('button', { name: '上一個泊位' }))

    expect(await heading()).toHaveTextContent(previous)
  })
})

describe('回頭看永遠有出口', () => {
  /** 票 06d 的 bug：完成頁的「回媒體庫路徑」把畫面釘住，之後沒有任何按鈕解除。 */
  it('完成頁回頭之後，走得回完成頁', async () => {
    wizard(8)
    const user = userEvent.setup()
    renderWithProviders(<SetupPage />)

    expect(await heading()).toHaveTextContent('完成設定')
    expect(screen.queryByRole('button', { name: '回媒體庫路徑' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '上一個泊位' }))
    expect(await heading()).toHaveTextContent('TMDB')

    await user.click(screen.getByRole('button', { name: '前往下一個泊位' }))
    expect(await heading()).toHaveTextContent('完成設定')
  })

  it('跳回很前面時，一顆「回到目前這一步」直接回去', async () => {
    wizard(8)
    const user = userEvent.setup()
    renderWithProviders(<SetupPage />)

    await user.click(await within(await findBoard()).findByRole('button', { name: /BTH 1/ }))
    expect(await heading()).toHaveTextContent('接手這台 Jellyfin')

    await user.click(screen.getByRole('button', { name: /回到目前這一步/ }))
    expect(await heading()).toHaveTextContent('完成設定')
  })

  /** 票 06d 的 bug：「前往泊位 1」做的是解除覆寫，走完過的人按了落到最後一步。 */
  it('走完過的人重新探測，再按前往泊位 1，落在泊位 1', async () => {
    wizard(8)
    const user = userEvent.setup()
    renderWithProviders(<SetupPage />)

    await user.click(await screen.findByRole('button', { name: /3 個服務已判定/ }))
    await user.click(await screen.findByRole('button', { name: '重新探測' }))
    await user.click(await screen.findByRole('button', { name: '前往泊位 1' }))

    expect(await heading()).toHaveTextContent('接手這台 Jellyfin')
  })
})

describe('泊位板與前置列', () => {
  it('走過的與目前的是按鈕，還沒到的不是按鈕', async () => {
    wizard(5, { 'GET /api/setup/routes': { body: ROUTES_DONE } })
    renderWithProviders(<SetupPage />)
    await heading()

    const cells = within(board())
    expect(cells.getByRole('button', { name: /BTH 1.*Jellyfin/ })).toBeVisible()
    expect(cells.getByRole('button', { name: /BTH 2.*qBittorrent/ })).toBeVisible()
    expect(cells.getByRole('button', { name: /BTH 3.*媒體庫路徑/ })).toHaveAttribute(
      'aria-current',
      'step',
    )
    for (const code of ['BTH 4', 'BTH 5']) {
      expect(cells.queryByRole('button', { name: new RegExp(code) })).not.toBeInTheDocument()
      expect(cells.getByText(code)).toBeVisible()
    }
  })

  it('前置列是證據也是入口：管理員回第 1 步、判定回第 2 步；沒有每頁的「重新探測」', async () => {
    wizard(4)
    const user = userEvent.setup()
    renderWithProviders(<SetupPage />)
    await heading()

    expect(screen.queryByRole('button', { name: '重新探測' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '改帳密' })).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /管理員已建立：skipper/ }))
    expect(await heading()).toHaveTextContent('Berth 管理員')

    await user.click(screen.getByRole('button', { name: /3 個服務已判定/ }))
    expect(await heading()).toHaveTextContent('偵測服務')
  })
})

describe('回頭看的泊位說出能改什麼', () => {
  it.each([
    ['BTH 1', /重跑.*已經是這樣/, /媒體庫.*改名.*Jellyfin/],
    ['BTH 2', /套用建議設定.*已經是這樣/, /qBittorrent 自己的介面/],
    ['BTH 3', /只新增.*重驗/, /改名.*停用.*設定.*媒體庫路徑/],
    ['BTH 4', /加.*站.*試搜.*移除/, /預設清單以外.*Prowlarr/],
  ])('%s', async (code, can, elsewhere) => {
    wizard(8)
    const user = userEvent.setup()
    renderWithProviders(<SetupPage />)

    await user.click(
      await within(await findBoard()).findByRole('button', { name: new RegExp(code) }),
    )

    const note = await screen.findByRole('note', { name: '回頭看' })
    expect(note).toHaveTextContent(can)
    expect(note).toHaveTextContent(elsewhere)
  })

  it('BTH 5', async () => {
    wizard(8)
    const user = userEvent.setup()
    renderWithProviders(<SetupPage />)

    // 從完成頁回頭一步就是它：剛做完的那一頁照樣說得出能改什麼。
    expect(await heading()).toHaveTextContent('完成設定')
    await user.click(screen.getByRole('button', { name: '上一個泊位' }))

    const note = await screen.findByRole('note', { name: '回頭看' })
    expect(note).toHaveTextContent(/重貼.*key/)
    expect(note).toHaveTextContent(/themoviedb\.org/)
  })

  it('目前這一步沒有回頭看的說明', async () => {
    wizard(4)
    renderWithProviders(<SetupPage />)
    await heading()

    expect(screen.queryByRole('note', { name: '回頭看' })).not.toBeInTheDocument()
  })
})

describe('重新偵測這個服務', () => {
  it('第 2 步：逾時或未解決的那一列旁邊有，只探那一個服務', async () => {
    const timedOut = setupStatus({
      current_step: 2,
      admin_created: true,
      admin_username: 'skipper',
      services: [
        detection(),
        detection({
          kind: 'qbittorrent',
          origin: 'timeout',
          reason: 'unreachable',
          resolved: false,
        }),
        detection({ kind: 'prowlarr', reason: 'no_indexers', detail: '' }),
      ],
    })
    const fetchStub = stubApi({
      'GET /api/setup/status': { body: timedOut },
      'POST /api/setup/detect': { body: timedOut },
    })
    const user = userEvent.setup()
    renderWithProviders(<SetupPage />)

    const buttons = await screen.findAllByRole('button', { name: /重新偵測這個服務/ })
    expect(buttons).toHaveLength(1)
    await user.click(buttons[0])

    await waitFor(() => {
      const call = fetchStub.mock.calls.find(([url]) => url === '/api/setup/detect')
      expect(JSON.parse(String(call?.[1]?.body))).toEqual({ restart: false, kind: 'qbittorrent' })
    })
  })

  it('泊位連不上時，那一頁有重新偵測那個服務', async () => {
    const fetchStub = wizard(4, {
      'GET /api/setup/qbittorrent/diff': {
        body: qbittorrentSetup({ reachable: false, blocked: true, error: 'connection refused' }),
      },
    }).fetchStub
    const user = userEvent.setup()
    renderWithProviders(<SetupPage />)

    await user.click(await screen.findByRole('button', { name: /重新偵測這個服務/ }))

    await waitFor(() => {
      const call = fetchStub.mock.calls.find(([url]) => url === '/api/setup/detect')
      expect(JSON.parse(String(call?.[1]?.body))).toEqual({ restart: false, kind: 'qbittorrent' })
    })
  })
})

describe('重新偵測之後回得到原本那一頁', () => {
  /**
   * 泊位 2 上重新偵測 qBittorrent，它還在啟動：後端退回第 2 步、前端輪詢接手。輪詢不能把畫面
   * 釘在第 2 步——判定一出來，畫面要回到按下那顆鍵的那一頁。
   */
  it('服務還在啟動的那幾秒退回偵測，判定出來之後回到泊位 2', async () => {
    let starting = true
    const at = (step: number, origin: 'pending' | 'bundled') =>
      setupStatus({
        current_step: step,
        admin_created: true,
        admin_username: 'skipper',
        services: [
          detection(),
          detection({
            kind: 'qbittorrent',
            origin,
            reason: 'anonymous_ok',
            resolved: origin !== 'pending',
          }),
          detection({ kind: 'prowlarr', reason: 'no_indexers', detail: '' }),
        ],
      })
    stubApi({
      'GET /api/setup/status': () => ({ body: at(4, 'bundled') }),
      'GET /api/setup/qbittorrent/diff': {
        body: qbittorrentSetup({ reachable: false, blocked: true, error: 'connection refused' }),
      },
      'POST /api/setup/detect': () => {
        if (starting) {
          starting = false
          return { body: at(2, 'pending') }
        }
        return { body: at(4, 'bundled') }
      },
    })
    const user = userEvent.setup()
    renderWithProviders(<SetupPage />)

    await user.click(await screen.findByRole('button', { name: /重新偵測這個服務/ }))
    expect(await heading()).toHaveTextContent('偵測服務')

    expect(
      await screen.findByRole(
        'heading',
        { name: '套用建議的 qBittorrent 設定' },
        { timeout: 6000 },
      ),
    ).toBeVisible()
  }, 10000)
})

describe('套件內的自動建立只跑一次', () => {
  /** 自動建立跑過之後 Route 又一條都沒有（全刪了）：鍵要回來，不能只剩「自動建立中」。 */
  it('跑過之後一條都沒有，鍵回來', async () => {
    const { fetchStub } = wizard(5, { 'POST /api/setup/routes': { body: routeSetup() } })
    renderWithProviders(<SetupPage />)

    expect(await screen.findByRole('button', { name: '建立 3 條 Route 並檢查' })).toBeVisible()
    expect(fetchStub.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1)
  })
})

describe('第 2 步之後的每一格都有結果可看', () => {
  it('Route 的檢查結果留在畫面上', async () => {
    wizard(5, {
      'POST /api/setup/routes': {
        body: routeSetup({ routes: [routeView({ checks: CHECKS_PASSED })], ready: true }),
      },
    })
    renderWithProviders(<SetupPage />)

    expect(await screen.findByText(/inode=8162774324533690/)).toBeVisible()
  })
})
