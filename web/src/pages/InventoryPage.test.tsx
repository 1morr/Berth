import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Inventory, InventoryItem, InventoryRoute } from '../api/inventory'
import { HEALTHY, stubApi, type StubRoute } from '../test/fetch'
import { renderApp } from '../test/render'

afterEach(() => {
  vi.unstubAllGlobals()
})

function routeRow(overrides: Partial<InventoryRoute> = {}): InventoryRoute {
  return {
    slug: 'tv',
    name: 'TV',
    collection_type: 'tvshows',
    enabled: true,
    titles: 3,
    review: 1,
    unmatched: 1,
    ...overrides,
  }
}

function item(overrides: Partial<InventoryItem> = {}): InventoryItem {
  return {
    media_id: 'tv:136315',
    kind: 'tv',
    title: '大熊餐廳',
    title_en: 'The Bear',
    year: 2022,
    poster_url: '',
    status: 'partial',
    imported: 10,
    aired: 28,
    versions: 0,
    needs_review: false,
    has_unmatched: false,
    audits: 0,
    presence: 'found',
    jellyfin_item_id: 'b26853ef1000814d9563768d24869a99',
    ...overrides,
  }
}

/** TV 那一條：一部入庫一半而 Jellyfin 找到了、一部停在待審、一部還在下載。 */
function wall(overrides: Partial<Inventory> = {}): Inventory {
  return {
    route: routeRow(),
    // 套件內的 Jellyfin：主機名要由瀏覽器補上（jsdom 是 `http://localhost`）。
    jellyfin: { public_url: '', url: '', port: 8096 },
    items: [
      item(),
      item({
        media_id: 'tv:120089',
        title: 'SPY×FAMILY 間諜家家酒',
        title_en: 'SPY x FAMILY',
        status: 'review',
        imported: 0,
        aired: 37,
        needs_review: true,
        has_unmatched: true,
        presence: 'none',
        jellyfin_item_id: '',
      }),
      item({
        media_id: 'tv:209867',
        title: '葬送的芙莉蓮',
        title_en: "Frieren: Beyond Journey's End",
        status: 'downloading',
        imported: 3,
        aired: 28,
        presence: 'searching',
        jellyfin_item_id: '',
      }),
    ],
    ...overrides,
  }
}

const ROUTES = [
  routeRow(),
  routeRow({ slug: 'anime', name: 'Anime', titles: 0, review: 0, unmatched: 0 }),
  routeRow({
    slug: 'movies',
    name: 'Movies',
    collection_type: 'movies',
    titles: 1,
    review: 0,
    unmatched: 0,
  }),
]

function render(
  routes: Record<string, StubRoute | (() => StubRoute)> = {},
  role: 'admin' | 'user' = 'admin',
) {
  return stubApi({
    'GET /api/health': { body: HEALTHY },
    'GET /api/auth/me': { body: { name: 'skipper', role } },
    'GET /api/inventory': { body: ROUTES },
    'GET /api/inventory/tv': { body: wall() },
    'GET /api/inventory/anime': {
      body: wall({ route: ROUTES[1], items: [] }),
    },
    ...routes,
  })
}

/** 牆上的一格：以標題（每一格一個 heading）找到它所在的那一格。 */
function tile(title: string) {
  return screen.getByRole('heading', { name: new RegExp(title) }).closest('article')!
}

async function findTile(title: string) {
  return (await screen.findByRole('heading', { name: new RegExp(title) })).closest('article')!
}

