import { screen, waitFor, within } from '@testing-library/react'
import userEvent, { type UserEvent } from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { SetupStatus } from '../api/setup'
import { stubApi, type StubRoute } from '../test/fetch'
import {
  ALL_BUNDLED,
  CHECKS_PASSED,
  RECOMMENDED,
  SEQUENCE_DONE,
  indexerSetup,
  jellyfinSetup,
  qbittorrentSetup,
  routeSetup,
  routeView,
  setupStatus,
  site,
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
  sites: RECOMMENDED.map((row, index) => site(row, index + 1)),
  steps: RECOMMENDED.map((row) => step(row.definition_name, 'ok')),
  web_ui_username: 'skipper',
})

const TMDB_DONE = tmdbSetup({
  api_key_present: true,
  verified: true,
  steps: [step('configuration', 'ok', 'image.tmdb.org')],
})

/**
 * 會前進的假後端：步驟由它說了算（plan §9.3「步驟由狀態導出」），每一個動作做完就把
 * `current_step` 推到下一步——正是「做完就被換頁」那個 bug 的條件。
 *
 * 選擇跟著頁走（M4 票 15）：Jellyfin 在頁 1 選、qBittorrent 在頁 2、Prowlarr 在頁 4，三個都是套件內、
 * 都連上了。`built` 是套件內 Jellyfin 的媒體庫清單建完了沒；預設是「已經走過頁 3 就建完了」，
 * 按「建立並檢查」也會把它建完（M4 票 08）。
 */
function wizard(
  start: number,
  overrides: Record<string, StubRoute | (() => StubRoute)> = {},
  { built = start > 3 }: { built?: boolean } = {},
) {
  let current = start
  let owner = start > 1 ? 'skipper' : ''
  let listBuilt = built
  const status = (): SetupStatus =>
    setupStatus({
      current_step: current,
      owner,
      services: ALL_BUNDLED.filter(
        (row) =>
          row.kind === 'jellyfin' ||
          (row.kind === 'qbittorrent' && current >= 2) ||
          (row.kind === 'prowlarr' && current >= 4),
      ),
    })
  const advance =
    (to: number, body: unknown): (() => StubRoute) =>
    () => {
      current = Math.max(current, to)
      return { body }
    }
  const fetchStub = stubApi({
    'GET /api/setup/status': () => ({ body: status() }),
    'POST /api/setup/owner': () => {
      owner = 'skipper'
      current = Math.max(current, 2)
      return { body: status() }
    },
    'GET /api/setup/qbittorrent/diff': () => ({ body: qbittorrentSetup() }),
    'POST /api/setup/qbittorrent/apply': advance(
      3,
      qbittorrentSetup({ diffs: [], steps: [step('save_path', 'ok')], web_ui_username: 'skipper' }),
    ),
    'GET /api/setup/jellyfin': () => ({
      body: jellyfinSetup({
        steps: listBuilt ? SEQUENCE_DONE : [],
        api_key_present: true,
        bundled: jellyfinSetup().bundled.map((row) => ({ ...row, built: listBuilt })),
      }),
    }),
    // 按下「建立並檢查」先存畫面上的媒體庫清單（票 06f）。
    'PUT /api/setup/jellyfin/bundled': () => ({ body: jellyfinSetup() }),
    // 建清單不讓精靈前進：頁 3 還要 Route 全綠（後端 `_libraries_built` + `routes_ready`）。
    'POST /api/setup/jellyfin/bootstrap': () => {
      listBuilt = true
      return {
        body: jellyfinSetup({
          steps: SEQUENCE_DONE,
          api_key_present: true,
          bundled: jellyfinSetup().bundled.map((row) => ({ ...row, built: true })),
        }),
      }
    },
    'GET /api/setup/routes': () => ({ body: current > 3 ? ROUTES_DONE : routeSetup() }),
    'POST /api/setup/routes': advance(4, ROUTES_DONE),
    'GET /api/setup/indexers': () => ({ body: current > 4 ? SITES_DONE : indexerSetup() }),
    'POST /api/setup/indexers/apply': advance(5, SITES_DONE),
    // 介面登入是自己的一顆按鈕（M4 票 20）；站已經在了，設下去這一頁就做完。
    'PUT /api/setup/indexers/login': advance(5, SITES_DONE),
    'GET /api/setup/tmdb': () => ({ body: current > 5 ? TMDB_DONE : tmdbSetup() }),
    'POST /api/setup/tmdb/test': advance(6, TMDB_DONE),
    ...overrides,
  })
  return { fetchStub, current: () => current }
}

