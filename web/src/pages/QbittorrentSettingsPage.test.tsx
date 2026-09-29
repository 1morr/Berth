import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { HEALTHY, stubApi, type StubRoute } from '../test/fetch'
import {
  ALL_BUNDLED,
  chosen,
  diff,
  healthDetail,
  qbittorrentSetup,
  setupStatus,
} from '../test/fixtures'
import { renderApp } from '../test/render'

afterEach(() => {
  vi.unstubAllGlobals()
})

const SERVICES = 'GET /api/settings/services'
const DRIFT = 'GET /api/settings/qbittorrent/diff'
const APPLY = 'POST /api/settings/qbittorrent/apply'
const TEST_QBIT = 'POST /api/settings/services/qbittorrent/test'
const DISK = 'GET /api/settings/disk'
const SAVE_DISK = 'POST /api/settings/disk'
const STATUS = 'GET /api/setup/status'
const CONNECT = 'POST /api/setup/services/qbittorrent'
const LOGIN = 'PUT /api/setup/qbittorrent/login'

/** 建議值全部一致的那一台：沒有漂移，所以不該出現還原按鈕。 */
const CLEAN = qbittorrentSetup({
  diffs: [
    diff('temp_path_enabled', 'true', 'true'),
    diff('save_path', '/data/torrent/complete', '/data/torrent/complete'),
  ],
})

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

/** 既有那一台的差異表：Berth 不寫它的偏好，也不管它的登入。 */
const EXISTING_DRIFT = qbittorrentSetup({
  origin: 'existing',
  base_url: 'http://nas:8080',
  web_ui_login: false,
  web_ui_username: '',
  writes_preferences: false,
})

/** 設過 WebUI 登入（帳號 skipper）的套件內那一台。 */
const WITH_LOGIN = qbittorrentSetup({ ...CLEAN, web_ui_username: 'skipper' })

/** 「更新登入」寫進去了：帳號是 `username`。 */
function loginSet(username: string) {
  return qbittorrentSetup({
    ...CLEAN,
    web_ui_username: username,
    steps: [{ step: 'web_ui_password', status: 'ok', detail: username, error: '' }],
  })
}

const REUSE = '沿用 Jellyfin 帳密（skipper）'
const OWNER_PASSWORD = 'skipper 的 Jellyfin 密碼'

/** 介面登入那一區。擁有者讀回來之前欄位不畫，所以等勾選出現。 */
async function loginSection() {
  const section = within(
    (await screen.findByRole('heading', { name: '介面登入' })).closest('section')!,
  )
  await section.findByRole('checkbox', { name: REUSE })
  return section
}

