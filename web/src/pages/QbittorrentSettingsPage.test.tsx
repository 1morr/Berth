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
  admin_created: true,
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

  it('套件內的 qBittorrent 沒有帳密表單：帳密是 Berth 寫進去的', async () => {
    render()
    renderApp('/settings/qbittorrent')

    expect(await screen.findByText(/這一套 compose 起的/)).toBeInTheDocument()
    expect(screen.queryByLabelText('密碼')).not.toBeInTheDocument()
  })

  it('沒有漂移時不給還原按鈕——沒有東西要還原', async () => {
    render({})
    renderApp('/settings/qbittorrent')

    expect(await screen.findByText('五個建議鍵都還是建議值。')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '還原建議設定' })).not.toBeInTheDocument()
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
