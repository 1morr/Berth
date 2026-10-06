import { screen, waitFor, within } from '@testing-library/react'
import userEvent, { type UserEvent } from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { stubApi, type StubRoute } from '../test/fetch'
import { renderInRoute } from '../test/render'
import {
  ALL_BUNDLED,
  chosen,
  indexerSetup,
  qbittorrentSetup,
  setupStatus,
  step,
} from '../test/fixtures'
import type { IndexerSetup, SetupStatus } from '../api/setup'
import type { QbittorrentSetup } from '../api/schemas'
import { SetupPage } from './SetupPage'

/**
 * 密碼只問一次（M4 票 40，brief §19 D4、審計 E-3）：頁 1 建擁有者時勾「套件內 qBittorrent 與
 * Prowlarr 也用這組」，密碼只留在精靈這一個分頁的記憶體裡，到頁 2、頁 4 自動帶入；重新整理之後才再問。
 */
afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  localStorage.clear()
  sessionStorage.clear()
})

const STATUS = 'GET /api/setup/status'
const OWNER = 'POST /api/setup/owner'
const CHOOSE_QBITTORRENT = 'POST /api/setup/services/qbittorrent'
const QBITTORRENT = 'GET /api/setup/qbittorrent/diff'
const APPLY = 'POST /api/setup/qbittorrent/apply'
const CHOOSE_PROWLARR = 'POST /api/setup/services/prowlarr'
const INDEXERS = 'GET /api/setup/indexers'
const SET_LOGIN = 'PUT /api/setup/indexers/login'

const CARRY = '套件內 qBittorrent 與 Prowlarr 的介面也用這組'
const OWNER_PASSWORD = 'skipper 的 Jellyfin 密碼'

type FetchStub = ReturnType<typeof stubApi>

function bodiesOf(stub: FetchStub, url: string): unknown[] {
  return stub.mock.calls
    .filter(([called]) => called === url)
    .map(([, init]) => JSON.parse(String(init?.body)) as unknown)
}

const bundledCard = () => screen.getByRole('radio', { name: /^套件內/ })

/** 選了套件內 Jellyfin、連上了、還沒跑過初始精靈：建立管理員。 */
const CREATING = setupStatus({ services: [chosen()] })

/**
 * 一個記得自己狀態的假後端：頁 1 建擁有者 → 頁 2 選套件內 qBittorrent → 頁 4 選套件內 Prowlarr。
 * 兩個服務一開始都還沒設介面登入；套用之後記下帳號。
 */
function journey(initial: SetupStatus = CREATING) {
  let status = initial
  let qbittorrent: QbittorrentSetup = qbittorrentSetup()
  let indexers: IndexerSetup = indexerSetup()
  const routes: Record<string, () => StubRoute | Promise<StubRoute>> = {
    [STATUS]: () => ({ body: status }),
    [OWNER]: () => {
      status = setupStatus({ current_step: 2, owner: 'skipper', services: [chosen()] })
      return { body: status }
    },
    [CHOOSE_QBITTORRENT]: () => {
      status = setupStatus({ ...status, services: ALL_BUNDLED.slice(0, 2) })
      return { body: status }
    },
    [QBITTORRENT]: () => ({ body: qbittorrent }),
    [APPLY]: () => {
      qbittorrent = qbittorrentSetup({
        steps: [step('web_ui_password', 'ok', 'skipper')],
        web_ui_username: 'skipper',
      })
      // 頁 2 做完了；頁 3 由測試直接跳過（它與密碼無關）。
      status = setupStatus({ ...status, current_step: 4 })
      return { body: qbittorrent }
    },
    [CHOOSE_PROWLARR]: () => {
      status = setupStatus({ ...status, services: ALL_BUNDLED })
      return { body: status }
    },
    [INDEXERS]: () => ({ body: indexers }),
    [SET_LOGIN]: () => {
      indexers = indexerSetup({
        steps: [step('prowlarr_login', 'ok', 'skipper')],
        web_ui_username: 'skipper',
      })
      return { body: indexers }
    },
  }
  return routes
}

async function createOwner(user: UserEvent, password = 'harbour', carry = true) {
  await user.type(await screen.findByLabelText('Jellyfin 帳號'), 'skipper')
  await user.type(screen.getByLabelText('密碼'), password)
  await user.type(screen.getByLabelText('再輸入一次密碼'), password)
  const box = screen.getByRole('checkbox', { name: CARRY })
  expect(box).toBeChecked()
  if (!carry) await user.click(box)
  await user.click(screen.getByRole('button', { name: '建立管理員並登入' }))
  await screen.findByRole('heading', { level: 2, name: '擁有者：skipper' })
}

async function toQbittorrent(user: UserEvent) {
  await user.click(screen.getByRole('button', { name: '前往下一個泊位' }))
  await screen.findByRole('heading', { level: 2, name: '先選 qBittorrent 是哪一台' })
  await user.click(bundledCard())
}

