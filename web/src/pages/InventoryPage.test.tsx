import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Inventory, InventoryCard, InventoryLibrary } from '../api/inventory'
import type { Watching } from '../api/watching'
import { HEALTHY, session, stubApi, type StubRoute } from '../test/fetch'
import { renderApp } from '../test/render'

afterEach(() => {
  vi.unstubAllGlobals()
})

/** Jellyfin 的媒體庫 id（32 個十六進位字元，研究 §2）。 */
const TV = '4514ec850e5ad0c47b58444e17b6346c'
const MOVIES = 'f137a2dd21bbc1b99aa5c0f6bf02a805'

/** 兩種媒體庫的排序選單（後端 `BROWSABLE`，照 jellyfin-web）。 */
const TV_SORTS: InventoryLibrary['sorts'] = [
  'SortName',
  'Random',
  'CommunityRating',
  'DateCreated',
  'DateLastContentAdded',
  'SeriesDatePlayed',
  'OfficialRating',
  'PremiereDate',
]
const MOVIE_SORTS: InventoryLibrary['sorts'] = [
  'SortName',
  'Random',
  'CommunityRating',
  'CriticRating',
  'DateCreated',
  'DatePlayed',
  'OfficialRating',
  'PlayCount',
  'PremiereDate',
  'Runtime',
]

function library(overrides: Partial<InventoryLibrary> = {}): InventoryLibrary {
  return { id: TV, name: 'TV', collection_type: 'tvshows', sorts: TV_SORTS, ...overrides }
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
    poster_url_en: '',
    presence: 'found',
    jellyfin_item_id: '2a9857e656bbd18b7c3c3a3b4ee5eef1',
    tracking: null,
    watch: null,
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
  poster_url_en: 'https://image.tmdb.org/t/p/w342/spy-en.jpg',
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
    page_size: 50,
    total: 3,
    titles: [jellyfinCard(), HOTEL, BEAR],
    tracked: [BEAR, FRIEREN, SPY],
    review: 1,
    unmatched: 1,
    ...overrides,
  }
}

const LIBRARIES = [
  library(),
  library({ id: MOVIES, name: 'Movies', collection_type: 'movies', sorts: MOVIE_SORTS }),
]

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

/**
 * 牆上的一格：以標題找到它所在的那一格。接著看的格子也有 `h3`（票 13），但它們不是 `article`，所以只認
 * 在 `article` 裡的那一個。
 */
function tile(title: string, within_: HTMLElement = document.body) {
  return wallTile(within(within_).getAllByRole('heading', { name: new RegExp(title) }))
}

async function findTile(title: string) {
  return wallTile(await screen.findAllByRole('heading', { name: new RegExp(title) }))
}

