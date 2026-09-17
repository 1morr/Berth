import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Inventory, InventoryCard, InventoryLibrary } from '../api/inventory'
import { HEALTHY, session, stubApi, type StubRoute } from '../test/fetch'
import { renderApp } from '../test/render'

afterEach(() => {
  vi.unstubAllGlobals()
})

/** Jellyfin 的媒體庫 id（32 個十六進位字元，研究 §2）。 */
const TV = '4514ec850e5ad0c47b58444e17b6346c'
const MOVIES = 'f137a2dd21bbc1b99aa5c0f6bf02a805'

function library(overrides: Partial<InventoryLibrary> = {}): InventoryLibrary {
  return { id: TV, name: 'TV', collection_type: 'tvshows', ...overrides }
}

/** Jellyfin 牆上、不是 Berth 經手的一部。 */
function jellyfinCard(overrides: Partial<InventoryCard> = {}): InventoryCard {
  return {
    media_id: 'tv:1399',
    kind: 'tv',
    title: 'Alpha Show',
    title_en: 'Alpha Show',
    year: 2022,
    poster_url: '',
    presence: 'found',
    jellyfin_item_id: '2a9857e656bbd18b7c3c3a3b4ee5eef1',
    tracking: null,
    ...overrides,
  }
}

function tracking(overrides: Partial<NonNullable<InventoryCard['tracking']>> = {}) {
  return {
    status: 'partial' as const,
    imported: 10,
    aired: 28,
    versions: 0,
    needs_review: false,
    has_unmatched: false,
    audits: 0,
    ...overrides,
  }
}

/** Berth 經手、Jellyfin 已經有的那一部：牆上與 `tracked` 裡是同一格。 */
const BEAR = jellyfinCard({
  media_id: 'tv:136315',
  title: 'The Bear',
  title_en: 'The Bear',
  jellyfin_item_id: 'b26853ef1000814d9563768d24869a99',
  tracking: tracking(),
})

/** 還沒進 Jellyfin 的兩部：一部停在待審、一部還在下載。 */
const SPY = jellyfinCard({
  media_id: 'tv:120089',
  title: 'SPY×FAMILY 間諜家家酒',
  title_en: 'SPY x FAMILY',
  poster_url: 'https://image.tmdb.org/t/p/w342/spy.jpg',
  presence: 'none',
  jellyfin_item_id: '',
  tracking: tracking({
    status: 'review',
    imported: 0,
    aired: 37,
    needs_review: true,
    has_unmatched: true,
  }),
})
const FRIEREN = jellyfinCard({
  media_id: 'tv:209867',
  title: '葬送的芙莉蓮',
  title_en: "Frieren: Beyond Journey's End",
  presence: 'searching',
  jellyfin_item_id: '',
  tracking: tracking({ status: 'downloading', imported: 3 }),
})

/** 沒有 TMDB id 的 Jellyfin 作品：只有深連結。 */
const HOTEL = jellyfinCard({
  media_id: '',
  title: 'Hotel Show',
  title_en: 'Hotel Show',
  year: null,
  jellyfin_item_id: '9ea3bb1459aa4795a5ebf54b94fe0cc9',
})

function wall(overrides: Partial<Inventory> = {}): Inventory {
  return {
    library: library(),
    // 套件內的 Jellyfin：主機名要由瀏覽器補上（jsdom 是 `http://localhost`）。
    jellyfin: { public_url: '', url: '', port: 8096 },
    page: 1,
    page_size: 100,
    total: 3,
    titles: [jellyfinCard(), HOTEL, BEAR],
    tracked: [BEAR, FRIEREN, SPY],
    review: 1,
    unmatched: 1,
    ...overrides,
  }
}

const LIBRARIES = [library(), library({ id: MOVIES, name: 'Movies', collection_type: 'movies' })]

function render(
  routes: Record<string, StubRoute | (() => StubRoute)> = {},
  role: 'admin' | 'user' = 'admin',
) {
  return stubApi({
    'GET /api/health': { body: HEALTHY },
    'GET /api/auth/me': { body: { name: 'skipper', role } },
    'GET /api/inventory': { body: LIBRARIES },
    [`GET /api/inventory/${TV}`]: { body: wall() },
    ...routes,
  })
}