async function toProwlarr(user: UserEvent, router: ReturnType<typeof renderInRoute>['router']) {
  // 頁 3 與密碼無關：直接走到頁 4（泊位板上點 BTH 4 也是同一個網址）。
  await router.navigate({ to: '/setup', search: { step: 4 } })
  await screen.findByRole('heading', { level: 2, name: 'Prowlarr' })
  await user.click(bundledCard())
}

describe('密碼只問一次（M4 票 40）', () => {
  it('頁 1 勾著：頁 2、頁 4 不出現密碼欄，自動沿用頁 1 那一組；密碼不落進瀏覽器的 storage', async () => {
    const written = vi.spyOn(Storage.prototype, 'setItem')
    const stub = stubApi(journey())
    const user = userEvent.setup()

    const { router } = renderInRoute(<SetupPage />)
    await createOwner(user)

    await toQbittorrent(user)
    await waitFor(() =>
      expect(bodiesOf(stub, '/api/setup/qbittorrent/apply')).toEqual([
        { login: { username: '', password: 'harbour', reuse_owner: true } },
      ]),
    )
    expect(await screen.findByText('qBittorrent WebUI 的帳號：')).toBeInTheDocument()
    expect(screen.queryByLabelText(OWNER_PASSWORD)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '設定介面登入' })).not.toBeInTheDocument()

    await toProwlarr(user, router)
    await waitFor(() =>
      expect(bodiesOf(stub, '/api/setup/indexers/login')).toEqual([
        { username: '', password: 'harbour', reuse_owner: true },
      ]),
    )
    const login = within(await screen.findByTestId('prowlarr-login'))
    expect(await login.findByText('Prowlarr 介面的帳號：')).toBeInTheDocument()
    expect(login.queryByLabelText(OWNER_PASSWORD)).not.toBeInTheDocument()
    // 各自只送一次，沒有重送。
    expect(bodiesOf(stub, '/api/setup/qbittorrent/apply')).toHaveLength(1)
    expect(bodiesOf(stub, '/api/setup/indexers/login')).toHaveLength(1)

    // 密碼只在記憶體裡：兩種 storage 都沒有它，也從來沒被寫進去過。
    for (const storage of [localStorage, sessionStorage]) {
      for (let index = 0; index < storage.length; index += 1) {
        expect(storage.getItem(storage.key(index)!)).not.toContain('harbour')
      }
    }
    for (const [key, value] of written.mock.calls) {
      expect(`${key}${value}`).not.toContain('harbour')
    }
  })

  it('重新整理之後才再問：同一個精靈換一個分頁實例，頁 2 照舊是密碼欄', async () => {
    const stub = stubApi(journey())
    const user = userEvent.setup()

    const first = renderInRoute(<SetupPage />)
    await createOwner(user)
    first.unmount()

    renderInRoute(<SetupPage />, '/setup?step=2')
    await screen.findByRole('heading', { level: 2, name: '先選 qBittorrent 是哪一台' })
    await user.click(bundledCard())

    expect(await screen.findByLabelText(OWNER_PASSWORD)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '設定介面登入' })).toBeInTheDocument()
    expect(bodiesOf(stub, '/api/setup/qbittorrent/apply')).toEqual([])
  })

  it('頁 1 取消勾選：頁 2 照舊問密碼', async () => {
    const stub = stubApi(journey())
    const user = userEvent.setup()

    renderInRoute(<SetupPage />)
    await createOwner(user, 'harbour', false)
    await toQbittorrent(user)

    expect(await screen.findByLabelText(OWNER_PASSWORD)).toBeInTheDocument()
    expect(bodiesOf(stub, '/api/setup/qbittorrent/apply')).toEqual([])
  })

  it('頁 1 是登入既有的管理員：沒有這個勾選，頁 2 照舊問密碼', async () => {
    const stub = stubApi(journey(setupStatus({ ...CREATING, owner_signs_in: true })))
    const user = userEvent.setup()

    renderInRoute(<SetupPage />)
    await user.type(await screen.findByLabelText('Jellyfin 帳號'), 'skipper')
    expect(screen.queryByRole('checkbox', { name: CARRY })).not.toBeInTheDocument()
    await user.type(screen.getByLabelText('密碼'), 'harbour')
    await user.click(screen.getByRole('button', { name: '登入' }))
    await screen.findByRole('heading', { level: 2, name: '擁有者：skipper' })
    await toQbittorrent(user)

    expect(await screen.findByLabelText(OWNER_PASSWORD)).toBeInTheDocument()
    expect(bodiesOf(stub, '/api/setup/qbittorrent/apply')).toEqual([])
  })

  it('選既有 Jellyfin 建管理員時不提：勾選只給套件內那一台', async () => {
    stubApi({
      [STATUS]: {
        body: setupStatus({
          services: [chosen({ origin: 'existing', base_url: 'http://nas:8096' })],
        }),
      },
    })

    renderInRoute(<SetupPage />)
    await screen.findByLabelText('Jellyfin 帳號')
    expect(screen.queryByRole('checkbox', { name: CARRY })).not.toBeInTheDocument()
  })

  it('Jellyfin 密碼不合 qBittorrent 的規則：頁 2 不送，說明不能沿用、給自設的三格；頁 4 照樣沿用', async () => {
    const stub = stubApi(journey())
    const user = userEvent.setup()

    const { router } = renderInRoute(<SetupPage />)
    await createOwner(user, 'tiny5')
    await toQbittorrent(user)

    expect(
      await screen.findByText(
        'qBittorrent 的密碼至少要 6 個字元，頁 1 那一組 Jellyfin 密碼太短，不能沿用；請在下面另設一組。',
      ),
    ).toBeVisible()
    const legend = screen.getByText('qBittorrent WebUI 登入')
    const fields = within(legend.closest('fieldset')!)
    expect(
      fields.getByRole('checkbox', { name: '沿用 Jellyfin 帳密（skipper）' }),
    ).not.toBeChecked()
    expect(fields.getByLabelText('帳號')).toHaveValue('skipper')
    expect(fields.getByLabelText('再輸入一次密碼')).toBeInTheDocument()
    expect(bodiesOf(stub, '/api/setup/qbittorrent/apply')).toEqual([])

    // 照常自設一組：那一句跟著消失。
    await user.type(fields.getByLabelText('密碼'), 'harbour')
    await user.type(fields.getByLabelText('再輸入一次密碼'), 'harbour')
    await user.click(screen.getByRole('button', { name: '設定介面登入' }))
    await waitFor(() =>
      expect(bodiesOf(stub, '/api/setup/qbittorrent/apply')).toEqual([
        { login: { username: 'skipper', password: 'harbour', reuse_owner: false } },
      ]),
    )
    await waitFor(() => expect(screen.queryByText(/不能沿用/)).not.toBeInTheDocument())

    // Prowlarr 沒有長度規則：照樣沿用。
    await toProwlarr(user, router)
    await waitFor(() =>
      expect(bodiesOf(stub, '/api/setup/indexers/login')).toEqual([
        { username: '', password: 'tiny5', reuse_owner: true },
      ]),
    )
  })

  it('頁 4 自動送的登入還在等 Prowlarr 重啟時：加站與跳過先停用，回訪重掛載不重送', async () => {
    const routes = journey()
    const finish = routes[SET_LOGIN]!
    let release: () => void = () => undefined
    routes[SET_LOGIN] = () =>
      new Promise<StubRoute>((resolve) => {
        release = () => resolve(finish())
      })
    const stub = stubApi(routes)
    const user = userEvent.setup()

    const { router } = renderInRoute(<SetupPage />)
    await createOwner(user)
    await toQbittorrent(user)
    await screen.findByText('qBittorrent WebUI 的帳號：')
    await toProwlarr(user, router)

    expect(await screen.findByText('沿用頁 1 的 Jellyfin 帳密（skipper），設定中…')).toBeVisible()
    expect(screen.getByRole('button', { name: '之後再說' })).toBeDisabled()

    // 走開再回來：同一個請求還在飛，不再送一次。
    await router.navigate({ to: '/setup', search: { step: 2 } })
    await screen.findByText('qBittorrent WebUI 的帳號：')
    await router.navigate({ to: '/setup', search: { step: 4 } })
    await screen.findByTestId('prowlarr-login')
    expect(bodiesOf(stub, '/api/setup/indexers/login')).toHaveLength(1)

    release()
    expect(await screen.findByText('Prowlarr 介面的帳號：')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '之後再說' })).toBeEnabled()
    expect(bodiesOf(stub, '/api/setup/indexers/login')).toHaveLength(1)
  })

  it('Jellyfin 不再接受頁 1 那一組（在 Jellyfin 改過密碼）：退回密碼欄並說出來，頁 4 也不再自動送', async () => {
    const routes = journey()
    const accept = routes[APPLY]!
    let refused = false
    // 第一次（帶過來的那一組）被拒；改好之後手動送的那一次照常寫進去。
    routes[APPLY] = () => {
      if (refused) return accept()
      refused = true
      return { status: 422, body: { detail: { reason: 'owner_password', detail: '' } } }
    }
    const stub = stubApi(routes)
    const user = userEvent.setup()

    const { router } = renderInRoute(<SetupPage />)
    await createOwner(user)
    await toQbittorrent(user)

    expect(
      await screen.findByText('這不是 skipper 的 Jellyfin 密碼，所以什麼都沒寫；改好再按一次。'),
    ).toBeVisible()
    expect(screen.getByLabelText(OWNER_PASSWORD)).toHaveValue('')
    expect(bodiesOf(stub, '/api/setup/qbittorrent/apply')).toHaveLength(1)

    await user.type(screen.getByLabelText(OWNER_PASSWORD), 'changed-in-jellyfin')
    await user.click(screen.getByRole('button', { name: '設定介面登入' }))
    expect(await screen.findByText('qBittorrent WebUI 的帳號：')).toBeInTheDocument()

    await toProwlarr(user, router)
    const login = within(await screen.findByTestId('prowlarr-login'))
    expect(await login.findByLabelText(OWNER_PASSWORD)).toBeInTheDocument()
    expect(bodiesOf(stub, '/api/setup/indexers/login')).toEqual([])
  })
})
