import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { HEALTHY, stubApi, type StubRoute } from '../test/fetch'
import { healthDetail, pollerView, routeView, step, withFailedService } from '../test/fixtures'
import { renderApp } from '../test/render'

afterEach(() => {
  vi.unstubAllGlobals()
})

const DETAIL = 'GET /api/health/detail'
const CHECK = 'POST /api/health/check'

/** 走真正的 route tree：這一頁掛在 `/health`，而修正步驟裡有一個站內連結。 */
function render(detail: StubRoute, extra: Record<string, StubRoute | (() => StubRoute)> = {}) {
  return stubApi({
    'GET /api/health': { body: HEALTHY },
    'GET /api/auth/me': { body: { name: 'skipper', role: 'admin' } },
    [DETAIL]: detail,
    ...extra,
  })
}

/** 一個服務的區塊。板上那一格也會顯示同一個實測值，所以斷言要說清楚問的是哪裡。 */
function card(name: string) {
  return within(screen.getByRole('region', { name }))
}

describe('健康頁', () => {
  /** 票 03 第 13 條：這一頁本來從 `<h2>` 開起，整頁沒有 h1。 */
  it('頁標題是這一頁唯一的 h1', async () => {
    render({ body: healthDetail() })
    renderApp('/health')

    expect(await screen.findByRole('heading', { level: 1, name: '健康' })).toBeVisible()
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
  })

  /**
   * 票 03 第 16 條。全綠時同一顆綠章在一千像素裡出現八次（板四格 + 三張服務卡 + Route 總結，
   * 每條 Route 再一顆）。板子負責回答「有沒有紅的」，底下不再把同一句話重說一遍。
   */
  it('全綠時只有泊位板塗綠，底下的卡片與列是中性色塊（字照樣在）', async () => {
    render({ body: healthDetail() })
    renderApp('/health')

    const board = await screen.findByRole('region', { name: '泊位板' })
    // 收起來的 `<details>` 裡還有五條纜繩，但全綠時它們沒有畫在畫面上——
    // 重複八次說的是**看得到的**那幾顆。
    const painted = [...document.querySelectorAll<HTMLElement>('.bg-secured')].filter(
      (chip) => chip.closest('details:not([open])') === null,
    )
    expect(painted).toHaveLength(5)
    for (const chip of painted) expect(board).toContainElement(chip)

    // 底下的服務卡照樣說得出「已繫上」，只是不再塗一次漆。
    const chip = card('Jellyfin').getByText('已繫上')
    expect(chip).toBeVisible()
    expect(chip.className).not.toMatch(/bg-secured/)
  })

  /** 票 06e：板是五格，TMDB 那一格讀精靈第 7 步那一次憑證測試的結果，不是第五項檢查。 */
  it('TMDB 有自己的一格：憑證沒驗過就是紅的', async () => {
    render({ body: healthDetail({ tmdb_verified: false }) })
    renderApp('/health')

    const board = await screen.findByRole('region', { name: '泊位板' })
    const tmdb = within(within(board).getByText('BTH 5').closest('li')!)
    expect(tmdb.getByText('TMDB')).toBeVisible()
    expect(tmdb.getByText('待驗證')).toBeVisible()
    expect(within(board).getByText('BTH 5').closest('li')!.className).toMatch(/bg-blocked/)
  })

  /** 票 03 第 15 條：`truncate` 會截掉路徑尾巴，而三條 Route 常常只差最後一段。 */
  it('Route 列不截斷寫入目標——窄版上尾巴正是分辨它們的依據', async () => {
    render({
      body: healthDetail({
        routes: [
          routeView({ id: 1, slug: 'tv', name: 'TV', target_path: '/mnt/disk1/tv' }),
          routeView({ id: 2, slug: 'tv-2', name: 'TV 2', target_path: '/mnt/disk2/tv' }),
        ],
      }),
    })
    renderApp('/health')

    const path = await screen.findByText('/mnt/disk2/tv')
    expect(path.className).not.toMatch(/truncate/)
    expect(screen.getByText('/mnt/disk1/tv')).toBeVisible()
  })

  it('四項全綠時泊位板四格都是已繫上（票 10 驗收）', async () => {
    render({ body: healthDetail() })
    renderApp('/health')

    const board = await screen.findByRole('region', { name: '泊位板' })

    expect(within(board).getAllByText('已繫上')).toHaveLength(4)
  })

  it('每一項顯示它量到的東西', async () => {
    render({ body: healthDetail() })
    renderApp('/health')

    await screen.findByRole('region', { name: 'Jellyfin' })

    expect(card('Jellyfin').getByText('12.1.0 · 3 libraries')).toBeInTheDocument()
    expect(card('qBittorrent').getByText('v5.2.3 · Web API 2.15.1')).toBeInTheDocument()
  })

  it('紅的那一項就地展開原文與修正步驟，其餘三項不動', async () => {
    render({ body: withFailedService('prowlarr', 'GET /ping: connection refused') })
    renderApp('/health')

    expect(await screen.findByText('GET /ping: connection refused')).toBeInTheDocument()
    expect(screen.getByText('docker compose up -d prowlarr')).toBeInTheDocument()
    // 另外兩個服務加上 Route 那一項仍然綠著。
    const board = screen.getByRole('region', { name: '泊位板' })
    expect(within(board).getAllByText('已繫上')).toHaveLength(3)
  })

  it('既有服務的修正是到那個服務的設定頁改連線，不是 docker 指令（票 06i）', async () => {
    render({
      body: withFailedService('jellyfin', 'GET /System/Info/Public: connection refused', {
        origin: 'existing',
      }),
    })
    renderApp('/health')

    expect(await screen.findByRole('link', { name: '前往設定：Jellyfin' })).toHaveAttribute(
      'href',
      '/settings/jellyfin',
    )
    expect(screen.queryByText('docker compose up -d jellyfin')).not.toBeInTheDocument()
  })

  it('一般使用者看到的是「請管理員來看」，不是一條進不去的設定連結', async () => {
    render(
      {
        body: withFailedService('jellyfin', 'GET /System/Info/Public: connection refused', {
          origin: 'existing',
        }),
      },
      { 'GET /api/auth/me': { body: { name: 'deckhand', role: 'user' } } },
    )
    renderApp('/health')

    expect(await screen.findByText('設定頁只有管理員進得去，請管理員來看。')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /前往設定/ })).not.toBeInTheDocument()
  })

  it('連續失敗次數看得見——「剛剛壞的」與「壞了一整天」不是同一件事', async () => {
    const base = withFailedService('prowlarr', 'refused')
    render({
      body: {
        ...base,
        services: base.services.map((row) =>
          row.kind === 'prowlarr' ? { ...row, failures: 7 } : row,
        ),
      },
    })
    renderApp('/health')

    expect(await screen.findByText('連續失敗 7 次')).toBeInTheDocument()
  })

  it('設定漂移是「需要你」而不是紅燈——服務還在動', async () => {
    const base = healthDetail()
    render({
      body: {
        ...base,
        services: base.services.map((row) =>
          row.kind === 'qbittorrent' ? { ...row, drift: ['auto_tmm_enabled'] } : row,
        ),
      },
    })
    renderApp('/health')

    await screen.findByRole('region', { name: 'qBittorrent' })

    expect(card('qBittorrent').getByText('設定被改過')).toBeInTheDocument()
    expect(card('qBittorrent').getByText('auto_tmm_enabled')).toBeInTheDocument()
    expect(card('qBittorrent').queryByText('阻擋')).not.toBeInTheDocument()
    // 漂移是這一頁唯一有東西可以按的狀態，而按鈕住在設定頁。
    expect(
      card('qBittorrent').getByRole('link', { name: '前往設定：qBittorrent' }),
    ).toHaveAttribute('href', '/settings/qbittorrent')
    expect(card('Jellyfin').queryByRole('link', { name: /前往設定/ })).not.toBeInTheDocument()
  })

  /**
   * 票 03 第 14 條。原本是靜默 `redirect` 到 `/health`：一般使用者按下深連結之後
   * 換了一頁，而畫面一個字都沒說為什麼（PRODUCT.md 原則 4）。
   */
  it.each(['/settings/qbittorrent', '/settings/routes'])(
    '一般使用者開 %s 被送到健康頁時，畫面說得出為什麼',
    async (path) => {
      render(
        { body: healthDetail() },
        { 'GET /api/auth/me': { body: { name: 'deckhand', role: 'user' } } },
      )
      const { router } = renderApp(path)

      await waitFor(() => expect(router.state.location.pathname).toBe('/health'))
      expect(await screen.findByText(/只有管理員/)).toBeVisible()
    },
  )

  it('一般使用者看不到那條連結——設定頁只有 admin 進得去', async () => {
    const base = healthDetail()
    render(
      {
        body: {
          ...base,
          services: base.services.map((row) =>
            row.kind === 'qbittorrent' ? { ...row, drift: ['auto_tmm_enabled'] } : row,
          ),
        },
      },
      { 'GET /api/auth/me': { body: { name: 'deckhand', role: 'user' } } },
    )
    renderApp('/health')

    await screen.findByRole('region', { name: 'qBittorrent' })

    expect(card('qBittorrent').getByText('設定被改過')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /前往設定/ })).not.toBeInTheDocument()
  })

  it('Route 區塊給 admin 一條到 Route 設定的連結，一般使用者沒有（票 14）', async () => {
    render({ body: healthDetail() })
    renderApp('/health')

    const link = await screen.findByRole('link', { name: '到 Route 設定' })
    expect(link).toHaveAttribute('href', '/settings/routes')
  })

  it('停用的 Route 在它那一列說出來：總結不算它，畫面要說得出為什麼（票 14）', async () => {
    render({
      body: healthDetail({
        routes: [
          routeView(),
          routeView({ id: 4, slug: 'tv-2', name: 'TV 2', enabled: false, health: 'failed' }),
        ],
      }),
    })
    renderApp('/health')

    const summary = (await screen.findByText('TV 2', { selector: 'summary *' })).closest('summary')!
    expect(within(summary).getByText('停用')).toBeInTheDocument()
  })

  it('一般使用者看不到 Route 設定的連結', async () => {
    render(
      { body: healthDetail() },
      { 'GET /api/auth/me': { body: { name: 'deckhand', role: 'user' } } },
    )
    renderApp('/health')

    await screen.findByRole('region', { name: 'qBittorrent' })
    expect(screen.queryByRole('link', { name: '到 Route 設定' })).not.toBeInTheDocument()
  })

  it('迴圈還沒跑第一輪時說「尚未檢查」，不是「尚未接上」', async () => {
    // 精靈按完完成到第一個 tick 之間（最長 30 秒）：服務接好了，只是還沒被檢查過。
    const base = healthDetail()
    render({
      body: {
        ...base,
        status: 'ok',
        checked_at: null,
        services: base.services.map((row) => ({
          ...row,
          status: 'unknown' as const,
          detail: '',
          checked_at: null,
          last_ok_at: null,
          configured: false,
        })),
        routes_status: 'unknown',
      },
    })
    renderApp('/health')

    await screen.findByRole('region', { name: 'Jellyfin' })

    expect(card('Jellyfin').getByText('尚未檢查')).toBeInTheDocument()
    expect(screen.queryByText('尚未接上')).not.toBeInTheDocument()
  })

  it('每條 Route 也有最後成功時間', async () => {
    render({ body: healthDetail() })
    const { container } = renderApp('/health')

    await screen.findByRole('region', { name: 'Jellyfin' })
    const rows = container.querySelectorAll<HTMLDetailsElement>('details')
    rows[0].open = true

    expect(within(rows[0]).getByText('最後成功')).toBeInTheDocument()
  })

  it('跳過索引站的人看到的是「尚未接上」，不是一盞永遠的紅燈', async () => {
    const base = healthDetail()
    render({
      body: {
        ...base,
        services: base.services.map((row) =>
          row.kind === 'prowlarr'
            ? { ...row, status: 'unknown' as const, configured: false, detail: '', base_url: '' }
            : row,
        ),
      },
    })
    renderApp('/health')

    await screen.findByRole('region', { name: 'Prowlarr' })

    expect(card('Prowlarr').getByText('尚未接上')).toBeInTheDocument()
    expect(screen.queryByText('阻擋')).not.toBeInTheDocument()
  })

  it('綠燈的 Route 收起來，紅燈的就地展開五條纜繩', async () => {
    render({
      body: healthDetail({
        routes_status: 'failed',
        routes: [
          routeView({ library: 'TV' }),
          routeView({
            library: 'Anime',
            health: 'failed',
            checks: [
              step('category', 'ok'),
              step('download_path', 'ok'),
              step('library_path', 'ok'),
              step('probe_visible', 'failed', '', 'Jellyfin cannot see /data/library/anime'),
              step('hardlink', 'pending'),
            ],
          }),
        ],
      }),
    })
    const { container } = renderApp('/health')

    await screen.findByRole('region', { name: 'Jellyfin' })
    const rows = container.querySelectorAll<HTMLDetailsElement>('details')

    expect(rows).toHaveLength(2)
    expect(rows[0].open).toBe(false)
    expect(rows[1].open).toBe(true)
    expect(screen.getByText('Jellyfin cannot see /data/library/anime')).toBeInTheDocument()
  })

  it('「立即重測」真的重跑一輪，而且載入這一頁時不會自己跑', async () => {
    const fresh = withFailedService('qbittorrent', 'connection refused')
    const stub = render({ body: healthDetail() }, { [CHECK]: { body: fresh } })
    renderApp('/health')

    await screen.findByRole('region', { name: 'qBittorrent' })
    expect(stub.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(0)

    await userEvent.click(screen.getByRole('button', { name: '立即重測' }))

    expect(await screen.findByText('connection refused')).toBeInTheDocument()
  })

  describe('下載迴圈（票 10）', () => {
    it('上一輪何時跑的與輪詢間隔並排——三個服務都綠著也可能整片停住', async () => {
      render({ body: healthDetail() })
      renderApp('/health')

      const loop = within(await screen.findByRole('region', { name: '下載迴圈' }))
      expect(loop.getByText('上次輪詢')).toBeInTheDocument()
      expect(loop.getByText(/有下載時每 5 秒/)).toBeInTheDocument()
    })

    it('連續失敗時把服務回的原文原樣貼出來，不翻譯', async () => {
      render({
        body: healthDetail({
          poller: pollerView({
            failures: 4,
            error: 'GET /api/v2/sync/maindata: connection refused',
          }),
        }),
      })
      renderApp('/health')

      const loop = within(await screen.findByRole('region', { name: '下載迴圈' }))
      expect(loop.getByText('4')).toBeInTheDocument()
      expect(loop.getByText('GET /api/v2/sync/maindata: connection refused')).toBeInTheDocument()
    })

    it('沒有無主 torrent 時整份清單不畫——0 是正常，不是一個要人看的數字', async () => {
      render({ body: healthDetail() })
      renderApp('/health')

      const loop = within(await screen.findByRole('region', { name: '下載迴圈' }))
      expect(loop.queryByText('無主 torrent')).not.toBeInTheDocument()
    })

    it('無主 torrent 逐筆列出 client state、發佈名、category 與短 hash', async () => {
      render({
        body: healthDetail({
          poller: pollerView({
            unknown_torrents: [
              {
                hash: '3f9a2c1b00000000000000000000000000000000',
                name: 'Some.Release.2160p.WEB-DL',
                category: 'berth-tv',
                state: 'stalledUP',
              },
            ],
          }),
        }),
      })
      renderApp('/health')

      const loop = within(await screen.findByRole('region', { name: '下載迴圈' }))
      // `client_state` 是 qBittorrent 的機器字串，不翻譯（The Machine String Rule）。
      expect(loop.getByText('stalledUP')).toBeInTheDocument()
      expect(loop.getByText('Some.Release.2160p.WEB-DL')).toBeInTheDocument()
      expect(loop.getByText('berth-tv')).toBeInTheDocument()
      expect(loop.getByText('3f9a2c1b0000')).toBeInTheDocument()
    })
  })

  describe('請求預算（M3 票 20）', () => {
    const BUDGET = 'GET /api/health/budget'

    it('每一站這一小時用了多少、誰用的；輪詢、補漏、搜尋共用一份', async () => {
      render(
        { body: healthDetail() },
        {
          [BUDGET]: {
            body: {
              limit: 60,
              window_seconds: 3600,
              sites: [
                {
                  site: 'mikanani.me',
                  used: 10,
                  by_use: [
                    { use: 'poll', count: 4 },
                    { use: 'backfill', count: 1 },
                    { use: 'search', count: 5 },
                  ],
                  frees_at: null,
                  deferred: [],
                },
              ],
            },
          },
        },
      )
      renderApp('/health')

      const budget = within(await screen.findByRole('region', { name: '請求預算' }))
      expect(budget.getByText('mikanani.me')).toBeInTheDocument()
      expect(budget.getByText('10 / 60')).toBeInTheDocument()
      expect(budget.getByText('RSS 輪詢 4 · 每日補漏 1 · 搜尋 5')).toBeInTheDocument()
      expect(budget.queryByText(/延後/)).not.toBeInTheDocument()
    })

    it('用完時被延後的工作說得出來：哪一種、擋了幾個請求、何時放得下（票 20 驗收）', async () => {
      const later = new Date(Date.now() + 30 * 60 * 1000).toISOString()
      render(
        { body: healthDetail() },
        {
          [BUDGET]: {
            body: {
              limit: 10,
              window_seconds: 3600,
              sites: [
                {
                  site: 'mikanani.me',
                  used: 10,
                  by_use: [{ use: 'poll', count: 10 }],
                  frees_at: later,
                  deferred: [
                    {
                      use: 'backfill',
                      refused: 3,
                      since: new Date().toISOString(),
                      until: later,
                    },
                  ],
                },
              ],
            },
          },
        },
      )
      renderApp('/health')

      const budget = within(await screen.findByRole('region', { name: '請求預算' }))
      expect(budget.getByText('延後：每日補漏（擋下 3 個請求）')).toBeInTheDocument()
      expect(budget.getByText('30 分鐘後')).toBeInTheDocument()
    })

    it('這一小時還沒問過任何站時說一句話，不畫空表', async () => {
      render(
        { body: healthDetail() },
        { [BUDGET]: { body: { limit: 60, window_seconds: 3600, sites: [] } } },
      )
      renderApp('/health')

      const budget = within(await screen.findByRole('region', { name: '請求預算' }))
      expect(budget.getByText('這一小時還沒有問過任何站。')).toBeInTheDocument()
    })
  })

  it('後端連不上時說得出來，而不是一片空白', async () => {
    render({ status: 500, body: { detail: 'boom' } })
    renderApp('/health')

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
  })

  it('還沒有 Route 時說明要去哪裡建，而不是報錯', async () => {
    render({ body: healthDetail({ routes_status: 'unknown', routes: [] }) })
    renderApp('/health')

    expect(await screen.findByText(/還沒有 Route/)).toBeInTheDocument()
  })
})