/** 送出過的那幾個 POST（依序）。 */
function posts(fetchStub: ReturnType<typeof stubApi>): string[] {
  return fetchStub.mock.calls
    .filter(([, init]) => init?.method === 'POST')
    .map(([url]) => String(url))
}

/** 泊位上的介面登入（M4 票 07、15）：預設沿用擁有者的 Jellyfin 帳密，密碼打一次。 */
async function typeLogin(user: UserEvent) {
  await user.type(await screen.findByLabelText('skipper 的 Jellyfin 密碼'), 'harbour')
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
  it('頁 1：擁有者成立之後停在「擁有者：名字」上，按了才前往下一個泊位', async () => {
    wizard(1)
    const user = userEvent.setup()
    renderWithProviders(<SetupPage />)

    expect(await heading()).toHaveTextContent('建立 Jellyfin 管理員')
    await user.type(screen.getByLabelText('Jellyfin 帳號'), 'skipper')
    await user.type(screen.getByLabelText('密碼'), 'harbour')
    await user.type(screen.getByLabelText('再輸入一次密碼'), 'harbour')
    await user.click(screen.getByRole('button', { name: '建立管理員並登入' }))

    expect(await screen.findByRole('button', { name: '前往下一個泊位' })).toBeVisible()
    expect(await heading()).toHaveTextContent('擁有者：skipper')

    await user.click(screen.getByRole('button', { name: '前往下一個泊位' }))
    expect(await heading()).toHaveTextContent('套用建議的 qBittorrent 設定')
  })

  it('頁 2：套用完停在逐鍵結果上，前往下一個是頁 3 的媒體庫與路徑', async () => {
    wizard(2)
    const user = userEvent.setup()
    renderWithProviders(<SetupPage />)

    await typeLogin(user)
    await user.click(await screen.findByRole('button', { name: /^套用這/ }))

    expect(await screen.findByRole('button', { name: '前往下一個泊位' })).toBeVisible()
    expect(await heading()).toHaveTextContent('套用建議的 qBittorrent 設定')

    await user.click(screen.getByRole('button', { name: '前往下一個泊位' }))
    expect(await heading()).toHaveTextContent('媒體庫路徑')
  })

  // M4 票 08：進頁不動手；一顆「建立並檢查」建媒體庫、建 Route、跑檢查，做完停在結果上。
  it('頁 3：進頁不送任何東西；按「建立並檢查」之後停在五條檢查的結果上，按了才走', async () => {
    const { fetchStub } = wizard(3)
    const user = userEvent.setup()
    renderWithProviders(<SetupPage />)

    expect(await heading()).toHaveTextContent('媒體庫路徑')
    await user.click(await screen.findByRole('button', { name: '建立並檢查' }))

    expect(await screen.findByRole('button', { name: '前往下一個泊位' })).toBeVisible()
    expect(posts(fetchStub)).toEqual(['/api/setup/jellyfin/bootstrap', '/api/setup/routes'])
    expect(await heading()).toHaveTextContent('媒體庫路徑')
    expect(screen.getAllByText('berth-tv').length).toBeGreaterThan(0)

    await user.click(screen.getByRole('button', { name: '前往下一個泊位' }))
    expect(await heading()).toHaveTextContent('索引站')
  })

  it('頁 3：清單已經建完、還沒有 Route，進頁照樣不建', async () => {
    const { fetchStub } = wizard(3, {}, { built: true })
    renderWithProviders(<SetupPage />)

    expect(await screen.findByRole('button', { name: '建立並檢查' })).toBeVisible()
    await new Promise((resolve) => setTimeout(resolve, 100))
    expect(posts(fetchStub)).toEqual([])
  })

  it('頁 3：回頭看已經建好的 Route 不重跑', async () => {
    const { fetchStub } = wizard(6)
    const user = userEvent.setup()
    renderWithProviders(<SetupPage />)

    await user.click(await within(await findBoard()).findByRole('button', { name: /BTH 3/ }))

    expect(await heading()).toHaveTextContent('媒體庫路徑')
    expect(posts(fetchStub)).toEqual([])
  })

  it('頁 3：既有 Jellyfin 直接是 Route，仍然要勾媒體庫、自己按；沒有清單', async () => {
    const existing = routeSetup({
      origin: 'existing',
      libraries: routeSetup().libraries.map((row) => ({ ...row, has_berth_path: false })),
    })
    const { fetchStub } = wizard(3, {
      'GET /api/setup/routes': { body: existing },
      'GET /api/setup/jellyfin': {
        body: jellyfinSetup({ origin: 'existing', base_url: 'http://nas:8096' }),
      },
    })
    renderWithProviders(<SetupPage />)

    expect(await screen.findByRole('checkbox', { name: 'Movies' })).toBeVisible()
    expect(await heading()).toHaveTextContent('媒體庫路徑')
    expect(screen.queryByRole('button', { name: '加一個媒體庫' })).not.toBeInTheDocument()
    // 唯一的 POST 是進頁時向 Jellyfin 重讀媒體庫（M4 票 19）：它不寫任何服務。
    await waitFor(() => expect(posts(fetchStub)).toEqual(['/api/setup/routes/libraries']))
  })

  it('頁 4：加完站停在逐站結果與試搜上，前往下一個是 TMDB', async () => {
    wizard(4)
    const user = userEvent.setup()
    renderWithProviders(<SetupPage />)

    // TMDB 不在這一頁（票 06e 拆成兩個泊位）。
    expect(await heading()).toHaveTextContent('索引站')
    expect(screen.queryByLabelText(/TMDB API key/)).not.toBeInTheDocument()
    await typeLogin(user)
    await user.click(await screen.findByRole('button', { name: '設定介面登入' }))

    expect(await screen.findByRole('button', { name: '前往下一個泊位' })).toBeVisible()
    expect(await heading()).toHaveTextContent('索引站')
    expect(screen.getByRole('heading', { name: /^已加入/ })).toBeVisible()

    await user.click(screen.getByRole('button', { name: '前往下一個泊位' }))
    expect(await heading()).toHaveTextContent('TMDB')
  })

  it('頁 5：測過 TMDB 停在結果上，前往下一個是完成頁', async () => {
    wizard(5)
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
    [2, '套用建議的 qBittorrent 設定', '擁有者：skipper'],
    [3, '媒體庫路徑', '套用建議的 qBittorrent 設定'],
    [4, '索引站', '媒體庫路徑'],
    [5, 'TMDB', '索引站'],
    [6, '完成設定', 'TMDB'],
  ])('頁 %i 有上一個泊位', async (at, here, previous) => {
    wizard(at, at === 3 ? { 'GET /api/setup/routes': { body: ROUTES_DONE } } : {}, {
      built: at >= 3,
    })
    const user = userEvent.setup()
    renderWithProviders(<SetupPage />)

    expect(await heading()).toHaveTextContent(here)
    await user.click(screen.getByRole('button', { name: '上一個泊位' }))

    expect(await heading()).toHaveTextContent(previous)
  })

  it('頁 1 沒有上一個泊位，只有前往下一個', async () => {
    wizard(6)
    const user = userEvent.setup()
    renderWithProviders(<SetupPage />)

    await user.click(await within(await findBoard()).findByRole('button', { name: /BTH 1/ }))

    expect(await heading()).toHaveTextContent('擁有者：skipper')
    expect(screen.getByRole('button', { name: '前往下一個泊位' })).toBeVisible()
    expect(screen.queryByRole('button', { name: '上一個泊位' })).not.toBeInTheDocument()
  })
})

