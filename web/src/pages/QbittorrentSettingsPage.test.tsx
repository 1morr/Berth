import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { HEALTHY, stubApi, type StubRoute } from '../test/fetch'
import { ALL_BUNDLED, chosen, healthDetail, qbittorrentSetup, setupStatus } from '../test/fixtures'
import { renderApp } from '../test/render'

afterEach(() => {
  vi.unstubAllGlobals()
})

const SERVICES = 'GET /api/settings/services'
/** 頁 2 的同一支讀取：設定頁的介面登入那一區照它畫（M4 票 32 起沒有設定頁專用的那一支）。 */
const QBITTORRENT = 'GET /api/setup/qbittorrent/diff'
const TEST_QBIT = 'POST /api/settings/services/qbittorrent/test'
const DISK = 'GET /api/settings/disk'
const SAVE_DISK = 'POST /api/settings/disk'
const STATUS = 'GET /api/setup/status'
const CONNECT = 'POST /api/setup/services/qbittorrent'
const LOGIN = 'PUT /api/setup/qbittorrent/login'

/** 套件內那一台，還沒設過 WebUI 登入。 */
const CLEAN = qbittorrentSetup()

/** 精靈跑完、三個都是套件內的一台；擁有者 skipper（介面登入沿用的就是他）。 */
const BUNDLED = setupStatus({
  completed: true,
  current_step: 6,
  owner: 'skipper',
  services: ALL_BUNDLED,
})

/** 使用者自己的 qBittorrent：精靈頁 2 選了既有、填過位址與帳密。 */
const EXISTING = setupStatus({
  ...BUNDLED,
  services: ALL_BUNDLED.map((row) =>
    row.kind === 'qbittorrent'
      ? chosen({
          kind: 'qbittorrent',
          origin: 'existing',
          reason: 'connected',
          detail: 'v5.1.2 · Web API 2.11.4',
          base_url: 'http://nas:8080',
        })
      : row,
  ),
})

/** 既有那一台：Berth 不管它的登入。 */
const EXISTING_QBITTORRENT = qbittorrentSetup({
  origin: 'existing',
  base_url: 'http://nas:8080',
  web_ui_login: false,
  web_ui_username: '',
})

/** 設過 WebUI 登入（帳號 skipper）的套件內那一台。 */
const WITH_LOGIN = qbittorrentSetup({ ...CLEAN, web_ui_username: 'skipper' })

/** 「儲存」寫進去了：帳號是 `username`。 */
function loginSet(username: string) {
  return qbittorrentSetup({
    ...CLEAN,
    web_ui_username: username,
    steps: [{ step: 'web_ui_password', status: 'ok', detail: username, error: '' }],
  })
}

/** 介面登入那一區。目前的帳號讀回來之前帳號那一格是空的，所以等它預填。 */
async function loginSection(username = 'skipper') {
  const section = within(
    (await screen.findByRole('heading', { name: '介面登入' })).closest('section')!,
  )
  await waitFor(() => expect(section.getByLabelText('帳號')).toHaveValue(username))
  return section
}

function render(routes: Record<string, StubRoute | (() => StubRoute)> = {}) {
  return stubApi({
    'GET /api/health': { body: HEALTHY },
    'GET /api/auth/me': { body: { name: 'skipper', role: 'admin' } },
    [SERVICES]: { body: healthDetail() },
    [STATUS]: { body: BUNDLED },
    [QBITTORRENT]: { body: CLEAN },
    [DISK]: { body: { min_free_gb: 10 } },
    'GET /api/issues': { body: [] },
    ...routes,
  })
}

