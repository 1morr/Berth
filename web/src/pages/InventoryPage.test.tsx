import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Inventory, InventoryCard, InventoryLibrary } from '../api/inventory'
import type { PlanReviewRow, ReviewQueue, UnmatchedReviewRow } from '../api/review'
import type { Watching, WatchingCard } from '../api/watching'
import { HEALTHY, session, stubApi, type StubRoute } from '../test/fetch'
import { expectCurrentByStateOnly } from '../test/navState'
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
  tracking: tracking({ status: 'review', imported: 0, aired: 37 }),
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
 * 牆上的一格：以標題找到它所在的那一格。繼續觀看與下一集的格子也有 `h3`（票 13），但它們不是 `article`，所以只認
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

    // 票 13：當前那一格只差在狀態屬性上，不另外疊一組 class。
    expectCurrentByStateOnly(current, within(switcher).getByRole('link', { name: 'Movies' }))
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

    it('牆是一份清單，每一格一個 h3 標題（票 13：與探索牆、繼續觀看與下一集同一種語意）', async () => {
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

  describe('待審 / 對不到（M2 票 14）', () => {
    /** 審核佇列在這個媒體庫上的那兩類（`GET /review?library=`）：一件待審核的計劃、兩個對不到的檔案。 */
    const LIBRARY_QUEUE = `GET /api/review?library=${TV}`
    const HELD: PlanReviewRow = {
      kind: 'plan',
      ref: 11,
      reason: { code: 'low_confidence', params: { files: 0, low: 2, medium: 0 } },
      actions: ['approve', 'reject'],
      at: '2026-09-23T04:00:00Z',
      media_id: 'tv:120089',
      title: 'SPY×FAMILY 間諜家家酒',
      title_en: 'SPY x FAMILY',
      job_hash: '4bd0f6ef1d3b1e3cbb1e1b6b6c2a9c7d8e5f0a1b',
      job_name: '[ANi] SPY×FAMILY - 05 [1080P][WEB-DL][AAC AVC][CHT]',
      summary: {
        files: 0,
        high: 0,
        medium: 0,
        low: 2,
        actions: { review: 2 },
        review_reason: 'low_confidence',
      },
    }
    function stray(ref: number, name: string): UnmatchedReviewRow {
      return {
        kind: 'unmatched',
        ref,
        reason: { code: 'left_in_place', params: {} },
        actions: ['import', 'extra', 'skip'],
        at: '2026-09-22T04:00:00Z',
        media_id: 'tv:136315',
        media_kind: 'tv',
        title: 'The Bear',
        title_en: 'The Bear',
        job_hash: 'b'.repeat(40),
        job_name: 'The.Bear.S03.1080p.WEB',
        path: `/data/torrent/complete/tv/The.Bear.S03.1080p.WEB/${name}`,
        file_kind: 'video',
        reasons: [{ code: 'own_numbered_special', params: {} }],
      }
    }
    const QUEUE: ReviewQueue = {
      rows: [HELD, stray(21, 'The.Bear.Special.mkv'), stray(22, 'The.Bear.Extra.mkv')],
      total: 3,
      queue_total: 7,
      issues_open: 0,
    }
    const COUNTED = wall({ review: 1, unmatched: 2 })

    function renderQueue(
      routes: Record<string, StubRoute | (() => StubRoute)> = {},
      role: 'admin' | 'user' = 'admin',
    ) {
      return render(
        {
          [`GET /api/inventory/${TV}`]: { body: COUNTED },
          [LIBRARY_QUEUE]: { body: QUEUE },
          ...routes,
        },
        role,
      )
    }

    it('「待審」是一列一件事的清單，不是牆：每一列說得出為什麼在這，帶子與分頁收起來', async () => {
      renderQueue()
      const { router } = renderApp(`/library/${TV}`)

      await userEvent.click(await screen.findByRole('link', { name: '待審 1' }))

      await waitFor(() => expect(router.state.location.search).toEqual({ filter: 'review' }))
      const list = await screen.findByRole('list', { name: '待審' })
      const [row] = within(list).getAllByRole('article')
      expect(within(list).getAllByRole('article')).toHaveLength(1)
      expect(within(row!).getByText('待審核')).toBeVisible()
      expect(within(row!).getByRole('heading', { name: 'SPY×FAMILY 間諜家家酒' })).toBeVisible()
      expect(within(row!).getByText(/有檔案的季集要你確認/)).toBeVisible()
      // 牆上的貨櫃一格都不剩：Jellyfin 那一頁、還沒進 Jellyfin 那一條與分頁都收起來。
      expect(screen.queryByRole('heading', { name: /Alpha Show/ })).not.toBeInTheDocument()
      expect(screen.queryByRole('region', { name: '還沒進 Jellyfin' })).not.toBeInTheDocument()
      expect(screen.queryByRole('navigation', { name: '分頁' })).not.toBeInTheDocument()
      expect(screen.getByText('顯示 1 件')).toHaveAttribute('aria-live', 'polite')
    })

    it('「對不到」一個檔案一列，就地指派；清單下方連到審核佇列裡其餘的件數', async () => {
      renderQueue()
      renderApp(`/library/${TV}?filter=unmatched`)

      const list = await screen.findByRole('list', { name: '對不到' })
      const rows = within(list).getAllByRole('article')
      expect(rows).toHaveLength(2)
      expect(within(rows[0]!).getByRole('heading')).toHaveTextContent(
        'The Bear · The.Bear.Special.mkv',
      )
      expect(within(rows[0]!).getByText(/對不到任何一集，留在 complete 原位/)).toBeVisible()
      // 表單就是這一列的工作：與 `/review` 同一個列元件，就地按。
      expect(within(rows[0]!).getByRole('combobox', { name: '改成' })).toBeVisible()
      expect(screen.getByRole('link', { name: '審核佇列裡還有 5 件' })).toHaveAttribute(
        'href',
        '/review',
      )
    })

    it('選著的篩選是「當前的一個選項」而不是另一頁：不是連結，也不掛 aria-current="page"（票 13）', async () => {
      renderQueue()
      renderApp(`/library/${TV}?filter=review`)

      const filters = within(await screen.findByRole('navigation', { name: '篩選' }))
      await screen.findByRole('list', { name: '待審' })

      expect(filters.getByText('待審 1')).toHaveAttribute('aria-current', 'true')
      expect(filters.queryByRole('link', { name: '待審 1' })).not.toBeInTheDocument()
      expect(filters.getByRole('link', { name: '全部' })).not.toHaveAttribute('aria-current')
      // zh-Hant 的文案是「對不到」，不是名詞表裡的 `Unmatched`（票 11，使用者拍板）。
      expect(filters.getByRole('link', { name: '對不到 2' })).not.toHaveAttribute('aria-current')
      expect(
        [...document.querySelectorAll('[aria-current="page"]')].map((node) => node.textContent),
      ).toEqual(['媒體庫', 'TV'])
    })

    it('在第 2 頁換篩選不重抓牆，按回「全部」回到第 2 頁', async () => {
      const api = renderQueue({
        [`GET /api/inventory/${TV}?page=2`]: {
          body: wall({ page: 2, total: 150, review: 1, unmatched: 2 }),
        },
      })
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
      await screen.findByRole('list', { name: '待審' })
      await userEvent.click(screen.getByRole('link', { name: '全部' }))

      await waitFor(() => expect(router.state.location.search).toEqual({ page: 2 }))
      expect(walls()).toBe(fetched)
    })

    it('按完一列，那一列消失，篩選鍵上的數字跟著重問', async () => {
      let decided = false
      renderQueue({
        [`GET /api/inventory/${TV}`]: () => ({
          body: decided ? wall({ review: 0, unmatched: 2 }) : COUNTED,
        }),
        [LIBRARY_QUEUE]: () => ({
          body: decided ? { ...QUEUE, rows: QUEUE.rows.slice(1) } : QUEUE,
        }),
        'POST /api/plans/11/approve': () => {
          decided = true
          return { body: {} }
        },
      })
      renderApp(`/library/${TV}?filter=review`)
      const list = await screen.findByRole('list', { name: '待審' })

      await userEvent.click(within(list).getByRole('button', { name: '核准並入庫' }))

      const empty = await screen.findByText('這個媒體庫沒有待審核的下載。')
      expect(empty).toBeVisible()
      expect(await screen.findByText('待審 0')).toHaveAttribute('aria-current', 'true')
      // 按下去的那一顆跟著那一列走了：焦點落在清單那一層，不掉回頁首（M2 票 16，同 `/review`）。
      await waitFor(() => expect(empty.closest('[tabindex="-1"]')).toHaveFocus())
    })

    it('一般使用者沒有這兩個篩選：那是管理員的工作佇列，網址上帶著也照畫整面牆', async () => {
      const api = renderQueue({}, 'user')
      renderApp(`/library/${TV}?filter=review`)

      expect(await findTile('Alpha Show')).toBeVisible()
      expect(screen.queryByRole('navigation', { name: '篩選' })).not.toBeInTheDocument()
      expect(screen.queryByRole('link', { name: /待審/ })).not.toBeInTheDocument()
      expect(api.mock.calls.some(([input]) => String(input).startsWith('/api/review'))).toBe(false)
    })

    it('網址上不認得的篩選值當成沒有篩選，不落進對不到', async () => {
      renderQueue()
      renderApp(`/library/${TV}?filter=nonsense`)

      // Jellyfin 那一頁照畫（分頁與帶子都在），不是審核佇列那一份清單。
      expect(await findTile('Alpha Show')).toBeVisible()
      expect(screen.getByText('1–3 / 3')).toBeVisible()
      expect(screen.queryByRole('list', { name: '對不到' })).not.toBeInTheDocument()
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

    it('清單是空的時說這個媒體庫沒有這一種事，給一條回到全部的路', async () => {
      renderQueue({ [LIBRARY_QUEUE]: { body: { rows: [], total: 0, queue_total: 4 } } })
      renderApp(`/library/${TV}?filter=unmatched`)

      expect(await screen.findByText('這個媒體庫沒有對不到的檔案。')).toBeVisible()
      expect(screen.getByRole('link', { name: '顯示全部' })).toHaveAttribute(
        'href',
        `/library/${TV}`,
      )
      expect(screen.getByRole('link', { name: '審核佇列裡還有 4 件' })).toBeVisible()
    })

    it('超過上限時說只列出最舊的幾件（同 `/review`）', async () => {
      renderQueue({
        [LIBRARY_QUEUE]: { body: { rows: QUEUE.rows, total: 250, queue_total: 260 } },
      })
      renderApp(`/library/${TV}?filter=unmatched`)

      expect(await screen.findByText('只列出最舊的 3 件，共 250 件。')).toBeVisible()
    })

    it('讀不到審核佇列時說一句，篩選列照樣在', async () => {
      renderQueue({ [LIBRARY_QUEUE]: { status: 500, body: {} } })
      renderApp(`/library/${TV}?filter=review`)

      expect(await screen.findByText(/讀不到審核佇列/)).toBeVisible()
      expect(screen.getByRole('link', { name: '全部' })).toBeVisible()
    })
  })

  it('頁尾有 TMDB 的標誌與聲明，標誌的替代文字走 i18n（票 13）', async () => {
    render()
    renderApp(`/library/${TV}`)

    expect(await screen.findByRole('img', { name: 'TMDB 標誌' })).toBeInTheDocument()
    expect(screen.getByText(/未經 TMDB 認可/)).toBeVisible()
  })

  describe('排序與類型、年份（票 06）', () => {
    it('方向那一個下拉有看得見的標籤，不是只有 aria-label（票 13）', async () => {
      render()
      renderApp(`/library/${TV}`)
      await findTile('Alpha Show')

      const order = screen.getByRole<HTMLSelectElement>('combobox', { name: '方向' })

      expect(order).not.toHaveAttribute('aria-label')
      expect(order.labels?.[0]).toHaveTextContent('方向')
      expect(order.labels?.[0]).toBeVisible()
    })

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
      await userEvent.selectOptions(screen.getByRole('combobox', { name: '方向' }), '遞減')

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
      expect(screen.getByRole('combobox', { name: '方向' })).toHaveValue('Descending')
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

  describe('按名字找（M2 票 14）', () => {
    const BEAR_ONLY = wall({ titles: [BEAR], total: 1 })
    /** 牆那一支每一次問的網址（類型年份清單與上方兩列是另外的端點）。 */
    const asked = (api: ReturnType<typeof render>) =>
      api.mock.calls
        .map(([input]) => String(input))
        .filter((url) => url.startsWith(`/api/inventory/${TV}`) && !url.includes('/watching'))

    it('打字之後寫進網址、回到第 1 頁，向後端要那一面牆；打字途中不是每個字都問一次', async () => {
      const api = render({
        [`GET /api/inventory/${TV}?page=2`]: { body: wall({ page: 2, total: 150 }) },
        [`GET /api/inventory/${TV}?q=bear`]: { body: BEAR_ONLY },
      })
      const { router } = renderApp(`/library/${TV}?page=2`)
      await findTile('Alpha Show')
      const entries = router.history.length

      await userEvent.type(screen.getByRole('searchbox', { name: '按名字找' }), 'bear')

      await waitFor(() => expect(router.state.location.search).toEqual({ q: 'bear' }))
      expect(await findTile('The Bear')).toBeVisible()
      expect(screen.queryByRole('heading', { name: /Alpha Show/ })).not.toBeInTheDocument()
      expect(asked(api).filter((url) => url.includes('q='))).toEqual([
        `/api/inventory/${TV}?q=bear`,
      ])
      // 焦點留在搜尋框裡：換牆的時候它沒有被卸掉。
      expect(screen.getByRole('searchbox', { name: '按名字找' })).toHaveFocus()
      // 換的是這一筆歷史紀錄：上一頁回到搜尋之前，不是每一段打到一半的字。
      expect(router.history.length).toBe(entries)
    })

    it('停在空白上時不吃掉那個空白：網址是去掉空白的名字，框裡的字照打的樣子', async () => {
      render({
        [`GET /api/inventory/${TV}?q=the`]: { body: wall() },
        [`GET /api/inventory/${TV}?q=the+bear`]: { body: BEAR_ONLY },
      })
      const { router } = renderApp(`/library/${TV}`)
      await findTile('Alpha Show')
      const box = screen.getByRole('searchbox', { name: '按名字找' })

      await userEvent.type(box, 'the ')
      await waitFor(() => expect(router.state.location.search).toEqual({ q: 'the' }))
      await userEvent.type(box, 'bear')

      expect(box).toHaveValue('the bear')
      await waitFor(() => expect(router.state.location.search).toEqual({ q: 'the bear' }))
    })

    it('重新整理與分享的連結還原得回來：搜尋框照網址，向後端要同一面牆', async () => {
      const api = render({ [`GET /api/inventory/${TV}?q=bear`]: { body: BEAR_ONLY } })
      renderApp(`/library/${TV}?q=bear`)

      expect(await screen.findByRole('searchbox', { name: '按名字找' })).toHaveValue('bear')
      expect(await findTile('The Bear')).toBeVisible()
      expect(asked(api)).toEqual([`/api/inventory/${TV}?q=bear`])
    })

    it('搜尋時「還沒進 Jellyfin」那一條收起：它們不在 Jellyfin 的搜尋結果裡', async () => {
      render({ [`GET /api/inventory/${TV}?q=bear`]: { body: BEAR_ONLY } })
      renderApp(`/library/${TV}?q=bear`)

      await findTile('The Bear')

      expect(screen.queryByRole('region', { name: '還沒進 Jellyfin' })).not.toBeInTheDocument()
    })

    it('分頁鍵帶著搜尋；清空搜尋框就回到整面牆', async () => {
      render({
        [`GET /api/inventory/${TV}?q=show`]: { body: wall({ total: 120 }) },
      })
      const { router } = renderApp(`/library/${TV}?q=show`)
      await findTile('Alpha Show')

      expect(
        within(screen.getByRole('navigation', { name: '分頁' })).getByRole('link', {
          name: '下一頁',
        }),
      ).toHaveAttribute('href', `/library/${TV}?page=2&q=show`)
      await userEvent.clear(screen.getByRole('searchbox', { name: '按名字找' }))

      await waitFor(() => expect(router.state.location.search).toEqual({}))
    })

    it('搜不到時說搜了什麼，給一條清掉搜尋的路（類型與排序留著）', async () => {
      render({
        [`GET /api/inventory/${TV}?sort=CommunityRating&genres=Drama&q=zzz`]: {
          body: wall({ total: 0, titles: [] }),
        },
      })
      const genres = encodeURIComponent(JSON.stringify(['Drama']))
      renderApp(`/library/${TV}?sort=CommunityRating&genres=${genres}&q=zzz`)

      expect(await screen.findByText('這個媒體庫沒有符合篩選的作品。')).toBeVisible()
      expect(screen.getByText('名字含「zzz」')).toBeVisible()
      expect(screen.getByText('類型：Drama')).toBeVisible()
      expect(screen.getByRole('link', { name: '清除搜尋' })).toHaveAttribute(
        'href',
        `/library/${TV}?sort=CommunityRating&genres=${genres}`,
      )
      expect(screen.getByRole('link', { name: '清除類型與年份' })).toHaveAttribute(
        'href',
        `/library/${TV}?sort=CommunityRating&q=zzz`,
      )
    })

    it('只打了空白不算在找', async () => {
      const api = render()
      const { router } = renderApp(`/library/${TV}`)
      await findTile('Alpha Show')

      await userEvent.type(screen.getByRole('searchbox', { name: '按名字找' }), '   ')
      await new Promise((resolve) => setTimeout(resolve, 600))

      expect(router.state.location.search).toEqual({})
      expect(asked(api)).toEqual([`/api/inventory/${TV}`])
    })

    it('「待審」「對不到」是審核佇列的清單，沒有搜尋框', async () => {
      render({
        [`GET /api/review?library=${TV}`]: { body: { rows: [], total: 0, queue_total: 0 } },
      })
      renderApp(`/library/${TV}?filter=review`)

      await screen.findByText('這個媒體庫沒有待審核的下載。')

      expect(screen.queryByRole('searchbox')).not.toBeInTheDocument()
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

    /** 媒體庫頁的兩列收成的那一顆（M2 票 14）。 */
    const findCarryOn = () => screen.findByRole('button', { name: /^接著看/ })

    it('第 1 頁、沒有篩選時收成「接著看 N 項」一行，在切換列與「還沒進 Jellyfin」之間，就地展開兩列', async () => {
      const api = render({ [`GET ${WATCHING}`]: rows() })
      renderApp(`/library/${TV}`)

      const toggle = await findCarryOn()
      await findTile('Alpha Show')

      // 收著的時候只有這一行：牆的第一格不必等使用者捲過兩列（M1.5 critique P1）。
      expect(toggle).toHaveAccessibleName('接著看 1 項')
      expect(toggle).toHaveAttribute('aria-expanded', 'false')
      expect(screen.queryByRole('region', { name: '下一集' })).not.toBeInTheDocument()
      const switcher = screen.getByRole('navigation', { name: '媒體庫' })
      expect(
        switcher.compareDocumentPosition(toggle) & Node.DOCUMENT_POSITION_FOLLOWING,
      ).toBeTruthy()
      expect(toggle.compareDocumentPosition(band()) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()

      await userEvent.click(toggle)

      expect(toggle).toHaveAttribute('aria-expanded', 'true')
      const next = screen.getByRole('region', { name: '下一集' })
      expect(toggle).toHaveAttribute('aria-controls', next.parentElement?.id)
      expect(
        within(next).getByRole('link', { name: /^Alpha Show S01E02 The Second One/ }),
      ).toHaveAttribute('href', `http://localhost:8096/web/#/details?id=${EPISODE}`)
      // 沒有內容的繼續觀看那一列不畫。
      expect(screen.queryByRole('region', { name: '繼續觀看' })).not.toBeInTheDocument()
      expect(next.compareDocumentPosition(band()) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
      // 問的是這個媒體庫的那一支，不是首頁那一支；展開不重問。
      expect(asked(api)).toEqual([WATCHING])

      await userEvent.click(toggle)
      expect(screen.queryByRole('region', { name: '下一集' })).not.toBeInTheDocument()
    })

    it('兩列都空時連那一行都不畫', async () => {
      const api = render({
        [`GET ${WATCHING}`]: {
          body: { ...(rows().body as Watching), next_up: [] } satisfies Watching,
        },
      })
      renderApp(`/library/${TV}`)
      await findTile('Alpha Show')
      await waitFor(() => expect(asked(api)).toEqual([WATCHING]))
      await new Promise((resolve) => setTimeout(resolve, 0))

      expect(screen.queryByRole('button', { name: /^接著看/ })).not.toBeInTheDocument()
    })

    it.each([
      [
        '第 2 頁',
        `?page=2`,
        'Alpha Show',
        { [`GET /api/inventory/${TV}?page=2`]: { body: wall({ page: 2, total: 150 }) } },
      ],
      [
        '篩類型',
        `?genres=${encodeURIComponent(JSON.stringify(['Drama']))}`,
        'Alpha Show',
        { [`GET /api/inventory/${TV}?genres=Drama`]: { body: wall() } },
      ],
      // 按名字找也讓作品不見（M2 票 14）：那兩列不照名字篩，照畫會是另一份清單。
      [
        '按名字找',
        `?q=alpha`,
        'Alpha Show',
        { [`GET /api/inventory/${TV}?q=alpha`]: { body: wall() } },
      ],
    ])('%s時不畫、也不問', async (_, search, shown, routes) => {
      const api = render({ [`GET ${WATCHING}`]: rows(), ...routes })
      renderApp(`/library/${TV}${search}`)

      await findTile(shown)

      expect(screen.queryByRole('button', { name: /^接著看/ })).not.toBeInTheDocument()
      expect(asked(api)).toEqual([])
    })

    it('待審時不畫、也不問：那是審核佇列的清單', async () => {
      const api = render({
        [`GET ${WATCHING}`]: rows(),
        [`GET /api/review?library=${TV}`]: { body: { rows: [], total: 0, queue_total: 0 } },
      })
      renderApp(`/library/${TV}?filter=review`)

      await screen.findByText('這個媒體庫沒有待審核的下載。')

      expect(screen.queryByRole('button', { name: /^接著看/ })).not.toBeInTheDocument()
      expect(asked(api)).toEqual([])
    })

    it('讀取中照這個媒體庫上一次的形狀佔一行，讀到之後換成真的那一顆（票 13：CLS）', async () => {
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
      expect(screen.queryByRole('button', { name: /^接著看/ })).not.toBeInTheDocument()

      answer(new Response(JSON.stringify(rows().body)))

      expect(await findCarryOn()).toBeInTheDocument()
      expect(document.querySelectorAll('[data-placeholder="watching"]')).toHaveLength(0)
      localStorage.clear()
    })

    it('第 2 頁說得出兩列去了哪裡、給一條回第 1 頁的路；上一次沒東西可接著看就不說（票 13）', async () => {
      const key = `berth.watching.skipper.library.${TV}`
      const second = {
        [`GET /api/inventory/${TV}?page=2&sort=CommunityRating`]: {
          body: wall({ page: 2, total: 150 }),
        },
      }
      localStorage.setItem(key, JSON.stringify({ resume: 0, nextUp: 1 }))
      render({ [`GET ${WATCHING}`]: rows(), ...second })
      const { unmount } = renderApp(`/library/${TV}?page=2&sort=CommunityRating`)
      await findTile('Alpha Show')

      expect(screen.getByText('繼續觀看與下一集只列在第 1 頁、沒有篩選的時候。')).toBeVisible()
      // 回到會畫兩列的那一頁：頁碼與篩選拿掉，排序留著。
      expect(screen.getByRole('link', { name: '到第 1 頁看' })).toHaveAttribute(
        'href',
        `/library/${TV}?sort=CommunityRating`,
      )
      unmount()

      localStorage.setItem(key, JSON.stringify({ resume: 0, nextUp: 0 }))
      renderApp(`/library/${TV}?page=2&sort=CommunityRating`)
      await findTile('Alpha Show')
      expect(screen.queryByText(/只列在第 1 頁/)).not.toBeInTheDocument()
      localStorage.clear()
    })

    it('只換排序照樣畫：排序不會讓哪一集不見', async () => {
      render({
        [`GET ${WATCHING}`]: rows(),
        [`GET /api/inventory/${TV}?sort=CommunityRating`]: { body: wall() },
      })
      renderApp(`/library/${TV}?sort=CommunityRating`)

      expect(await findCarryOn()).toBeInTheDocument()
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
      expect(screen.queryByRole('button', { name: /^接著看/ })).not.toBeInTheDocument()
    })

    /**
     * 展開之後那兩列本身（M1.5 票 07）。原本在首頁上測，探索頁只放 TMDB 牆之後（M3 票 06）搬到這裡：
     * 這一頁是那兩列唯一的家。
     */
    describe('展開之後的兩列', () => {
      function card(overrides: Partial<WatchingCard> = {}): WatchingCard {
        return {
          item_id: '99701a68c9a746b2f3a2d31d0b6c49f2',
          kind: 'tv',
          title: '葬送的芙莉蓮',
          episode_name: '冒險結束',
          season: 1,
          episode_start: 5,
          episode_end: null,
          year: null,
          progress: 42,
          image_url:
            '/api/jellyfin/items/02c06be72a8c11102b98e17665c9fef2/images/Backdrop?size=wide&tag=609790cd6a30bf8277a008ba2fecb77f',
          ...overrides,
        }
      }

      const FILM = card({
        item_id: 'aaad8034da2f8c4db82f7aa3e26a4e3e',
        kind: 'movie',
        title: 'Oppenheimer',
        episode_name: '',
        season: null,
        episode_start: null,
        year: 2023,
        progress: 18,
        image_url: '',
      })

      function watching(overrides: Partial<Watching> = {}): StubRoute {
        return {
          body: {
            // 套件內的 Jellyfin：主機名由瀏覽器補上（jsdom 是 `http://localhost`）。
            jellyfin: { public_url: '', url: '', port: 8096 },
            resume: [card(), FILM],
            next_up: [card({ item_id: 'cd2f059cd4fdef1da23617e86514232e', progress: null })],
            ...overrides,
          } satisfies Watching,
        }
      }

      async function expanded(rows: StubRoute) {
        render({ [`GET ${WATCHING}`]: rows })
        renderApp(`/library/${TV}`)
        await userEvent.click(await findCarryOn())
      }

      it('卡片說得出作品、季集、集名與看到哪，點下去開 Jellyfin 的那一集', async () => {
        await expanded(watching())

        const resume = screen.getByRole('region', { name: '繼續觀看' })
        const next = screen.getByRole('region', { name: '下一集' })
        const episode = within(resume).getByRole('link', { name: /葬送的芙莉蓮/ })
        // 名字從作品名念起（票 13），看到幾 % 是描述。
        expect(episode).toHaveAccessibleName(/^葬送的芙莉蓮 S01E05 冒險結束.*（開新分頁）$/)
        expect(episode).toHaveAccessibleDescription('看到 42%')
        expect(episode).toHaveAttribute(
          'href',
          'http://localhost:8096/web/#/details?id=99701a68c9a746b2f3a2d31d0b6c49f2',
        )
        expect(episode).toHaveAttribute('target', '_blank')
        expect(episode.querySelector('img')).toHaveAttribute('src', card().image_url)
        // 下一集那一列沒有看到幾 %。
        expect(within(next).getByRole('link', { name: /葬送的芙莉蓮/ })).not.toHaveTextContent(
          /看到/,
        )
      })

      it('電影說類型代號與年份，沒有橫圖時同一塊印「無圖」', async () => {
        await expanded(watching())

        const film = within(screen.getByRole('region', { name: '繼續觀看' })).getByRole('link', {
          name: /Oppenheimer/,
        })

        expect(film).toHaveTextContent('MOVIE')
        expect(film).toHaveTextContent('2023')
        expect(film).toHaveTextContent('看到 18%')
        expect(within(film).getByText('無圖')).toBeInTheDocument()
        expect(film.querySelector('img')).toBeNull()
      })

      it('一行放不下時多的收起來，「全部 N 項」就地展開、再按收起', async () => {
        const many = Array.from({ length: 8 }, (_, index) =>
          card({ item_id: `${index}`.padStart(32, '0'), title: `劇 ${index + 1}`, progress: null }),
        )
        await expanded(watching({ resume: [], next_up: many }))

        const next = screen.getByRole('region', { name: '下一集' })
        const toggle = within(next).getByRole('button', { name: '全部 8 項' })
        const rows = within(next).getAllByRole('listitem')

        expect(toggle).toHaveAttribute('aria-expanded', 'false')
        expect(toggle).toHaveAttribute('aria-controls', within(next).getByRole('list').id)
        // 收起時每一格帶著「哪個寬度以上才出現」：窄版 2、sm 3、lg 4、xl 6 格，與牆同一份欄數。
        expect(rows.map((row) => row.className)).toEqual([
          '',
          '',
          'hidden sm:block',
          'hidden lg:block',
          'hidden xl:block',
          'hidden xl:block',
          'hidden',
          'hidden',
        ])

        await userEvent.click(toggle)

        expect(toggle).toHaveAttribute('aria-expanded', 'true')
        expect(toggle).toHaveAccessibleName('收起')
        expect(toggle).toHaveFocus()
        expect(
          within(next)
            .getAllByRole('listitem')
            .every((row) => row.className === ''),
        ).toBe(true)
      })

      it.each([
        [2, null],
        [3, 'sm:hidden'],
        [4, 'lg:hidden'],
        [6, 'xl:hidden'],
        [7, ''],
      ])('%i 格時「全部」鍵只在一行放不下的寬度出現', async (count, shown) => {
        const cards = Array.from({ length: count }, (_, index) =>
          card({ item_id: `${index}`.padStart(32, '0'), title: `劇 ${index + 1}` }),
        )
        await expanded(watching({ resume: cards, next_up: [] }))

        const resume = screen.getByRole('region', { name: '繼續觀看' })
        const toggle = within(resume).queryByRole('button', { name: `全部 ${count} 項` })

        if (shown === null) {
          expect(toggle).not.toBeInTheDocument()
        } else {
          expect(toggle?.className.split(' ').filter((name) => name.endsWith('hidden'))).toEqual(
            shown ? [shown] : [],
          )
        }
      })

      it('主機推不出來時卡片不是連結，說不知道 Jellyfin 開在哪裡', async () => {
        await expanded(watching({ jellyfin: { public_url: '', url: '', port: null }, next_up: [] }))

        const resume = screen.getByRole('region', { name: '繼續觀看' })

        expect(within(resume).queryByRole('link')).not.toBeInTheDocument()
        expect(within(resume).getAllByText('不知道 Jellyfin 開在哪裡')).toHaveLength(2)
      })
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
      await userEvent.click(await findCarryOn())
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