describe('回頭看永遠有出口', () => {
  /** 票 06d 的 bug：完成頁的「回媒體庫路徑」把畫面釘住，之後沒有任何按鈕解除。 */
  it('完成頁回頭之後，走得回完成頁', async () => {
    wizard(6)
    const user = userEvent.setup()
    renderWithProviders(<SetupPage />)

    expect(await heading()).toHaveTextContent('完成設定')
    expect(screen.queryByRole('button', { name: '回媒體庫路徑' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '上一個泊位' }))
    expect(await heading()).toHaveTextContent('TMDB')

    await user.click(screen.getByRole('button', { name: '前往下一個泊位' }))
    expect(await heading()).toHaveTextContent('完成設定')
  })

  it('跳回很前面時，板下的帶子說出在哪、走到哪，一顆「回到目前這一步」直接回去', async () => {
    wizard(6)
    const user = userEvent.setup()
    renderWithProviders(<SetupPage />)

    await user.click(await within(await findBoard()).findByRole('button', { name: /BTH 1/ }))
    expect(await heading()).toHaveTextContent('擁有者：skipper')
    expect(screen.getByText(/回頭看：BTH 1 Jellyfin/)).toBeVisible()
    expect(screen.getByText(/目前走到第 6 步/)).toBeVisible()

    await user.click(screen.getByRole('button', { name: '回到目前這一步' }))
    expect(await heading()).toHaveTextContent('完成設定')
    expect(screen.queryByText(/回頭看：/)).not.toBeInTheDocument()
  })

  it('停在剛做完的那一頁不出帶子：「前往下一個泊位」就是回去的路', async () => {
    wizard(6)
    const user = userEvent.setup()
    renderWithProviders(<SetupPage />)

    expect(await heading()).toHaveTextContent('完成設定')
    await user.click(screen.getByRole('button', { name: '上一個泊位' }))

    expect(await heading()).toHaveTextContent('TMDB')
    expect(screen.queryByRole('button', { name: '回到目前這一步' })).not.toBeInTheDocument()
  })
})

