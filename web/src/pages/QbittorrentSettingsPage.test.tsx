import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { HEALTHY, stubApi, type StubRoute } from '../test/fetch'
import {
  ALL_BUNDLED,
  detection,
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

/** 使用者自己的 qBittorrent：精靈第 2 步填過位址與帳密。 */
const EXISTING = setupStatus({
  completed: true,
  current_step: 8,
  owner: 'skipper',
  services: ALL_BUNDLED.map((row) =>
    row.kind === 'qbittorrent'
      ? detection({
          kind: 'qbittorrent',
          origin: 'existing',
          reason: 'connected',
          detail: 'v5.1.2 · Web API 2.11.4',
          base_url: 'http://nas:8080',
          configured: true,
        })
      : row,
  ),
})

function render(routes: Record<string, StubRoute | (() => StubRoute)> = {}) {
  return stubApi({
    'GET /api/health': { body: HEALTHY },
    'GET /api/auth/me': { body: { name: 'skipper', role: 'admin' } },
    [SERVICES]: { body: healthDetail() },
    [STATUS]: { body: setupStatus({ completed: true, current_step: 8, services: ALL_BUNDLED }) },
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

  it('既有 qBittorrent 換帳密：跑精靈第 2 步的同一支命令，然後重測健康（票 06i 驗收）', async () => {
    const stub = render({
      [STATUS]: { body: EXISTING },
      [CONNECT]: { body: EXISTING },
      [TEST_QBIT]: { body: healthDetail() },
    })
    const user = userEvent.setup()
    renderApp('/settings/qbittorrent')

    const line = within((await screen.findByText('連到你的 qBittorrent')).closest('li')!)
    expect(line.getByLabelText('位址')).toHaveValue('http://nas:8080')
    await user.type(line.getByLabelText('帳號'), 'admin')
    await user.type(line.getByLabelText('密碼'), 'new-secret')
    await user.click(line.getByRole('button', { name: '測試連線' }))

    await waitFor(() =>
      expect(
        stub.mock.calls.some(([url]) => url === '/api/settings/services/qbittorrent/test'),
      ).toBe(true),
    )
    const call = stub.mock.calls.find(([url]) => url === '/api/setup/services/qbittorrent')!
    expect(JSON.parse(String(call[1]?.body))).toEqual({
      base_url: 'http://nas:8080',
      api_key: '',
      username: 'admin',
      password: 'new-secret',
    })
  })

  it('套件內的 qBittorrent 沒有連線表單，只有它自己的 WebUI 登入（M4 票 07）', async () => {
    render({ [DRIFT]: { body: qbittorrentSetup({ ...CLEAN, web_ui_username: 'skipper' }) } })
    renderApp('/settings/qbittorrent')

    expect(await screen.findByText(/這一套 compose 起的/)).toBeInTheDocument()
    const login = within(
      (await screen.findByRole('heading', { name: '介面登入' })).closest('section')!,
    )
    expect(login.getByText(/目前的帳號是 skipper/)).toBeInTheDocument()
    expect(login.getByLabelText('帳號')).toHaveValue('skipper')
    expect(screen.queryByRole('button', { name: '測試連線' })).not.toBeInTheDocument()
  })

  it('改 WebUI 登入：只送登入那一支，說出舊的那一組不能再用（M4 票 07）', async () => {
    const stub = render({
      [DRIFT]: { body: qbittorrentSetup({ ...CLEAN, web_ui_username: 'skipper' }) },
      [LOGIN]: {
        body: qbittorrentSetup({
          ...CLEAN,
          web_ui_username: 'deckhand',
          steps: [{ step: 'web_ui_password', status: 'ok', detail: 'deckhand', error: '' }],
        }),
      },
      [TEST_QBIT]: { body: healthDetail() },
    })
    const user = userEvent.setup()
    renderApp('/settings/qbittorrent')

    const login = within(
      (await screen.findByRole('heading', { name: '介面登入' })).closest('section')!,
    )
    await user.clear(login.getByLabelText('帳號'))
    await user.type(login.getByLabelText('帳號'), 'deckhand')
    await user.type(login.getByLabelText('密碼'), 'changed')
    await user.type(login.getByLabelText('再輸入一次密碼'), 'changed')
    await user.click(login.getByRole('button', { name: '更新登入' }))

    expect(await login.findByText(/之後用 deckhand 登入，舊的那一組不能再用/)).toBeInTheDocument()
    const call = stub.mock.calls.find(([url]) => url === '/api/setup/qbittorrent/login')!
    expect(call[1]?.method).toBe('PUT')
    expect(JSON.parse(String(call[1]?.body))).toEqual({ username: 'deckhand', password: 'changed' })
    // 只換登入：不連帶「還原建議設定」。
    expect(stub.mock.calls.some(([url]) => url === '/api/settings/qbittorrent/apply')).toBe(false)
    expect(login.getByLabelText('密碼')).toHaveValue('')
  })

  it('改登入時 qBittorrent 連不上：貼出原文，不說成請求沒走完（M4 票 07）', async () => {
    render({
      [DRIFT]: { body: qbittorrentSetup({ ...CLEAN, web_ui_username: 'skipper' }) },
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

    const login = within(
      (await screen.findByRole('heading', { name: '介面登入' })).closest('section')!,
    )
    await user.type(login.getByLabelText('密碼'), 'changed')
    await user.type(login.getByLabelText('再輸入一次密碼'), 'changed')
    await user.click(login.getByRole('button', { name: '更新登入' }))

    expect(await login.findByText('connection refused')).toBeInTheDocument()
    expect(login.queryByText(/請求沒有走完/)).not.toBeInTheDocument()
  })

  it('兩次密碼不一樣就不送（M4 票 07）', async () => {
    const stub = render({
      [DRIFT]: { body: qbittorrentSetup({ ...CLEAN, web_ui_username: 'skipper' }) },
    })
    const user = userEvent.setup()
    renderApp('/settings/qbittorrent')

    const login = within(
      (await screen.findByRole('heading', { name: '介面登入' })).closest('section')!,
    )
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
      [DRIFT]: {
        body: qbittorrentSetup({
          origin: 'existing',
          base_url: 'http://nas:8080',
          web_ui_login: false,
          web_ui_username: '',
          writes_preferences: false,
        }),
      },
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
