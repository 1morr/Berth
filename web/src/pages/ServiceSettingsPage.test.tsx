import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { HEALTHY, stubApi, type StubRoute } from '../test/fetch'
import { diff, healthDetail, qbittorrentSetup, withFailedService } from '../test/fixtures'
import { renderApp } from '../test/render'

afterEach(() => {
  vi.unstubAllGlobals()
})

const SERVICES = 'GET /api/settings/services'
const DRIFT = 'GET /api/settings/qbittorrent/diff'
const APPLY = 'POST /api/settings/qbittorrent/apply'
const TEST_QBIT = 'POST /api/settings/services/qbittorrent/test'
const JELLYFIN = 'GET /api/settings/jellyfin'
const SAVE_JELLYFIN = 'POST /api/settings/jellyfin'

/** 建議值全部一致的那一台：沒有漂移，所以不該出現還原按鈕。 */
const CLEAN = qbittorrentSetup({
  diffs: [
    diff('temp_path_enabled', 'true', 'true'),
    diff('save_path', '/data/torrent/complete', '/data/torrent/complete'),
  ],
})

function render(routes: Record<string, StubRoute | (() => StubRoute)>) {
  return stubApi({
    'GET /api/health': { body: HEALTHY },
    'GET /api/auth/me': { body: { name: 'skipper', role: 'admin' } },
    [SERVICES]: { body: healthDetail() },
    [DRIFT]: { body: CLEAN },
    // 套件內的 Jellyfin、對外網址沒填：深連結開在瀏覽器的主機名上。
    [JELLYFIN]: { body: { public_url: '', url: '', port: 8096 } },
    ...routes,
  })
}

describe('服務設定頁', () => {
  it('每個服務都有一顆「測試連線」，結果立刻顯示（票 10 驗收）', async () => {
    render({ [TEST_QBIT]: { body: withFailedService('qbittorrent', 'connection refused') } })
    renderApp('/settings/services')

    const card = within(await screen.findByRole('region', { name: 'qBittorrent' }))
    await userEvent.click(card.getByRole('button', { name: '測試連線' }))

    expect(await screen.findByText('connection refused')).toBeInTheDocument()
  })

  it('沒有漂移時不給還原按鈕——沒有東西要還原', async () => {
    render({})
    renderApp('/settings/services')

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
    renderApp('/settings/services')

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
    renderApp('/settings/services')

    await userEvent.click(await screen.findByRole('button', { name: '還原建議設定' }))

    await waitFor(() =>
      expect(screen.queryByRole('button', { name: '還原建議設定' })).not.toBeInTheDocument(),
    )
  })

  it('連不上 qBittorrent 時說的是「讀不到偏好」，不是假裝沒有差異', async () => {
    render({
      [DRIFT]: { body: qbittorrentSetup({ reachable: false, diffs: [], error: 'refused' }) },
    })
    renderApp('/settings/services')

    expect(await screen.findByText('連不上 qBittorrent，讀不到它現在的偏好。')).toBeInTheDocument()
  })

  it('位址與憑證不在這一頁改，而是指回精靈', async () => {
    render({})
    renderApp('/settings/services')

    const links = await screen.findAllByRole('link', { name: '改位址或憑證' })

    expect(links).toHaveLength(3)
  })

  it('非管理員被送回健康頁（前端隱藏不是安全機制，後端同時回 403）', async () => {
    render({ 'GET /api/auth/me': { body: { name: 'deckhand', role: 'user' } } })

    const { router } = renderApp('/settings/services')

    await waitFor(() => expect(router.state.location.pathname).toBe('/health'))
  })

  it('Jellyfin 對外網址空著時，說得出深連結會開在哪（票 13）', async () => {
    render({})
    renderApp('/settings/services')

    expect(
      await screen.findByText('現在沒有填：深連結開在這個瀏覽器目前的主機名，port 8096。'),
    ).toBeInTheDocument()
  })

  it('存下對外網址之後，說明換成填進去的那一個', async () => {
    const stub = render({
      [SAVE_JELLYFIN]: {
        body: { public_url: 'https://jf.example.com', url: 'https://jf.example.com', port: null },
      },
    })
    renderApp('/settings/services')

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
      [SAVE_JELLYFIN]: { status: 422, body: { detail: "'jf' is not an http(s) address" } },
    })
    renderApp('/settings/services')

    await userEvent.type(await screen.findByLabelText('對外網址'), 'jf')
    await userEvent.click(screen.getByRole('button', { name: '儲存' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      '要是一個 http:// 或 https:// 開頭的網址。',
    )
  })
})