describe('媒體庫頁', () => {
  it('頁首有「媒體庫」，而 /library 直接落在第一條 Route', async () => {
    render()
    const { router } = renderApp('/library')

    await waitFor(() => expect(router.state.location.pathname).toBe('/library/tv'))
    expect(await screen.findByRole('link', { name: '媒體庫' })).toBeVisible()
  })

  it('切換列列出每一條 Route 與它的作品數，現在這一條標成當前頁', async () => {
    render()
    renderApp('/library/tv')

    const switcher = await screen.findByRole('navigation', { name: 'Route' })
    const current = within(switcher).getByRole('link', { name: /TV/ })

    expect(current).toHaveAttribute('aria-current', 'page')
    expect(current).toHaveTextContent('3 部')
    expect(within(switcher).getByRole('link', { name: /Anime/ })).toHaveTextContent('0 部')
  })

  it('卡片本體連到 Berth 的 Media 詳情（使用者拍板）', async () => {
    render()
    renderApp('/library/tv')

    const link = await screen.findByRole('link', { name: /大熊餐廳/ })

    expect(link).toHaveAttribute('href', '/media/tv%3A136315')
  })

  it('Jellyfin 找到了的作品有一條連到它的深連結，開在瀏覽器自己的主機上', async () => {
    render()
    renderApp('/library/tv')

    await screen.findByRole('link', { name: /大熊餐廳/ })
    const open = within(tile('大熊餐廳')).getByRole('link', { name: /在 Jellyfin 開啟/ })

    expect(open).toHaveAttribute(
      'href',
      'http://localhost:8096/web/#/details?id=b26853ef1000814d9563768d24869a99',
    )
    expect(open).toHaveAttribute('target', '_blank')
    // 每一格都有這一條：名字說得出會開新分頁，描述說得出是哪一部（WCAG 2.4.4，依上下文）。
    // 標題不塞進名字裡——那會讓它與卡片本體那一條連結撞名。
    expect(open).toHaveAccessibleName('在 Jellyfin 開啟（開新分頁）')
    expect(open).toHaveAccessibleDescription('大熊餐廳')
  })

  it('還沒反查到時說原因，不給一條死連結（票 13 驗收）', async () => {
    render()
    renderApp('/library/tv')

    await screen.findByRole('link', { name: /葬送的芙莉蓮/ })

    expect(within(tile('葬送的芙莉蓮')).getByText('Jellyfin 還在掃描')).toBeVisible()
    expect(
      within(tile('葬送的芙莉蓮')).queryByRole('link', { name: /在 Jellyfin 開啟/ }),
    ).not.toBeInTheDocument()
  })

  it('反查用完了就說 Jellyfin 找不到它', async () => {
    render({
      'GET /api/inventory/tv': {
        body: wall({ items: [item({ presence: 'lost', jellyfin_item_id: '' })] }),
      },
    })
    renderApp('/library/tv')

    expect(await screen.findByText('Jellyfin 找不到它')).toBeVisible()
  })

  it('一格說得出它的狀態與入庫了幾集', async () => {
    render()
    renderApp('/library/tv')

    await screen.findByRole('link', { name: /大熊餐廳/ })

    expect(within(tile('大熊餐廳')).getByText('部分')).toBeVisible()
    expect(within(tile('大熊餐廳')).getByText('10 / 28 集入庫')).toBeVisible()
    expect(within(tile('SPY×FAMILY')).getByText('待審')).toBeVisible()
  })

  it('medium 自動入庫、還要人看一眼的檔案數貼在卡片上（brief §6.5、票 15）', async () => {
    render({
      'GET /api/inventory/tv': {
        body: wall({ items: [item({ status: 'complete', audits: 11 })] }),
      },
    })
    renderApp('/library/tv')

    expect(within(await findTile('大熊餐廳')).getByText('11 個待確認')).toBeVisible()
  })

  it('電影說的是版本數，不是集數', async () => {
    render({
      'GET /api/inventory/tv': {
        body: wall({
          items: [
            item({
              media_id: 'movie:872585',
              kind: 'movie',
              title: '奧本海默',
              title_en: 'Oppenheimer',
              status: 'complete',
              imported: 1,
              aired: 1,
              versions: 2,
              jellyfin_item_id: 'movie-1',
            }),
          ],
        }),
      },
    })
    renderApp('/library/tv')

    expect(await screen.findByText('2 個版本')).toBeVisible()
    expect(screen.getByText('已入庫')).toBeVisible()
  })

  it('篩選「待審」只留下待審的作品，網址記得它，筆數唸得出來', async () => {
    render()
    const { router } = renderApp('/library/tv')

    await userEvent.click(await screen.findByRole('link', { name: '待審 1' }))

    await waitFor(() => expect(router.state.location.search).toEqual({ filter: 'review' }))
    expect(screen.getByRole('link', { name: /SPY×FAMILY/ })).toBeVisible()
    expect(screen.queryByRole('link', { name: /大熊餐廳/ })).not.toBeInTheDocument()
    expect(screen.getByText('顯示 1 部作品')).toHaveAttribute('aria-live', 'polite')
  })

  it('篩選「Unmatched」只留下有對不到檔案的作品', async () => {
    render()
    renderApp('/library/tv?filter=unmatched')

    expect(await screen.findByRole('link', { name: /SPY×FAMILY/ })).toBeVisible()
    expect(screen.queryByRole('link', { name: /葬送的芙莉蓮/ })).not.toBeInTheDocument()
  })

  it('篩完什麼都沒有時，給一條回到全部的路', async () => {
    render({
      'GET /api/inventory/tv': { body: wall({ items: [item()] }) },
    })
    renderApp('/library/tv?filter=review')

    expect(await screen.findByText('沒有待審的作品。')).toBeVisible()
    expect(screen.getByRole('link', { name: '顯示全部' })).toBeVisible()
  })

  it('一條 Route 還沒有作品時說得出下一步', async () => {
    render()
    renderApp('/library/anime')

    expect(await screen.findByText(/「Anime」還沒有任何作品/)).toBeVisible()
    expect(screen.getByRole('link', { name: '回探索頁' })).toHaveAttribute('href', '/')
  })

  it('一條 Route 都沒有時，管理員拿到一條去精靈建 Route 的連結', async () => {
    render({ 'GET /api/inventory': { body: [] } })
    renderApp('/library')

    expect(await screen.findByText(/還沒有任何 Route/)).toBeVisible()
    expect(screen.getByRole('link', { name: '到設定精靈建 Route' })).toHaveAttribute(
      'href',
      '/setup?berth=4',
    )
  })

  it('一般使用者看到的是「請管理員」，不是一條進不去的連結', async () => {
    render({ 'GET /api/inventory': { body: [] } }, 'user')
    renderApp('/library')

    expect(await screen.findByText('請管理員建一條 Route。')).toBeVisible()
    expect(screen.queryByRole('link', { name: '到設定精靈建 Route' })).not.toBeInTheDocument()
  })

  it('網址上的 Route 不存在時說清楚，並連到第一條', async () => {
    render({
      'GET /api/inventory/old': { status: 404, body: { detail: 'no such route' } },
    })
    renderApp('/library/old')

    expect(await screen.findByText('沒有叫「old」的 Route。')).toBeVisible()
    expect(screen.getByRole('link', { name: '看「TV」' })).toHaveAttribute('href', '/library/tv')
  })

  it('停用的 Route 仍然在切換列上，而且說得出它停用了', async () => {
    render({
      'GET /api/inventory': {
        body: [routeRow(), routeRow({ slug: 'old', name: 'Old', enabled: false })],
      },
    })
    renderApp('/library/tv')

    const switcher = await screen.findByRole('navigation', { name: 'Route' })

    expect(within(switcher).getByRole('link', { name: /Old/ })).toHaveTextContent('停用')
  })
})