/** 牆上的一格：以標題（每一格一個 heading）找到它所在的那一格。 */
function tile(title: string, within_: HTMLElement = document.body) {
  return within(within_)
    .getByRole('heading', { name: new RegExp(title) })
    .closest('article')!
}

async function findTile(title: string) {
  return (await screen.findByRole('heading', { name: new RegExp(title) })).closest('article')!
}

function band() {
  return screen.getByRole('region', { name: '還沒進 Jellyfin' })
}

describe('媒體庫頁', () => {
  it('頁首有「媒體庫」，而 /library 直接落在這位使用者的第一個媒體庫', async () => {
    render()
    const { router } = renderApp('/library')

    await waitFor(() => expect(router.state.location.pathname).toBe(`/library/${TV}`))
    expect(await screen.findByRole('link', { name: '媒體庫' })).toBeVisible()
  })

  it('切換列列出看得到的媒體庫名，現在這一個標成當前頁', async () => {
    render()
    renderApp(`/library/${TV}`)

    const switcher = await screen.findByRole('navigation', { name: '媒體庫' })
    const current = within(switcher).getByRole('link', { name: 'TV' })

    expect(current).toHaveAttribute('aria-current', 'page')
    expect(within(switcher).getByRole('link', { name: 'Movies' })).toHaveAttribute(
      'href',
      `/library/${MOVIES}`,
    )
  })

  describe('Jellyfin 的牆', () => {
    it('不是 Berth 經手的作品也在牆上，沒有任何狀態色塊', async () => {
      render()
      renderApp(`/library/${TV}`)

      const alpha = await findTile('Alpha Show')

      expect(within(alpha).queryByText('部分')).not.toBeInTheDocument()
      expect(within(alpha).getByRole('link', { name: /Alpha Show/ })).toHaveAttribute(
        'href',
        '/media/tv%3A1399',
      )
    })

    it('沒有 TMDB id 的作品只給 Jellyfin 深連結，開在瀏覽器自己的主機上', async () => {
      render()
      renderApp(`/library/${TV}`)

      const hotel = await findTile('Hotel Show')
      const links = within(hotel).getAllByRole('link')

      expect(links).toHaveLength(1)
      expect(links[0]).toHaveAccessibleName('在 Jellyfin 開啟（開新分頁）')
      expect(links[0]).toHaveAccessibleDescription('Hotel Show')
      expect(links[0]).toHaveAttribute(
        'href',
        'http://localhost:8096/web/#/details?id=9ea3bb1459aa4795a5ebf54b94fe0cc9',
      )
      expect(links[0]).toHaveAttribute('target', '_blank')
    })

    it('Berth 經手的作品疊上狀態與入庫集數', async () => {
      render()
      renderApp(`/library/${TV}`)

      const bear = await findTile('The Bear')

      expect(within(bear).getByText('部分')).toBeVisible()
      expect(within(bear).getByText('10 / 28 集入庫')).toBeVisible()
    })

    it('Jellyfin 的名稱不跟 UI 語言換，切換時也不重抓（使用者拍板，brief §7.5）', async () => {
      const api = render()
      renderApp(`/library/${TV}`)
      await findTile('Alpha Show')
      const fetched = api.mock.calls.length

      await userEvent.click(screen.getByRole('button', { name: 'EN' }))

      expect(await screen.findByRole('navigation', { name: 'Libraries' })).toBeVisible()
      expect(within(tile('Alpha Show')).getAllByText('Alpha Show')).toHaveLength(1)
      expect(api.mock.calls.length).toBe(fetched)
    })

    it('medium 自動入庫、還要人看一眼的檔案數貼在卡片上（brief §6.5、票 15）', async () => {
      const checked = { ...BEAR, tracking: tracking({ status: 'complete', audits: 11 }) }
      render({
        [`GET /api/inventory/${TV}`]: { body: wall({ titles: [checked], tracked: [checked] }) },
      })
      renderApp(`/library/${TV}`)

      expect(within(await findTile('The Bear')).getByText('11 個待確認')).toBeVisible()
    })

    it('電影說的是版本數，不是集數', async () => {
      const film = jellyfinCard({
        media_id: 'movie:872585',
        kind: 'movie',
        title: 'Oppenheimer',
        title_en: 'Oppenheimer',
        tracking: tracking({ status: 'complete', imported: 1, aired: 1, versions: 2 }),
      })
      render({
        [`GET /api/inventory/${MOVIES}`]: {
          body: wall({ library: LIBRARIES[1], titles: [film], tracked: [film], total: 1 }),
        },
      })
      renderApp(`/library/${MOVIES}`)

      expect(within(await findTile('Oppenheimer')).getByText('2 個版本')).toBeVisible()
      expect(screen.getByText('已入庫')).toBeVisible()
    })
  })

  describe('還沒進 Jellyfin', () => {
    it('Berth 經手、Jellyfin 還沒有的作品在牆上方自己一條', async () => {
      render()
      renderApp(`/library/${TV}`)

      await findTile('Alpha Show')
      const arriving = band()

      expect(within(arriving).getByText('2 部作品還沒進 Jellyfin')).toBeInTheDocument()
      expect(within(arriving).getByText('待審')).toBeVisible()
      // 已經在 Jellyfin 裡的那一部不重複出現在這一條。
      expect(within(arriving).queryByRole('heading', { name: /The Bear/ })).not.toBeInTheDocument()
    })

    it('說得出 Jellyfin 那邊走到哪，不給一條死連結', async () => {
      render()
      renderApp(`/library/${TV}`)

      await findTile('Alpha Show')
      const frieren = tile('葬送的芙莉蓮', band())

      expect(within(frieren).getByText('Jellyfin 還在掃描')).toBeVisible()
      expect(
        within(frieren).queryByRole('link', { name: /在 Jellyfin 開啟/ }),
      ).not.toBeInTheDocument()
    })

    it('標題與海報是 TMDB 的，標題跟著 UI 語言', async () => {
      render()
      renderApp(`/library/${TV}`)
      await findTile('SPY×FAMILY')

      await userEvent.click(screen.getByRole('button', { name: 'EN' }))

      const spy = await findTile('SPY x FAMILY')
      expect(spy).not.toHaveTextContent('間諜家家酒')
    })

    it('Jellyfin 裡還一部都沒有時，不說「這個媒體庫還沒有任何作品」', async () => {
      render({ [`GET /api/inventory/${TV}`]: { body: wall({ total: 0, titles: [] }) } })
      renderApp(`/library/${TV}`)

      await findTile('葬送的芙莉蓮')

      expect(screen.queryByText('「TV」還沒有任何作品。')).not.toBeInTheDocument()
    })

    it('每一部都在 Jellyfin 裡時這一條不畫', async () => {
      render({ [`GET /api/inventory/${TV}`]: { body: wall({ tracked: [BEAR] }) } })
      renderApp(`/library/${TV}`)

      await findTile('The Bear')

      expect(screen.queryByRole('region', { name: '還沒進 Jellyfin' })).not.toBeInTheDocument()
    })
  })

  describe('分頁', () => {
    const big = (page: number) =>
      wall({
        page,
        total: 250,
        titles: [jellyfinCard({ title: `Show on page ${page}`, title_en: `Show on page ${page}` })],
      })

    it('第一頁說得出範圍，下一頁寫進網址，上一頁按不了', async () => {
      render({ [`GET /api/inventory/${TV}`]: { body: big(1) } })
      renderApp(`/library/${TV}`)

      const pager = (await screen.findAllByRole('navigation', { name: '分頁' }))[0]!

      expect(within(pager).getByText('1–100 / 250')).toBeVisible()
      expect(within(pager).getByText('第 1–100 部，共 250 部')).toHaveAttribute(
        'aria-live',
        'polite',
      )
      expect(within(pager).getByRole('link', { name: '下一頁' })).toHaveAttribute(
        'href',
        `/library/${TV}?page=2`,
      )
      expect(within(pager).getByText('上一頁')).toHaveAttribute('aria-disabled', 'true')
    })

    it('換頁向後端要那一頁，最後一頁的下一頁按不了', async () => {
      const api = render({
        [`GET /api/inventory/${TV}`]: { body: big(1) },
        [`GET /api/inventory/${TV}?page=3`]: { body: big(3) },
      })
      renderApp(`/library/${TV}?page=3`)

      expect(await screen.findByRole('heading', { name: 'Show on page 3' })).toBeVisible()
      const pager = screen.getAllByRole('navigation', { name: '分頁' })[0]!

      expect(within(pager).getByText('201–250 / 250')).toBeVisible()
      expect(within(pager).getByRole('link', { name: '上一頁' })).toHaveAttribute(
        'href',
        `/library/${TV}?page=2`,
      )
      expect(within(pager).getByText('下一頁')).toHaveAttribute('aria-disabled', 'true')
      expect(api.mock.calls.map(([input]) => String(input))).toContain(
        `/api/inventory/${TV}?page=3`,
      )
    })

    it('只有一頁時只留範圍，沒有分頁鍵', async () => {
      render()
      renderApp(`/library/${TV}`)

      const pager = (await screen.findAllByRole('navigation', { name: '分頁' }))[0]!

      expect(within(pager).getByText('1–3 / 3')).toBeVisible()
      expect(within(pager).queryByText('下一頁')).not.toBeInTheDocument()
      // 牆底那一組不畫：只有一頁時總數寫一次就夠。
      expect(screen.getAllByRole('navigation', { name: '分頁' })).toHaveLength(1)
    })

    it('頁碼超出範圍時說清楚，給一條回第 1 頁的路', async () => {
      render({ [`GET /api/inventory/${TV}?page=9`]: { body: wall({ page: 9, titles: [] }) } })
      renderApp(`/library/${TV}?page=9`)

      expect(await screen.findByText('這一頁沒有作品。')).toBeVisible()
      expect(screen.getByRole('link', { name: '回第 1 頁' })).toHaveAttribute(
        'href',
        `/library/${TV}`,
      )
    })
  })

  describe('篩選', () => {
    it('「待審」換成 Berth 那一份清單：Jellyfin 內外的都在，帶子與分頁都收起來', async () => {
      render()
      const { router } = renderApp(`/library/${TV}`)

      await userEvent.click(await screen.findByRole('link', { name: '待審 1' }))

      await waitFor(() => expect(router.state.location.search).toEqual({ filter: 'review' }))
      expect(screen.getByRole('heading', { name: /SPY×FAMILY/ })).toBeVisible()
      expect(screen.queryByRole('heading', { name: /Alpha Show/ })).not.toBeInTheDocument()
      expect(screen.queryByRole('region', { name: '還沒進 Jellyfin' })).not.toBeInTheDocument()
      expect(screen.queryByRole('navigation', { name: '分頁' })).not.toBeInTheDocument()
      expect(screen.getByText('顯示 1 部作品')).toHaveAttribute('aria-live', 'polite')
    })

    it('在第 2 頁換篩選不重抓，按回「全部」回到第 2 頁', async () => {
      const second = wall({ page: 2, total: 150 })
      const api = render({ [`GET /api/inventory/${TV}?page=2`]: { body: second } })
      const { router } = renderApp(`/library/${TV}?page=2`)
      await findTile('Alpha Show')
      // 換網址時路由守衛照樣問 `auth/me`，所以只數牆那一支。
      const walls = () =>
        api.mock.calls.filter(([input]) => String(input).startsWith(`/api/inventory/${TV}`)).length
      const fetched = walls()

      await userEvent.click(screen.getByRole('link', { name: '待審 1' }))
      await waitFor(() =>
        expect(router.state.location.search).toEqual({ page: 2, filter: 'review' }),
      )
      await userEvent.click(screen.getByRole('link', { name: '全部' }))

      await waitFor(() => expect(router.state.location.search).toEqual({ page: 2 }))
      expect(walls()).toBe(fetched)
    })

    it('「Unmatched」也看得到已經在 Jellyfin 裡的作品', async () => {
      const flagged = { ...BEAR, tracking: tracking({ has_unmatched: true }) }
      render({ [`GET /api/inventory/${TV}`]: { body: wall({ tracked: [flagged, FRIEREN] }) } })
      renderApp(`/library/${TV}?filter=unmatched`)

      expect(await screen.findByRole('heading', { name: 'The Bear' })).toBeVisible()
      expect(screen.queryByRole('heading', { name: /葬送的芙莉蓮/ })).not.toBeInTheDocument()
    })

    it('篩完什麼都沒有時，給一條回到全部的路', async () => {
      render({ [`GET /api/inventory/${TV}`]: { body: wall({ tracked: [BEAR] }) } })
      renderApp(`/library/${TV}?filter=review`)

      expect(await screen.findByText('這個媒體庫沒有待審的作品。')).toBeVisible()
      expect(screen.getByRole('link', { name: '顯示全部' })).toHaveAttribute(
        'href',
        `/library/${TV}`,
      )
    })
  })

  describe('空與錯', () => {
    it('媒體庫是空的時說得出下一步', async () => {
      render({
        [`GET /api/inventory/${TV}`]: { body: wall({ total: 0, titles: [], tracked: [] }) },
      })
      renderApp(`/library/${TV}`)

      expect(await screen.findByText('「TV」還沒有任何作品。')).toBeVisible()
      expect(screen.getByRole('link', { name: '回探索頁' })).toHaveAttribute('href', '/')
    })

    it('沒有權限與不存在是同一句話，並連到第一個媒體庫', async () => {
      render({
        'GET /api/inventory/anime': {
          status: 404,
          body: { detail: { reason: 'library_not_visible', detail: 'no such library' } },
        },
      })
      renderApp('/library/anime')

      expect(await screen.findByText('找不到這個媒體庫，或你沒有權限看它。')).toBeVisible()
      expect(screen.getByRole('link', { name: '看「TV」' })).toHaveAttribute(
        'href',
        `/library/${TV}`,
      )
    })

    it('Jellyfin 問不到時說原因、貼原文，並給重試與健康頁', async () => {
      let answers = 0
      render({
        'GET /api/inventory': () => {
          answers += 1
          return answers === 1
            ? {
                status: 503,
                body: {
                  detail: {
                    reason: 'jellyfin_unreachable',
                    detail: 'GET /UserViews: connection refused',
                  },
                },
              }
            : { body: LIBRARIES }
        },
      })
      renderApp(`/library/${TV}`)

      expect(await screen.findByRole('alert')).toHaveTextContent('問不到 Jellyfin')
      expect(screen.getByText('GET /UserViews: connection refused')).toBeVisible()
      expect(screen.getByRole('link', { name: '看健康頁' })).toHaveAttribute('href', '/health')

      await userEvent.click(screen.getByRole('button', { name: '重試' }))

      expect(await screen.findByRole('navigation', { name: '媒體庫' })).toBeVisible()
    })

    it('一般使用者沒有電影或劇集媒體庫時，下一步是請管理員', async () => {
      render({ 'GET /api/inventory': { body: [] } }, 'user')
      renderApp('/library')

      expect(await screen.findByText(/沒有電影或劇集媒體庫/)).toBeVisible()
      expect(screen.getByText('請管理員在 Jellyfin 開放媒體庫給你。')).toBeVisible()
    })

    it('管理員拿到一條到 Jellyfin 媒體庫設定的連結', async () => {
      render({
        'GET /api/inventory': { body: [] },
        'GET /api/settings/jellyfin': {
          body: { public_url: '', url: 'http://nas.local:8096', port: null },
        },
      })
      renderApp('/library')

      expect(await screen.findByRole('link', { name: /到 Jellyfin 的媒體庫設定/ })).toHaveAttribute(
        'href',
        'http://nas.local:8096/web/#/dashboard/libraries',
      )
    })

    it('帳號在 Jellyfin 被停用：session 結束，人被送回登入頁並說登入已失效', async () => {
      const account = session({ name: 'deckhand', role: 'user' })
      stubApi({
        'GET /api/health': { body: HEALTHY },
        'GET /api/auth/me': account.me,
        'GET /api/inventory': () => {
          account.signOut()
          return {
            status: 401,
            body: { detail: { reason: 'account_disabled', detail: 'disabled' } },
          }
        },
      })
      const { router } = renderApp(`/library/${TV}`)

      await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
      expect(router.state.location.search).toMatchObject({ expired: true })
    })
  })
})