describe('設定 → qBittorrent', () => {
  it('頁標題是這一頁唯一的 h1', async () => {
    render()
    renderApp('/settings/qbittorrent')

    expect(await screen.findByRole('heading', { level: 1, name: 'qBittorrent 設定' })).toBeVisible()
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
  })

  it('既有 qBittorrent 換帳密：打開表單、送同一支選擇命令帶 existing，然後重測健康（M4 票 15）', async () => {
    const stub = render({
      [STATUS]: { body: EXISTING },
      [QBITTORRENT]: { body: EXISTING_QBITTORRENT },
      [CONNECT]: { body: EXISTING },
      [TEST_QBIT]: { body: healthDetail() },
    })
    const user = userEvent.setup()
    renderApp('/settings/qbittorrent')

    const connection = within(await screen.findByRole('region', { name: '位址與憑證' }))
    expect(await connection.findByRole('radio', { name: /^既有/ })).toBeChecked()
    // 連上了的那一台不攤開表單；要改才按。
    expect(connection.queryByLabelText('位址')).not.toBeInTheDocument()
    await user.click(connection.getByRole('button', { name: '改位址或憑證' }))

    expect(connection.getByLabelText('位址')).toHaveValue('http://nas:8080')
    await user.type(connection.getByLabelText('帳號'), 'admin')
    await user.type(connection.getByLabelText('密碼'), 'new-secret')
    await user.click(connection.getByRole('button', { name: '測試連線' }))

    await waitFor(() =>
      expect(
        stub.mock.calls.some(([url]) => url === '/api/settings/services/qbittorrent/test'),
      ).toBe(true),
    )
    const call = stub.mock.calls.find(([url]) => url === '/api/setup/services/qbittorrent')!
    expect(JSON.parse(String(call[1]?.body))).toEqual({
      origin: 'existing',
      base_url: 'http://nas:8080',
      api_key: '',
      username: 'admin',
      password: 'new-secret',
    })
  })

  it('套件內的 qBittorrent 沒有連線表單，只有它自己的 WebUI 登入（M4 票 07、15）', async () => {
    render({ [QBITTORRENT]: { body: WITH_LOGIN } })
    renderApp('/settings/qbittorrent')

    const connection = within(await screen.findByRole('region', { name: '位址與憑證' }))
    expect(await connection.findByRole('radio', { name: /^套件內/ })).toBeChecked()
    expect(connection.getByText('連上了')).toBeInTheDocument()
    expect(connection.queryByLabelText('位址')).not.toBeInTheDocument()
    expect(connection.queryByRole('button', { name: '改位址或憑證' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '測試連線' })).not.toBeInTheDocument()

    const login = await loginSection()
    expect(login.getByText('目前的帳號：')).toHaveTextContent('目前的帳號： skipper')
  })

  it('改 WebUI 登入是一般的改帳密表單：沒有沿用，帳號預填、新密碼兩次、儲存（M4 票 78）', async () => {
    const stub = render({
      [QBITTORRENT]: { body: WITH_LOGIN },
      [LOGIN]: { body: loginSet('deckhand') },
      [TEST_QBIT]: { body: healthDetail() },
    })
    const user = userEvent.setup()
    renderApp('/settings/qbittorrent')

    const login = await loginSection()
    // 精靈的「沿用 Jellyfin 帳密」與它那段臨時密碼的說明都不在設定頁。
    expect(login.queryByRole('checkbox')).not.toBeInTheDocument()
    expect(login.queryByText(/臨時密碼/)).not.toBeInTheDocument()
    expect(login.getByText('改了之後舊的那一組就不能再用。')).toBeInTheDocument()
    await user.clear(login.getByLabelText('帳號'))
    await user.type(login.getByLabelText('帳號'), 'deckhand')
    await user.type(login.getByLabelText('新密碼'), 'changed')
    await user.type(login.getByLabelText('再輸入一次密碼'), 'changed')
    await user.click(login.getByRole('button', { name: '儲存' }))

    expect(await login.findByText(/之後用 deckhand 登入，舊的那一組不能再用/)).toBeInTheDocument()
    const call = stub.mock.calls.find(([url]) => url === '/api/setup/qbittorrent/login')!
    expect(call[1]?.method).toBe('PUT')
    expect(JSON.parse(String(call[1]?.body))).toEqual({
      username: 'deckhand',
      password: 'changed',
      reuse_owner: false,
    })
    // 只換登入：不連帶頁 2 的套用。
    expect(stub.mock.calls.some(([url]) => url === '/api/setup/qbittorrent/apply')).toBe(false)
    expect(login.getByLabelText('新密碼')).toHaveValue('')
    expect(login.getByLabelText('帳號')).toHaveValue('deckhand')
  })

  it('短於 qBittorrent 規則的密碼送出前就擋下；qBittorrent 不收時照它的規則說（M4 票 26）', async () => {
    const stub = render({
      [QBITTORRENT]: { body: WITH_LOGIN },
      [LOGIN]: {
        body: qbittorrentSetup({
          ...CLEAN,
          web_ui_username: 'skipper',
          steps: [
            {
              step: 'web_ui_password',
              status: 'failed',
              detail: 'skipper',
              error: 'WebUI password must be at least 6 characters long',
              failure: 'login_rejected',
            },
          ],
        }),
      },
    })
    const user = userEvent.setup()
    renderApp('/settings/qbittorrent')

    const login = await loginSection()
    await user.type(login.getByLabelText('新密碼'), 'abcd')
    await user.type(login.getByLabelText('再輸入一次密碼'), 'abcd')
    await user.click(login.getByRole('button', { name: '儲存' }))
    expect(await login.findByText('qBittorrent 的密碼至少要 6 個字元。')).toBeInTheDocument()
    expect(stub.mock.calls.some(([url]) => url === '/api/setup/qbittorrent/login')).toBe(false)

    await user.type(login.getByLabelText('新密碼'), 'ef')
    await user.type(login.getByLabelText('再輸入一次密碼'), 'ef')
    await user.click(login.getByRole('button', { name: '儲存' }))
    expect(await login.findByText(/qBittorrent 不收這組帳密/)).toBeInTheDocument()
    // 沒有設好：打過的密碼還在，可以改。
    expect(login.getByLabelText('新密碼')).toHaveValue('abcdef')
  })

  it('改登入時 qBittorrent 連不上：貼出原文，不說成請求沒走完（M4 票 07）', async () => {
    render({
      [QBITTORRENT]: { body: WITH_LOGIN },
      [LOGIN]: {
        body: qbittorrentSetup({
          web_ui_username: 'skipper',
          reachable: false,
          blocked: true,
          error: 'connection refused',
        }),
      },
      [TEST_QBIT]: { body: healthDetail() },
    })
    const user = userEvent.setup()
    renderApp('/settings/qbittorrent')

    const login = await loginSection()
    await user.type(login.getByLabelText('新密碼'), 'hunter2')
    await user.type(login.getByLabelText('再輸入一次密碼'), 'hunter2')
    await user.click(login.getByRole('button', { name: '儲存' }))

    expect(await login.findByText('connection refused')).toBeInTheDocument()
    expect(login.queryByText(/請求沒有走完/)).not.toBeInTheDocument()
  })

  it('兩次密碼不一樣就不送（M4 票 07）', async () => {
    const stub = render({ [QBITTORRENT]: { body: WITH_LOGIN } })
    const user = userEvent.setup()
    renderApp('/settings/qbittorrent')

    const login = await loginSection()
    await user.type(login.getByLabelText('新密碼'), 'changed')
    await user.type(login.getByLabelText('再輸入一次密碼'), 'chagned')
    await user.click(login.getByRole('button', { name: '儲存' }))

    expect(await login.findByText('兩次輸入的密碼不一樣。')).toBeInTheDocument()
    expect(stub.mock.calls.some(([url]) => url === '/api/setup/qbittorrent/login')).toBe(false)
  })

  it('沒有建議設定、差異表與還原鍵：Berth 不寫也不看全域偏好（M4 票 32）', async () => {
    render({ [QBITTORRENT]: { body: WITH_LOGIN } })
    renderApp('/settings/qbittorrent')

    await loginSection()
    expect(screen.queryByRole('heading', { name: /建議設定/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /還原/ })).not.toBeInTheDocument()
  })

  it('既有 qBittorrent 沒有介面登入那一區：Berth 不寫既有服務的帳密（M4 票 07）', async () => {
    const stub = render({
      [STATUS]: { body: EXISTING },
      [QBITTORRENT]: { body: EXISTING_QBITTORRENT },
    })
    renderApp('/settings/qbittorrent')

    expect(await screen.findByRole('region', { name: '位址與憑證' })).toBeInTheDocument()
    await waitFor(() =>
      expect(stub.mock.calls.some(([url]) => url === '/api/setup/qbittorrent/diff')).toBe(true),
    )
    expect(screen.queryByRole('heading', { name: '介面登入' })).not.toBeInTheDocument()
  })

  it('磁碟空間門檻在設定裡，改了就存（M2 票 09c）', async () => {
    const stub = render({ [SAVE_DISK]: { body: { min_free_gb: 50 } } })
    renderApp('/settings/qbittorrent')

    const field = await screen.findByLabelText('最少剩下（GB）')
    await waitFor(() => expect(field).toHaveValue('10'))
    await userEvent.clear(field)
    await userEvent.type(field, '50')
    await userEvent.click(screen.getByRole('button', { name: '儲存門檻' }))

    expect(await screen.findByText('已儲存，並且立刻重量了一次。')).toBeInTheDocument()
    const call = stub.mock.calls.find(
      ([url, init]) => url === '/api/settings/disk' && init?.method === 'POST',
    )
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({ min_free_gb: 50 })
  })

  it('不是 0 以上的整數，欄位自己說不行，也不送出去', async () => {
    const stub = render({})
    renderApp('/settings/qbittorrent')

    const field = await screen.findByLabelText('最少剩下（GB）')
    await waitFor(() => expect(field).toHaveValue('10'))
    await userEvent.clear(field)
    await userEvent.type(field, '-1')
    await userEvent.click(screen.getByRole('button', { name: '儲存門檻' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('要是 0 或更大的整數。')
    expect(
      stub.mock.calls.some(
        ([url, init]) => url === '/api/settings/disk' && init?.method === 'POST',
      ),
    ).toBe(false)
  })
})