function wallTile(headings: HTMLElement[]) {
  const tiles = headings
    .map((heading) => heading.closest('article'))
    .filter((node) => node !== null)
  expect(tiles).toHaveLength(1)
  return tiles[0]!
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
      const toMedia = within(alpha).getByRole('link', { name: 'Alpha Show' })
      expect(toMedia).toHaveAttribute('href', '/media/tv%3A1399')
      // 名字是作品名，圖位的「無海報」與類型年份不進名字（票 13）；類型年份是描述。
      expect(toMedia).toHaveAccessibleDescription(/^TV\s+2022/)
    })

    it('牆是一份清單，每一格一個 h3 標題（票 13：與探索牆、接著看同一種語意）', async () => {
      render()
      renderApp(`/library/${TV}`)
      await findTile('Alpha Show')

      const list = within(screen.getByRole('region', { name: 'TV' })).getByRole('list')

      expect(within(list).getAllByRole('listitem')).toHaveLength(3)
      expect(
        within(list)
          .getAllByRole('heading', { level: 3 })
          .map((heading) => heading.textContent),
      ).toEqual(['Alpha Show', 'Hotel Show', 'The Bear'])
    })

    it('沒有 TMDB id 的作品只給 Jellyfin 深連結，開在瀏覽器自己的主機上', async () => {
      render()
      renderApp(`/library/${TV}`)

      const hotel = await findTile('Hotel Show')
      const links = within(hotel).getAllByRole('link')

      expect(links).toHaveLength(1)
      // 每一格都有這一條：名字帶上是哪一部（票 13），看得見的「在 Jellyfin 開啟」仍是名字的開頭（WCAG 2.5.3）。
      expect(links[0]).toHaveAccessibleName('在 Jellyfin 開啟：Hotel Show（開新分頁）')
      expect(links[0]).toHaveAttribute(
        'href',
        'http://localhost:8096/web/#/details?id=9ea3bb1459aa4795a5ebf54b94fe0cc9',
      )
      expect(links[0]).toHaveAttribute('target', '_blank')
    })

    it('海報是 Berth 代理的 Jellyfin 圖，網址照後端給的（票 04）', async () => {
      const poster =
        '/api/jellyfin/items/2a9857e656bbd18b7c3c3a3b4ee5eef1/images/Primary?size=poster&tag=f99664090dfd3223c18e80663440deac'
      render({
        [`GET /api/inventory/${TV}`]: {
          body: wall({ titles: [jellyfinCard({ poster_url: poster }), HOTEL] }),
        },
      })
      renderApp(`/library/${TV}`)

      const alpha = await findTile('Alpha Show')

      // `alt=""`：標題就在下面那一行，所以海報不在無障礙樹上，只能從元素找。
      expect(alpha.querySelector('img')).toHaveAttribute('src', poster)
      // 同一張圖的兩個寬度（票 13）：手機兩欄與高密度螢幕挑大的那一張。
      expect(alpha.querySelector('img')).toHaveAttribute(
        'srcset',
        `${poster} 342w, ${poster.replace('size=poster', 'size=poster_large')} 684w`,
      )
      expect(within(alpha).queryByText('無海報')).not.toBeInTheDocument()
      // Jellyfin 真的沒有圖的那一部，說「無海報」是真話。
      expect(within(tile('Hotel Show')).getByText('無海報')).toBeVisible()
    })

    it('海報載不下來（Jellyfin 回 404 或連不上）時換成佔位，其餘的格子照樣在', async () => {
      const poster =
        '/api/jellyfin/items/2a9857e656bbd18b7c3c3a3b4ee5eef1/images/Primary?size=poster&tag=f99664090dfd3223c18e80663440deac'
      render({
        [`GET /api/inventory/${TV}`]: {
          body: wall({ titles: [jellyfinCard({ poster_url: poster }), HOTEL, BEAR] }),
        },
      })
      renderApp(`/library/${TV}`)
      const alpha = await findTile('Alpha Show')

      fireEvent.error(alpha.querySelector('img')!)

      expect(await within(alpha).findByText('無海報')).toBeVisible()
      expect(alpha.querySelector('img')).not.toBeInTheDocument()
      expect(tile('The Bear')).toBeVisible()
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

  describe('觀看狀態（票 05）', () => {
    const UNWATCHED = { played: false, progress: null, unplayed_episodes: null }
    /** 五集看過一集的劇、看到一半的片、看完的劇、還沒看過的片。 */
    const ALPHA = jellyfinCard({ watch: { ...UNWATCHED, unplayed_episodes: 4 } })
    const ECHO = jellyfinCard({
      media_id: 'movie:27205',
      kind: 'movie',
      title: 'Echo Movie',
      title_en: 'Echo Movie',
      jellyfin_item_id: '3b8941d78aeda0bdfb69c6381c8bd1a9',
      watch: { ...UNWATCHED, progress: 42 },
    })
    const BRAVO = jellyfinCard({
      media_id: 'tv:1396',
      title: 'Bravo Show',
      title_en: 'Bravo Show',
      jellyfin_item_id: '6d616414836b339f17e139c3b00fd2ae',
      watch: { ...UNWATCHED, played: true },
    })
    const GOLF = jellyfinCard({
      media_id: 'movie:1',
      kind: 'movie',
      title: 'Golf Movie',
      title_en: 'Golf Movie',
      jellyfin_item_id: 'eab6bd53ab3da44543cdcdf2ab031696',
      watch: { ...UNWATCHED, played: true },
    })
    /** 還沒看過的片：標為已看什麼都不會清掉，一按就送。 */
    const FOXTROT = jellyfinCard({
      media_id: 'movie:157336',
      kind: 'movie',
      title: 'Foxtrot Movie',
      title_en: 'Foxtrot Movie',
      jellyfin_item_id: 'aaad8034da2f8c4db82f7aa3e26a4e3e',
      watch: UNWATCHED,
    })
    const PLAYED = (id: string) => `/api/jellyfin/items/${id}/played`

    function watching(routes: Record<string, StubRoute | (() => StubRoute)> = {}) {
      return render({
        [`GET /api/inventory/${TV}`]: {
          body: wall({
            titles: [ALPHA, BRAVO, ECHO, GOLF, FOXTROT],
            tracked: [FRIEREN, SPY],
          }),
        },
        ...routes,
      })
    }

    function sent(api: ReturnType<typeof render>, method: string, path: string) {
      return api.mock.calls.filter(([url, init]) => url === path && init?.method === method)
    }

    it('卡片用字說出已看、看到幾 %、剩幾集沒看；還沒看過的片什麼都不說', async () => {
      watching({
        [`GET /api/inventory/${TV}`]: {
          body: wall({
            titles: [ALPHA, BRAVO, ECHO, jellyfinCard({ title: 'Hotel Show', watch: UNWATCHED })],
          }),
        },
      })
      renderApp(`/library/${TV}`)

      expect(within(await findTile('Alpha Show')).getByText('剩 4 集沒看')).toBeVisible()
      expect(within(tile('Bravo Show')).getByText('已看')).toBeVisible()
      expect(within(tile('Echo Movie')).getByText('看到 42%')).toBeVisible()
      const hotel = tile('Hotel Show')
      expect(within(hotel).queryByText('已看')).not.toBeInTheDocument()
      expect(hotel).not.toHaveTextContent(/看到|沒看/)
      // 沒看過的照樣標得了。
      expect(within(hotel).getByRole('button', { name: /^標為已看/ })).toBeVisible()
    })

    it('還沒進 Jellyfin 的作品沒有觀看狀態，也沒有切換鍵', async () => {
      watching()
      renderApp(`/library/${TV}`)
      await findTile('Alpha Show')

      expect(within(band()).queryByRole('button', { name: /標為/ })).not.toBeInTheDocument()
    })

    it('劇集標為已看先確認每一集看到一半的位置會歸零；確認之後那一格當場換掉，不重抓整面牆', async () => {
      const api = watching({
        [`POST ${PLAYED(ALPHA.jellyfin_item_id)}`]: { body: { ...UNWATCHED, played: true } },
      })
      renderApp(`/library/${TV}`)
      const alpha = await findTile('Alpha Show')
      const walls = sent(api, 'GET', `/api/inventory/${TV}`).length

      const mark = within(alpha).getByRole('button', { name: /^標為已看/ })
      // 每一格都有這一顆：名字帶上是哪一部（票 13），控制項清單裡不是一整排同名的鍵。
      expect(mark).toHaveAccessibleName('標為已看：Alpha Show')
      await userEvent.click(mark)
      // 劇集的觀看紀錄看不出底下有沒有看到一半的集，所以一律先說（M1.5 票 08 使用者拍板）。
      const confirm = within(alpha).getByRole('group')
      expect(confirm).toHaveAccessibleName(/每一集.*看到一半.*歸零/)
      expect(sent(api, 'POST', PLAYED(ALPHA.jellyfin_item_id))).toHaveLength(0)
      await userEvent.click(within(confirm).getByRole('button', { name: /^標為已看/ }))

      expect(await within(alpha).findByText('已看')).toBeVisible()
      expect(within(alpha).queryByText('剩 4 集沒看')).not.toBeInTheDocument()
      expect(within(alpha).getByRole('button', { name: /^標為未看/ })).toBeVisible()
      // 成功也要唸得出來：焦點回到那一顆鍵時它的名字剛換過，螢幕閱讀器不會重念（票 11 的 audit）。
      expect(within(alpha).getByText('已標為已看。')).toHaveAttribute('aria-live', 'polite')
      expect(sent(api, 'POST', PLAYED(ALPHA.jellyfin_item_id))).toHaveLength(1)
      expect(sent(api, 'GET', `/api/inventory/${TV}`)).toHaveLength(walls)
    })

    it('看到一半的片標為已看先確認：說得出會清掉看到幾 % 的位置', async () => {
      const api = watching({
        [`POST ${PLAYED(ECHO.jellyfin_item_id)}`]: { body: { ...UNWATCHED, played: true } },
      })
      renderApp(`/library/${TV}`)
      const echo = await findTile('Echo Movie')

      await userEvent.click(within(echo).getByRole('button', { name: /^標為已看/ }))

      const confirm = within(echo).getByRole('group')
      expect(confirm).toHaveAccessibleName(/42%.*位置.*找不回來/)
      expect(confirm).toHaveFocus()
      await userEvent.click(within(confirm).getByRole('button', { name: /^標為已看/ }))

      expect(await within(echo).findByText('已看')).toBeVisible()
      expect(sent(api, 'POST', PLAYED(ECHO.jellyfin_item_id))).toHaveLength(1)
    })

    it('還沒看過的片標為已看什麼都不會清掉，一按就送', async () => {
      const api = watching({
        [`POST ${PLAYED(FOXTROT.jellyfin_item_id)}`]: { body: { ...UNWATCHED, played: true } },
      })
      renderApp(`/library/${TV}`)
      const foxtrot = await findTile('Foxtrot Movie')

      await userEvent.click(within(foxtrot).getByRole('button', { name: /^標為已看/ }))

      expect(await within(foxtrot).findByText('已看')).toBeVisible()
      expect(within(foxtrot).queryByRole('group')).not.toBeInTheDocument()
      expect(sent(api, 'POST', PLAYED(FOXTROT.jellyfin_item_id))).toHaveLength(1)
    })

    it('標為未看先確認：說得出會清掉觀看次數與時間，取消就什麼都不送', async () => {
      const api = watching()
      renderApp(`/library/${TV}`)
      const golf = await findTile('Golf Movie')

      await userEvent.click(within(golf).getByRole('button', { name: /^標為未看/ }))

      const confirm = within(golf).getByRole('group')
      expect(confirm).toHaveAccessibleName(/觀看次數.*最後觀看時間.*找不回來/)
      // 電影沒有「集」可以清。
      expect(confirm).not.toHaveAccessibleName(/每一集/)
      expect(confirm).toHaveFocus()

      await userEvent.click(within(golf).getByRole('button', { name: '取消' }))

      expect(within(golf).getByRole('button', { name: /^標為未看/ })).toHaveFocus()
      expect(within(golf).getByText('已看')).toBeVisible()
      expect(api.mock.calls.filter(([, init]) => init?.method === 'DELETE')).toHaveLength(0)
    })

    it('劇集的確認說得出清掉的是每一集，確認之後才送出，牆上換成剩幾集沒看', async () => {
      const api = watching({
        [`DELETE ${PLAYED(BRAVO.jellyfin_item_id)}`]: {
          body: { ...UNWATCHED, unplayed_episodes: 2 },
        },
      })
      renderApp(`/library/${TV}`)
      const bravo = await findTile('Bravo Show')

      await userEvent.click(within(bravo).getByRole('button', { name: /^標為未看/ }))
      const confirm = within(bravo).getByRole('group')
      expect(confirm).toHaveAccessibleName(/每一集.*觀看次數.*最後觀看時間/)
      expect(sent(api, 'DELETE', PLAYED(BRAVO.jellyfin_item_id))).toHaveLength(0)

      await userEvent.click(within(confirm).getByRole('button', { name: /^標為未看/ }))

      expect(await within(bravo).findByText('剩 2 集沒看')).toBeVisible()
      expect(within(bravo).queryByText('已看')).not.toBeInTheDocument()
      expect(sent(api, 'DELETE', PLAYED(BRAVO.jellyfin_item_id))).toHaveLength(1)
    })

    it('鍵盤做得完：Enter 打開確認、Esc 收起並回到那一顆鍵', async () => {
      const api = watching({
        [`DELETE ${PLAYED(GOLF.jellyfin_item_id)}`]: { body: UNWATCHED },
      })
      renderApp(`/library/${TV}`)
      const golf = await findTile('Golf Movie')
      const unmark = within(golf).getByRole('button', { name: /^標為未看/ })

      unmark.focus()
      await userEvent.keyboard('{Enter}')
      expect(within(golf).getByRole('group')).toHaveFocus()
      await userEvent.keyboard('{Escape}')
      expect(within(golf).getByRole('button', { name: /^標為未看/ })).toHaveFocus()

      await userEvent.keyboard('{Enter}')
      await userEvent.tab()
      await userEvent.keyboard('{Enter}')

      await waitFor(() => expect(within(golf).queryByText('已看')).not.toBeInTheDocument())
      expect(sent(api, 'DELETE', PLAYED(GOLF.jellyfin_item_id))).toHaveLength(1)
      // 送出之後焦點回到同一顆鍵（現在是「標為已看」），不掉回頁首（playwright 實跑抓到）。
      expect(within(golf).getByRole('button', { name: /^標為已看/ })).toHaveFocus()
    })

    it('寫不進去時就在那一格說原因，狀態不變', async () => {
      watching({
        [`POST ${PLAYED(FOXTROT.jellyfin_item_id)}`]: {
          status: 404,
          body: { detail: { reason: 'item_not_visible', detail: 'no such item' } },
        },
      })
      renderApp(`/library/${TV}`)
      const foxtrot = await findTile('Foxtrot Movie')

      await userEvent.click(within(foxtrot).getByRole('button', { name: /^標為已看/ }))

      expect(await within(foxtrot).findByRole('alert')).toHaveTextContent(
        '你在 Jellyfin 看不到這部作品，沒有寫入。',
      )
      expect(within(foxtrot).getByRole('button', { name: /^標為已看/ })).toBeVisible()
      expect(within(foxtrot).queryByText('已看')).not.toBeInTheDocument()
    })

    it('Jellyfin 問不到時說下一步並貼服務原文', async () => {
      watching({
        [`DELETE ${PLAYED(GOLF.jellyfin_item_id)}`]: {
          status: 503,
          body: {
            detail: {
              reason: 'jellyfin_unreachable',
              detail: 'DELETE /UserPlayedItems: connection refused',
            },
          },
        },
      })
      renderApp(`/library/${TV}`)
      const golf = await findTile('Golf Movie')

      await userEvent.click(within(golf).getByRole('button', { name: /^標為未看/ }))
      await userEvent.click(
        within(within(golf).getByRole('group')).getByRole('button', { name: /^標為未看/ }),
      )

      expect(await within(golf).findByRole('alert')).toHaveTextContent(/問不到 Jellyfin.*健康頁/)
      expect(within(golf).getByText('DELETE /UserPlayedItems: connection refused')).toBeVisible()
      expect(within(golf).getByText('已看')).toBeVisible()
    })

    it('帳號在 Jellyfin 被停用時，標記那一下就把人送回登入頁', async () => {
      const account = session({ name: 'deckhand', role: 'user' })
      stubApi({
        'GET /api/health': { body: HEALTHY },
        'GET /api/auth/me': account.me,
        'GET /api/inventory': { body: LIBRARIES },
        [`GET /api/inventory/${TV}`]: { body: wall({ titles: [FOXTROT] }) },
        [`POST ${PLAYED(FOXTROT.jellyfin_item_id)}`]: () => {
          account.signOut()
          return { status: 401, body: { detail: { reason: 'account_disabled', detail: '' } } }
        },
      })
      const { router } = renderApp(`/library/${TV}`)

      await userEvent.click(
        within(await findTile('Foxtrot Movie')).getByRole('button', { name: /^標為已看/ }),
      )

      await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
      expect(router.state.location.search).toMatchObject({ expired: true })
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
      // 海報也跟著換（TMDB 的海報分語言，票 11）。
      expect(within(spy).getByRole('presentation', { hidden: true })).toHaveAttribute(
        'src',
        'https://image.tmdb.org/t/p/w342/spy-en.jpg',
      )
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

      expect(within(pager).getByText('1–50 / 250')).toBeVisible()
      expect(within(pager).getByText('第 1–50 部，共 250 部')).toHaveAttribute(
        'aria-live',
        'polite',
      )
      expect(within(pager).getByRole('link', { name: '下一頁' })).toHaveAttribute(
        'href',
        `/library/${TV}?page=2`,
      )
      expect(within(pager).getByText('上一頁')).toHaveAttribute('aria-disabled', 'true')
    })

    it('牆上下兩組分頁是兩個名字不同的 landmark（票 13）', async () => {
      render({ [`GET /api/inventory/${TV}`]: { body: big(1) } })
      renderApp(`/library/${TV}`)

      await screen.findByRole('heading', { name: 'Show on page 1' })

      expect(
        screen.getAllByRole('navigation').map((nav) => nav.getAttribute('aria-label')),
      ).toEqual(['主要導覽', '媒體庫', '篩選', '分頁', '牆底的分頁'])
    })

    it('換頁向後端要那一頁，最後一頁的下一頁按不了', async () => {
      const api = render({
        [`GET /api/inventory/${TV}`]: { body: big(1) },
        [`GET /api/inventory/${TV}?page=5`]: { body: big(5) },
      })
      renderApp(`/library/${TV}?page=5`)

      expect(await screen.findByRole('heading', { name: 'Show on page 5' })).toBeVisible()
      const pager = screen.getAllByRole('navigation', { name: '分頁' })[0]!

      expect(within(pager).getByText('201–250 / 250')).toBeVisible()
      expect(within(pager).getByRole('link', { name: '上一頁' })).toHaveAttribute(
        'href',
        `/library/${TV}?page=4`,
      )
      expect(within(pager).getByText('下一頁')).toHaveAttribute('aria-disabled', 'true')
      expect(api.mock.calls.map(([input]) => String(input))).toContain(
        `/api/inventory/${TV}?page=5`,
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

    it('選著的篩選是「當前的一個選項」而不是另一頁：不是連結，也不掛 aria-current="page"（票 13）', async () => {
      render()
      renderApp(`/library/${TV}?filter=review`)

      const filters = within(await screen.findByRole('navigation', { name: '篩選' }))
      await screen.findByRole('heading', { name: /SPY×FAMILY/ })

      expect(filters.getByText('待審 1')).toHaveAttribute('aria-current', 'true')
      expect(filters.queryByRole('link', { name: '待審 1' })).not.toBeInTheDocument()
      expect(filters.getByRole('link', { name: '全部' })).not.toHaveAttribute('aria-current')
      expect(filters.getByRole('link', { name: '對不到 1' })).not.toHaveAttribute('aria-current')
      // 整頁只剩切換列上那一個「當前頁」。
      expect(
        [...document.querySelectorAll('[aria-current="page"]')].map((node) => node.textContent),
      ).toEqual(['媒體庫', 'TV'])
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

    it('「對不到」也看得到已經在 Jellyfin 裡的作品', async () => {
      const flagged = { ...BEAR, tracking: tracking({ has_unmatched: true }) }
      render({ [`GET /api/inventory/${TV}`]: { body: wall({ tracked: [flagged, FRIEREN] }) } })
      renderApp(`/library/${TV}?filter=unmatched`)

      // zh-Hant 的文案是「對不到」，不是名詞表裡的 `Unmatched`（票 11，使用者拍板）。
      expect(await screen.findByText('對不到 1')).toHaveAttribute('aria-current', 'true')
      expect(screen.queryByRole('link', { name: /Unmatched/ })).not.toBeInTheDocument()
      expect(await screen.findByRole('heading', { name: 'The Bear' })).toBeVisible()
      expect(screen.queryByRole('heading', { name: /葬送的芙莉蓮/ })).not.toBeInTheDocument()
    })

    it('網址上不認得的篩選值當成沒有篩選，不落進 Unmatched', async () => {
      // 三顆篩選鍵都不會被標成當前，畫面卻只剩 Berth 經手的那幾部——使用者看到的是一份他沒有要的清單。
      const flagged = { ...BEAR, tracking: tracking({ has_unmatched: true }) }
      render({ [`GET /api/inventory/${TV}`]: { body: wall({ tracked: [flagged, FRIEREN] }) } })
      renderApp(`/library/${TV}?filter=nonsense`)

      // Jellyfin 那一頁照畫（分頁與帶子都在），不是被篩成 Berth 的那一份清單。
      expect(await findTile('Alpha Show')).toBeVisible()
      expect(screen.getByText('1–3 / 3')).toBeVisible()
      expect(screen.queryByText('顯示 1 部作品')).not.toBeInTheDocument()
    })

    it.each([
      ['不認得的篩選', '?filter=nonsense', { filter: undefined }],
      ['不是數字的頁碼', '?page=abc', { page: undefined }],
      ['空的排序', '?sort=', { sort: undefined }],
    ])('路由交給頁面的網址參數擋得住%s（票 13）', async (_, search, expected) => {
      // 根路由不驗網址，子路由拿到的是「根的原樣 + 自己驗過的」合起來：驗不過的那一格不寫回去的話，
      // 原樣的值照樣漏到 `useSearch`（M1.5 票 11 實測 `filter="nonsense"`）。
      render()
      const { router } = renderApp(`/library/${TV}${search}`)
      await findTile('Alpha Show')

      expect(router.state.matches.at(-1)?.search).toMatchObject(expected)
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

  describe('排序與類型、年份（票 06）', () => {
    /** 類型、年份的開關：展開之後的面板標題也叫這個名字。 */
    const findToggle = (label: string) =>
      screen.findByRole('button', { name: new RegExp(`^${label}`) })
    /** 網址上的陣列是 TanStack Router 的 JSON 形狀。 */
    const json = (value: unknown) => encodeURIComponent(JSON.stringify(value))
    const walls = (api: ReturnType<typeof render>) =>
      api.mock.calls
        .map(([input]) => String(input))
        // 牆那一支：類型年份清單與上方兩列（票 07）是另外的端點。
        .filter(
          (url) =>
            url.startsWith(`/api/inventory/${TV}`) &&
            !url.endsWith('/filters') &&
            !url.endsWith('/watching'),
        )

    it('劇集庫與電影庫各有自己的排序選單', async () => {
      render({ [`GET /api/inventory/${MOVIES}`]: { body: wall({ library: LIBRARIES[1] }) } })
      renderApp(`/library/${TV}`)

      const tv = within(await screen.findByLabelText('排序')).getAllByRole('option')
      expect(tv.map((option) => option.textContent)).toEqual([
        '名稱',
        '隨機',
        '社群評分',
        '加入日期',
        '新集加入',
        '最近看過',
        '分級',
        '發行日期',
      ])

      await userEvent.click(screen.getByRole('link', { name: 'Movies' }))
      await waitFor(() =>
        expect(screen.getByRole('option', { name: '播放次數' })).toBeInTheDocument(),
      )
      expect(screen.getByRole('option', { name: '片長' })).toBeInTheDocument()
      expect(screen.queryByRole('option', { name: '新集加入' })).not.toBeInTheDocument()
    })

    it('換排序與方向寫進網址、回到第 1 頁，向後端要照那樣排的牆', async () => {
      const api = render({
        [`GET /api/inventory/${TV}?page=2`]: { body: wall({ page: 2, total: 150 }) },
        [`GET /api/inventory/${TV}?sort=CommunityRating`]: { body: wall() },
        [`GET /api/inventory/${TV}?sort=CommunityRating&order=Descending`]: { body: wall() },
      })
      const { router } = renderApp(`/library/${TV}?page=2`)

      await userEvent.selectOptions(await screen.findByLabelText('排序'), '社群評分')
      await waitFor(() => expect(router.state.location.search).toEqual({ sort: 'CommunityRating' }))
      await userEvent.selectOptions(screen.getByLabelText('排序方向'), '遞減')

      await waitFor(() =>
        expect(router.state.location.search).toEqual({
          sort: 'CommunityRating',
          order: 'Descending',
        }),
      )
      expect(walls(api)).toContain(`/api/inventory/${TV}?sort=CommunityRating&order=Descending`)
    })

    it('類型清單打開才問；勾選可多選、寫進網址、回到第 1 頁，焦點留在那一格', async () => {
      const api = render({
        [`GET /api/inventory/${TV}?page=2`]: { body: wall({ page: 2, total: 150 }) },
        [`GET /api/inventory/${TV}/filters`]: {
          body: { genres: ['Comedy', 'Drama'], years: [2020, 2022] },
        },
        [`GET /api/inventory/${TV}?genres=Drama`]: { body: wall() },
        [`GET /api/inventory/${TV}?genres=Comedy&genres=Drama`]: { body: wall() },
      })
      const { router } = renderApp(`/library/${TV}?page=2`)
      const filterLists = () =>
        api.mock.calls.filter(([input]) => String(input).endsWith('/filters')).length

      const genres = await findToggle('類型')
      expect(filterLists()).toBe(0)
      expect(genres).toHaveAttribute('aria-expanded', 'false')
      await userEvent.click(genres)
      expect(genres).toHaveAttribute('aria-expanded', 'true')
      expect(screen.getByRole('group', { name: '類型' })).toHaveAttribute(
        'id',
        genres.getAttribute('aria-controls'),
      )
      await userEvent.click(await screen.findByRole('checkbox', { name: 'Drama' }))
      await waitFor(() => expect(router.state.location.search).toEqual({ genres: ['Drama'] }))
      await userEvent.click(screen.getByRole('checkbox', { name: 'Comedy' }))

      await waitFor(() =>
        expect(router.state.location.search).toEqual({ genres: ['Comedy', 'Drama'] }),
      )
      expect(screen.getByRole('checkbox', { name: 'Comedy' })).toHaveFocus()
      expect(screen.getByRole('checkbox', { name: 'Drama' })).toBeChecked()
      expect(walls(api)).toContain(`/api/inventory/${TV}?genres=Comedy&genres=Drama`)
      expect(filterLists()).toBe(1)
    })

    it('年份也是勾選，取消勾選就拿掉', async () => {
      render({
        [`GET /api/inventory/${TV}/filters`]: { body: { genres: [], years: [2020, 2022] } },
        [`GET /api/inventory/${TV}?years=2020&years=2022`]: { body: wall() },
        [`GET /api/inventory/${TV}?years=2022`]: { body: wall() },
      })
      const { router } = renderApp(`/library/${TV}?years=${json([2020, 2022])}`)

      await userEvent.click(await findToggle('年份'))
      await userEvent.click(await screen.findByRole('checkbox', { name: '2020' }))

      await waitFor(() => expect(router.state.location.search).toEqual({ years: [2022] }))
    })

    it('網址上選著、這個媒體庫卻沒有的類型照樣列出來，取消得了', async () => {
      render({
        [`GET /api/inventory/${TV}?genres=Mecha`]: { body: wall() },
        [`GET /api/inventory/${TV}/filters`]: {
          body: { genres: ['Comedy', 'Drama'], years: [] },
        },
      })
      const { router } = renderApp(`/library/${TV}?genres=${json(['Mecha'])}`)

      await userEvent.click(await findToggle('類型'))
      await screen.findByRole('checkbox', { name: 'Drama' })
      const boxes = within(screen.getByRole('group', { name: '類型' })).getAllByRole('checkbox')
      expect(boxes.map((box) => box.closest('div')?.textContent)).toEqual([
        'Comedy',
        'Drama',
        'Mecha',
      ])
      await userEvent.click(screen.getByRole('checkbox', { name: 'Mecha' }))

      await waitFor(() => expect(router.state.location.search).toEqual({}))
    })

    it('重新整理與分享的連結還原得回來：控制項照網址，向後端要同一面牆', async () => {
      const api = render({
        [`GET /api/inventory/${TV}?sort=CommunityRating&order=Descending&genres=Drama&years=2020`]:
          { body: wall() },
      })
      renderApp(
        `/library/${TV}?sort=CommunityRating&order=Descending&genres=${json(['Drama'])}&years=${json([2020])}`,
      )

      expect(await screen.findByLabelText('排序')).toHaveValue('CommunityRating')
      expect(screen.getByLabelText('排序方向')).toHaveValue('Descending')
      expect(await findToggle('類型')).toHaveAccessibleName(/^類型\s*已選 1 個$/)
      await waitFor(() =>
        expect(walls(api)).toEqual([
          `/api/inventory/${TV}?sort=CommunityRating&order=Descending&genres=Drama&years=2020`,
        ]),
      )
    })

    it('這個媒體庫的選單上沒有的排序當成預設，不送出去', async () => {
      const api = render()
      renderApp(`/library/${TV}?sort=DatePlayed`)

      expect(await screen.findByLabelText('排序')).toHaveValue('SortName')
      expect(walls(api)).toEqual([`/api/inventory/${TV}`])
    })

    it('分頁鍵與「待審」帶著排序與篩選，按「全部」回到原本排好、篩好的那一頁', async () => {
      const big = wall({ page: 2, total: 250 })
      const api = render({
        [`GET /api/inventory/${TV}?page=2&sort=CommunityRating&genres=Drama`]: { body: big },
      })
      const { router } = renderApp(
        `/library/${TV}?page=2&sort=CommunityRating&genres=${json(['Drama'])}`,
      )

      const pager = (await screen.findAllByRole('navigation', { name: '分頁' }))[0]!
      expect(within(pager).getByRole('link', { name: '下一頁' })).toHaveAttribute(
        'href',
        `/library/${TV}?page=3&sort=CommunityRating&genres=${json(['Drama'])}`,
      )

      await userEvent.click(screen.getByRole('link', { name: '待審 1' }))
      await waitFor(() =>
        expect(router.state.location.search).toEqual({
          page: 2,
          filter: 'review',
          sort: 'CommunityRating',
          genres: ['Drama'],
        }),
      )
      // 待審是 Berth 的清單，Jellyfin 的類型套不上：控制項收起（使用者拍板）。
      expect(screen.queryByLabelText('排序')).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /^類型/ })).not.toBeInTheDocument()

      await userEvent.click(screen.getByRole('link', { name: '全部' }))
      await waitFor(() =>
        expect(router.state.location.search).toEqual({
          page: 2,
          sort: 'CommunityRating',
          genres: ['Drama'],
        }),
      )
      // 待審與全部之間切換不重抓：Berth 的清單跟著那一頁一起到手。
      expect(walls(api)).toEqual([`/api/inventory/${TV}?page=2&sort=CommunityRating&genres=Drama`])
    })

    it('篩類型或年份時「還沒進 Jellyfin」收起；只換排序時照舊', async () => {
      render({
        [`GET /api/inventory/${TV}?genres=Drama`]: { body: wall() },
        [`GET /api/inventory/${TV}?sort=CommunityRating`]: { body: wall() },
      })
      const { router } = renderApp(`/library/${TV}?genres=${json(['Drama'])}`)

      await findTile('Alpha Show')
      expect(screen.queryByRole('region', { name: '還沒進 Jellyfin' })).not.toBeInTheDocument()

      await router.navigate({
        to: '/library/$libraryId',
        params: { libraryId: TV },
        search: { sort: 'CommunityRating' },
      })
      expect(await screen.findByRole('region', { name: '還沒進 Jellyfin' })).toBeVisible()
    })

    it('篩完什麼都沒有時說得出篩了什麼，給一條清掉類型與年份的路（排序留著）', async () => {
      render({
        [`GET /api/inventory/${TV}?sort=CommunityRating&genres=Drama&years=2020`]: {
          body: wall({ total: 0, titles: [] }),
        },
      })
      renderApp(
        `/library/${TV}?sort=CommunityRating&genres=${json(['Drama'])}&years=${json([2020])}`,
      )

      expect(await screen.findByText('這個媒體庫沒有符合篩選的作品。')).toBeVisible()
      expect(screen.getByText('類型：Drama')).toBeVisible()
      expect(screen.getByText('年份：2020')).toBeVisible()
      expect(screen.getByRole('link', { name: '清除類型與年份' })).toHaveAttribute(
        'href',
        `/library/${TV}?sort=CommunityRating`,
      )
      // 空的是篩選的結果，不是媒體庫本身。
      expect(screen.queryByText('「TV」還沒有任何作品。')).not.toBeInTheDocument()
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

  describe('繼續觀看與下一集（票 07）', () => {
    const WATCHING = `/api/inventory/${TV}/watching`
    const EPISODE = 'cd2f059cd4fdef1da23617e86514232e'

    function rows(): StubRoute {
      return {
        body: {
          jellyfin: { public_url: '', url: '', port: 8096 },
          resume: [],
          next_up: [
            {
              item_id: EPISODE,
              kind: 'tv',
              title: 'Alpha Show',
              episode_name: 'The Second One',
              season: 1,
              episode_start: 2,
              episode_end: null,
              year: null,
              progress: null,
              image_url: '',
            },
          ],
        } satisfies Watching,
      }
    }

    function asked(api: ReturnType<typeof render>) {
      return api.mock.calls.filter(([url]) => String(url).endsWith('/watching')).map(([url]) => url)
    }

    it('第 1 頁、沒有篩選時畫這個媒體庫的兩列，在切換列與「還沒進 Jellyfin」之間', async () => {
      const api = render({ [`GET ${WATCHING}`]: rows() })
      renderApp(`/library/${TV}`)

      const next = await screen.findByRole('region', { name: '下一集' })
      await findTile('Alpha Show')

      expect(
        within(next).getByRole('link', { name: /^Alpha Show S01E02 The Second One/ }),
      ).toHaveAttribute('href', `http://localhost:8096/web/#/details?id=${EPISODE}`)
      // 沒有內容的繼續觀看那一列不畫。
      expect(screen.queryByRole('region', { name: '繼續觀看' })).not.toBeInTheDocument()
      const switcher = screen.getByRole('navigation', { name: '媒體庫' })
      expect(switcher.compareDocumentPosition(next) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
      expect(next.compareDocumentPosition(band()) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
      // 問的是這個媒體庫的那一支，不是首頁那一支。
      expect(asked(api)).toEqual([WATCHING])
    })

    it.each([
      [
        '第 2 頁',
        `?page=2`,
        'Alpha Show',
        { [`GET /api/inventory/${TV}?page=2`]: { body: wall({ page: 2, total: 150 }) } },
      ],
      // 待審那一面牆是 Berth 的清單：Alpha Show 不在上面。
      ['待審', `?filter=review`, 'SPY', {}],
      [
        '篩類型',
        `?genres=${encodeURIComponent(JSON.stringify(['Drama']))}`,
        'Alpha Show',
        { [`GET /api/inventory/${TV}?genres=Drama`]: { body: wall() } },
      ],
    ])('%s時不畫、也不問', async (_, search, shown, routes) => {
      const api = render({ [`GET ${WATCHING}`]: rows(), ...routes })
      renderApp(`/library/${TV}${search}`)

      await findTile(shown)

      expect(screen.queryByRole('region', { name: '下一集' })).not.toBeInTheDocument()
      expect(asked(api)).toEqual([])
    })

    it('讀取中照這個媒體庫上一次的形狀佔位，讀到之後換成真的那一列（票 13：CLS）', async () => {
      const key = `berth.watching.skipper.library.${TV}`
      localStorage.setItem(key, JSON.stringify({ resume: 0, nextUp: 1 }))
      let answer: (response: Response) => void = () => {}
      const api = render({ [`GET ${WATCHING}`]: rows() })
      vi.stubGlobal('fetch', (input: RequestInfo | URL, init?: RequestInit) =>
        String(input) === WATCHING
          ? new Promise<Response>((resolve) => (answer = resolve))
          : api(input, init),
      )
      renderApp(`/library/${TV}`)
      await findTile('Alpha Show')

      expect(document.querySelectorAll('[data-placeholder="watching"]')).toHaveLength(1)
      expect(screen.queryByRole('region', { name: '下一集' })).not.toBeInTheDocument()

      answer(new Response(JSON.stringify(rows().body)))

      expect(await screen.findByRole('region', { name: '下一集' })).toBeInTheDocument()
      expect(document.querySelectorAll('[data-placeholder="watching"]')).toHaveLength(0)
      localStorage.clear()
    })

    it('只換排序照樣畫：排序不會讓哪一集不見', async () => {
      render({
        [`GET ${WATCHING}`]: rows(),
        [`GET /api/inventory/${TV}?sort=CommunityRating`]: { body: wall() },
      })
      renderApp(`/library/${TV}?sort=CommunityRating`)

      expect(await screen.findByRole('region', { name: '下一集' })).toBeInTheDocument()
    })

    it('媒體庫不在允許清單上時兩列不畫，由牆說找不到', async () => {
      render({
        [`GET ${WATCHING}`]: {
          status: 404,
          body: { detail: { reason: 'library_not_visible', detail: '' } },
        },
        [`GET /api/inventory/${TV}`]: {
          status: 404,
          body: { detail: { reason: 'library_not_visible', detail: '' } },
        },
      })
      renderApp(`/library/${TV}`)

      expect(await screen.findByText(/找不到這個媒體庫/)).toBeVisible()
      expect(screen.queryByRole('region', { name: '下一集' })).not.toBeInTheDocument()
    })

    it('在牆上標為已看之後兩列不當場重問：它們一換，牆就在指標底下移動', async () => {
      const alpha = jellyfinCard({ watch: { played: false, progress: null, unplayed_episodes: 4 } })
      const api = render({
        [`GET /api/inventory/${TV}`]: { body: wall({ titles: [alpha] }) },
        [`GET ${WATCHING}`]: rows(),
        [`POST /api/jellyfin/items/${alpha.jellyfin_item_id}/played`]: {
          body: { played: true, progress: null, unplayed_episodes: null },
        },
      })
      renderApp(`/library/${TV}`)
      await screen.findByRole('region', { name: '下一集' })
      expect(asked(api)).toHaveLength(1)

      const tileOf = await findTile('Alpha Show')
      await userEvent.click(within(tileOf).getByRole('button', { name: /^標為已看/ }))
      await userEvent.click(
        within(within(tileOf).getByRole('group')).getByRole('button', { name: /^標為已看/ }),
      )

      expect(await within(await findTile('Alpha Show')).findByText('已看')).toBeVisible()
      expect(asked(api)).toHaveLength(1)
    })
  })
})