function render(routes: Record<string, StubRoute | (() => StubRoute)> = {}) {
  return stubApi({
    'GET /api/health': { body: HEALTHY },
    'GET /api/auth/me': { body: { name: 'skipper', role: 'admin' } },
    [SERVICES]: { body: healthDetail() },
    [STATUS]: { body: BUNDLED },
    [DRIFT]: { body: CLEAN },
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
      [DRIFT]: { body: EXISTING_DRIFT },
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
    render({ [DRIFT]: { body: WITH_LOGIN } })
    renderApp('/settings/qbittorrent')

    const connection = within(await screen.findByRole('region', { name: '位址與憑證' }))
    expect(await connection.findByRole('radio', { name: /^套件內/ })).toBeChecked()
    expect(connection.getByText('連上了')).toBeInTheDocument()
    expect(connection.queryByLabelText('位址')).not.toBeInTheDocument()
    expect(connection.queryByRole('button', { name: '改位址或憑證' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '測試連線' })).not.toBeInTheDocument()

    const login = await loginSection()
    expect(login.getByText(/目前的帳號是 skipper/)).toBeInTheDocument()
  })

  it('改 WebUI 登入預設沿用 Jellyfin 帳密：只打一次擁有者的密碼（M4 票 15）', async () => {
    const stub = render({
      [DRIFT]: { body: WITH_LOGIN },
      [LOGIN]: { body: loginSet('skipper') },
      [TEST_QBIT]: { body: healthDetail() },
    })
    const user = userEvent.setup()
    renderApp('/settings/qbittorrent')

    const login = await loginSection()
    expect(login.getByRole('checkbox', { name: REUSE })).toBeChecked()
    // 沿用時只有一格：帳號就是擁有者，密碼也不必打兩次。
    expect(login.queryByLabelText('帳號')).not.toBeInTheDocument()
    expect(login.queryByLabelText('再輸入一次密碼')).not.toBeInTheDocument()
    await user.type(login.getByLabelText(OWNER_PASSWORD), 'hunter2')
    await user.click(login.getByRole('button', { name: '更新登入' }))

    expect(await login.findByText(/之後用 skipper 登入，舊的那一組不能再用/)).toBeInTheDocument()
    const call = stub.mock.calls.find(([url]) => url === '/api/setup/qbittorrent/login')!
    expect(call[1]?.method).toBe('PUT')
    expect(JSON.parse(String(call[1]?.body))).toEqual({
      username: '',
      password: 'hunter2',
      reuse_owner: true,
    })
    // 只換登入：不連帶「還原建議設定」。
    expect(stub.mock.calls.some(([url]) => url === '/api/settings/qbittorrent/apply')).toBe(false)
    expect(login.getByLabelText(OWNER_PASSWORD)).toHaveValue('')
  })

  it('不是擁有者的 Jellyfin 密碼：說出來，說什麼都沒寫（M4 票 15）', async () => {
    render({
      [DRIFT]: { body: WITH_LOGIN },
      [LOGIN]: { status: 422, body: { detail: { reason: 'owner_password', detail: '' } } },
    })
    const user = userEvent.setup()
    renderApp('/settings/qbittorrent')

    const login = await loginSection()
    await user.type(login.getByLabelText(OWNER_PASSWORD), 'wrong')
    await user.click(login.getByRole('button', { name: '更新登入' }))

    expect(
      await login.findByText('這不是 skipper 的 Jellyfin 密碼，所以什麼都沒寫；改好再按一次。'),
    ).toBeInTheDocument()
    expect(login.queryByText(/請求沒有走完/)).not.toBeInTheDocument()
    expect(login.queryByText(/舊的那一組不能再用/)).not.toBeInTheDocument()
  })

  it('取消勾選就自設一組：三格、帳號預填目前那一個，送 reuse_owner false（M4 票 07、15）', async () => {
    const stub = render({
      [DRIFT]: { body: WITH_LOGIN },
      [LOGIN]: { body: loginSet('deckhand') },
      [TEST_QBIT]: { body: healthDetail() },
    })
    const user = userEvent.setup()
    renderApp('/settings/qbittorrent')

    const login = await loginSection()
    await user.click(login.getByRole('checkbox', { name: REUSE }))
    expect(login.queryByLabelText(OWNER_PASSWORD)).not.toBeInTheDocument()
    expect(login.getByLabelText('帳號')).toHaveValue('skipper')
    await user.clear(login.getByLabelText('帳號'))
    await user.type(login.getByLabelText('帳號'), 'deckhand')
    await user.type(login.getByLabelText('密碼'), 'changed')
    await user.type(login.getByLabelText('再輸入一次密碼'), 'changed')
    await user.click(login.getByRole('button', { name: '更新登入' }))

    expect(await login.findByText(/之後用 deckhand 登入，舊的那一組不能再用/)).toBeInTheDocument()
    const call = stub.mock.calls.find(([url]) => url === '/api/setup/qbittorrent/login')!
    expect(call[1]?.method).toBe('PUT')
    expect(JSON.parse(String(call[1]?.body))).toEqual({
      username: 'deckhand',
      password: 'changed',
      reuse_owner: false,
    })
    expect(login.getByLabelText('密碼')).toHaveValue('')
  })

  it('改登入時 qBittorrent 連不上：貼出原文，不說成請求沒走完（M4 票 07）', async () => {
    render({
      [DRIFT]: { body: WITH_LOGIN },
      [LOGIN]: {
        body: qbittorrentSetup({
          web_ui_username: 'skipper',
          reachable: false,
          blocked: true,
          diffs: [],
          error: 'connection refused',
        }),
      },
      [TEST_QBIT]: { body: healthDetail() },
    })
    const user = userEvent.setup()
    renderApp('/settings/qbittorrent')

    const login = await loginSection()
    await user.type(login.getByLabelText(OWNER_PASSWORD), 'hunter2')
    await user.click(login.getByRole('button', { name: '更新登入' }))

    expect(await login.findByText('connection refused')).toBeInTheDocument()
    expect(login.queryByText(/請求沒有走完/)).not.toBeInTheDocument()
  })

  it('自設時兩次密碼不一樣就不送（M4 票 07）', async () => {
    const stub = render({ [DRIFT]: { body: WITH_LOGIN } })
    const user = userEvent.setup()
    renderApp('/settings/qbittorrent')

    const login = await loginSection()
    await user.click(login.getByRole('checkbox', { name: REUSE }))
    await user.type(login.getByLabelText('密碼'), 'changed')
    await user.type(login.getByLabelText('再輸入一次密碼'), 'chagned')
    await user.click(login.getByRole('button', { name: '更新登入' }))

    expect(await login.findByText('兩次輸入的密碼不一樣。')).toBeInTheDocument()
    expect(stub.mock.calls.some(([url]) => url === '/api/setup/qbittorrent/login')).toBe(false)
  })

  it('沒有漂移時不給還原按鈕——沒有東西要還原', async () => {
    render({})
    renderApp('/settings/qbittorrent')

    expect(await screen.findByText('五個建議鍵都還是建議值。')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '還原建議設定' })).not.toBeInTheDocument()
  })

  it('既有 qBittorrent 沒有建議設定可還原：它的全域偏好是使用者的（M4 票 05）', async () => {
    render({
      [STATUS]: { body: EXISTING },
      [DRIFT]: { body: EXISTING_DRIFT },
    })
    renderApp('/settings/qbittorrent')

    expect(await screen.findByText(/Berth 不改你這台 qBittorrent 的全域偏好/)).toBeInTheDocument()
    expect(screen.queryByText(/個鍵與建議值不同/)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '還原建議設定' })).not.toBeInTheDocument()
    // 也沒有介面登入那一區：Berth 不寫既有服務的帳密（M4 票 07）。
    expect(screen.queryByRole('heading', { name: '介面登入' })).not.toBeInTheDocument()
  })

  it('漂移時列出逐鍵差異與還原按鈕（brief §16.3）', async () => {
    render({
      [DRIFT]: {
        body: qbittorrentSetup({
          diffs: [
            diff('auto_tmm_enabled', 'false', 'true'),
            diff('save_path', '/downloads', '/data/torrent/complete'),
          ],
        }),
      },
    })
    renderApp('/settings/qbittorrent')

    expect(await screen.findByText('2 個鍵與建議值不同。')).toBeInTheDocument()
    expect(screen.getByText('auto_tmm_enabled')).toBeInTheDocument()
    expect(screen.getByText('/downloads')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '還原建議設定' })).toBeInTheDocument()
  })

  it('按下還原之後差異消失', async () => {
    const applied = qbittorrentSetup({
      diffs: [diff('auto_tmm_enabled', 'true', 'true')],
    })
    render({
      [DRIFT]: {
        body: qbittorrentSetup({ diffs: [diff('auto_tmm_enabled', 'false', 'true')] }),
      },
      [APPLY]: { body: applied },
      [TEST_QBIT]: { body: healthDetail() },
    })
    renderApp('/settings/qbittorrent')

    await userEvent.click(await screen.findByRole('button', { name: '還原建議設定' }))

    await waitFor(() =>
      expect(screen.queryByRole('button', { name: '還原建議設定' })).not.toBeInTheDocument(),
    )
  })

  it('連不上 qBittorrent 時說的是「讀不到偏好」，不是假裝沒有差異', async () => {
    render({
      [DRIFT]: { body: qbittorrentSetup({ reachable: false, diffs: [], error: 'refused' }) },
    })
    renderApp('/settings/qbittorrent')

    expect(await screen.findByText('連不上 qBittorrent，讀不到它現在的偏好。')).toBeInTheDocument()
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