describe('泊位板', () => {
  it('走過的與目前的是按鈕，還沒到的不是按鈕', async () => {
    wizard(3, { 'GET /api/setup/routes': { body: ROUTES_DONE } }, { built: true })
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

  /** M4 票 15：不再偵測，板上方那一列「擁有者 · 名字」「N 個服務已判定」跟著拿掉。 */
  it('板上正好五格，沒有前置列，也沒有偵測或重新偵測的鍵', async () => {
    wizard(4)
    renderWithProviders(<SetupPage />)
    await heading()

    expect(
      within(board())
        .getAllByText(/^BTH \d$/)
        .map((cell) => cell.textContent),
    ).toEqual(['BTH 1', 'BTH 2', 'BTH 3', 'BTH 4', 'BTH 5'])
    expect(screen.queryByRole('button', { name: /擁有者 · / })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /個服務已判定/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /偵測/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /探測/ })).not.toBeInTheDocument()
  })
})

describe('回頭看的泊位說出能改什麼', () => {
  it.each([
    // 套件內與既有各說一半（M4 票 05：既有的那一台一個鍵都不寫）；來源可以改選（M4 票 15）。
    [
      'BTH 2',
      /改選套件內或既有.*套用.*已經是這樣.*你自己的.*一個鍵都不寫/,
      /qBittorrent 自己的介面/,
    ],
    ['BTH 3', /只新增.*清單.*重驗/, /改名.*停用.*設定.*媒體庫路徑/],
    ['BTH 4', /改選套件內或既有.*加.*站.*試搜.*移除/, /要帳號的站.*Prowlarr/],
  ])('%s', async (code, can, elsewhere) => {
    wizard(6)
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
    wizard(6)
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
    wizard(2)
    renderWithProviders(<SetupPage />)
    await heading()

    expect(screen.queryByRole('note', { name: '回頭看' })).not.toBeInTheDocument()
  })
})

describe('頁 2 之後的每一格都有結果可看', () => {
  it('Route 的檢查結果留在畫面上', async () => {
    wizard(
      3,
      {
        'POST /api/setup/routes': {
          body: routeSetup({ routes: [routeView({ checks: CHECKS_PASSED })], ready: true }),
        },
      },
      { built: true },
    )
    const user = userEvent.setup()
    renderWithProviders(<SetupPage />)
    await user.click(await screen.findByRole('button', { name: '建立並檢查' }))

    // 全綠的收起來了：展開那一列、再展開那一條的技術細節看得到實測值（M4 票 21）。
    await user.click(await screen.findByText('6 / 6 通過'))
    const inode = await screen.findByText(/inode=8162774324533690/)
    expect(inode).not.toBeVisible()
    await user.click(inode.closest('details')!.querySelector('summary')!)
    expect(inode).toBeVisible()
  })
})

/**
 * 票 06h 的 audit：按下動作之後那顆鍵被換掉、換步之後舊的一頁整個卸下，焦點都掉回 `body`
 * （WCAG 2.4.3）。鍵盤與螢幕閱讀器的人從頁首重新 Tab。
 */
describe('焦點不掉回 body', () => {
  it('前往下一個泊位之後，焦點在新一步的標題上', async () => {
    wizard(2)
    const user = userEvent.setup()
    renderWithProviders(<SetupPage />)

    await typeLogin(user)
    await user.click(await screen.findByRole('button', { name: /^套用這/ }))
    await user.click(await screen.findByRole('button', { name: '前往下一個泊位' }))

    const next = await heading()
    expect(next).toHaveTextContent('媒體庫路徑')
    await waitFor(() => expect(next).toHaveFocus())
  })

  it('做完這一步、按的那顆鍵換掉之後，焦點落在「前往下一個泊位」', async () => {
    wizard(2)
    const user = userEvent.setup()
    renderWithProviders(<SetupPage />)

    await typeLogin(user)
    await user.click(await screen.findByRole('button', { name: /^套用這/ }))

    const next = await screen.findByRole('button', { name: '前往下一個泊位' })
    await waitFor(() => expect(next).toHaveFocus())
  })
})
