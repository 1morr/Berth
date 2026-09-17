import { useEffect, useId } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useRouter } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { meQueryOptions } from '../api/auth'
import { ApiError } from '../api/client'
import {
  inventoriesQueryOptions,
  inventoryQueryOptions,
  accessRefusal,
  type Inventory,
  type InventoryCard,
  type InventoryLibrary,
} from '../api/inventory'
import { jellyfinAddressQueryOptions } from '../api/settings'
import { GHOST_LINK, GhostButton, NAV_BOX, NAV_BOX_ACTIVE, Notice } from '../components/controls'
import { TilePlaceholder } from '../discover/MediaTile'
import { WALL_GRID } from '../discover/MediaWall'
import { InventoryTile } from '../inventory/InventoryTile'
import { jellyfinLibrariesUrl } from '../inventory/jellyfinLink'
import tmdbLogo from '../assets/tmdb.svg'

/** 網址上的篩選（`?filter=`）。Issue 那一種留給 M2（票 13 驗收）。 */
export type InventoryFilter = 'review' | 'unmatched'

/** 讀取中先畫幾格空位，與探索牆同一個道理：版面不跳。 */
const PLACEHOLDERS = 12

/** 切換列與篩選列的一個方塊。當前那一個重橫線 + `deck` 底，不靠顏色（與頁首導覽同一種）。 */
const SWITCH = `${NAV_BOX} inline-flex items-center px-4 py-2.5`
const SWITCH_ACTIVE = `${NAV_BOX_ACTIVE} inline-flex items-center px-4 py-2.5`
/** 篩選列的方塊比切換列小一號。 */
const FILTER = `${NAV_BOX} inline-flex items-center px-3 py-1.5`
const FILTER_ACTIVE = `${NAV_BOX_ACTIVE} inline-flex items-center px-3 py-1.5`
/** 分頁鍵：Ghost 的外觀，但它們換網址，所以是連結。到頭的那一顆是同樣大小的一段字。 */
const PAGE_KEY = 'label inline-flex min-h-6 items-center border-2 px-3 py-1.5'

/**
 * 媒體庫頁 `/library/:libraryId`（M1.5 票 03、`.scratch/m1.5/library-shape.md`）。
 *
 * 堆場全景加一條待卸貨的碼頭邊：Jellyfin 的牆是已經進倉的整座堆場（一頁 100 箱，照 Jellyfin 的順序），
 * 上方那一條是 Berth 經手、還沒進倉的貨。使用者在兩個時刻打開它——「我想看那部片」與「怎麼那部還沒好」。
 *
 * 一個媒體庫一個網址，頁碼與篩選也在網址上：重新整理、分享與上一頁都留得住。篩選不重抓——Berth 經手的
 * 那一份跟著每一頁一起到手，數字由後端算好。
 */
export function InventoryPage({
  libraryId,
  page,
  filter,
}: {
  libraryId: string | null
  page: number
  filter?: InventoryFilter
}) {
  const { t } = useTranslation()
  const libraries = useQuery(inventoriesQueryOptions)

  return (
    <div className="mx-auto grid w-full max-w-[110rem] gap-6 px-6 py-8">
      <div className="border-b-2 border-rule-strong pb-2">
        <h1 className="label text-ink">{t('inventory.title')}</h1>
      </div>

      {libraries.isPending ? (
        <Placeholders />
      ) : !libraries.data ? (
        <Trouble error={libraries.error} retry={() => void libraries.refetch()} />
      ) : libraries.data.length === 0 ? (
        <NoLibraries />
      ) : (
        <>
          <nav aria-label={t('inventory.libraries')} className="flex flex-wrap gap-2">
            {libraries.data.map((row) => (
              <Link
                key={row.id}
                to="/library/$libraryId"
                params={{ libraryId: row.id }}
                // 換媒體庫時頁碼與篩選不跟著走：那是上一個媒體庫的。
                activeOptions={{ exact: true, includeSearch: false }}
                className={SWITCH}
                activeProps={{ className: SWITCH_ACTIVE }}
              >
                {/* 媒體庫名是使用者在 Jellyfin 打的字：`.label` 的大寫會把 `Movies` 印成 `MOVIES`（票 15）。 */}
                <span className="normal-case">{row.name}</span>
              </Link>
            ))}
          </nav>
          {libraryId !== null && (
            <Wall libraryId={libraryId} page={page} filter={filter} libraries={libraries.data} />
          )}
        </>
      )}

      {/* 還沒進 Jellyfin 的卡片與詳情頁的資料來自 TMDB（brief §20.3）。它是法定聲明，不是頁尾裝飾。 */}
      <footer className="flex flex-wrap items-center gap-x-3 gap-y-2 border-t-2 border-rule pt-4">
        <img src={tmdbLogo} alt="TMDB" height={16} className="h-4 w-auto" />
        <p className="max-w-prose text-xs text-ink-dim">{t('discover.attribution')}</p>
      </footer>
    </div>
  )
}

function Wall({
  libraryId,
  page,
  filter,
  libraries,
}: {
  libraryId: string
  page: number
  filter?: InventoryFilter
  libraries: InventoryLibrary[]
}) {
  const { t } = useTranslation()
  const wall = useQuery(inventoryQueryOptions(libraryId, page))
  const wallTitle = useId()

  if (wall.isPending) return <Placeholders />
  if (!wall.data) {
    if (accessRefusal(wall.error)?.reason === 'library_not_visible') {
      return <UnknownLibrary first={libraries[0]} />
    }
    return <Trouble error={wall.error} retry={() => void wall.refetch()} />
  }

  const inventory = wall.data
  const notInJellyfin = inventory.tracked.filter((card) => card.presence !== 'found')
  const flagged = filter
    ? {
        filter,
        cards: inventory.tracked.filter((card) =>
          filter === 'review' ? card.tracking?.needs_review : card.tracking?.has_unmatched,
        ),
      }
    : null

  return (
    <>
      {/* 還沒進 Jellyfin 的作品不在 Jellyfin 的分頁結果裡，所以自己一條，翻到第幾頁都在（使用者拍板）。 */}
      {!flagged && notInJellyfin.length > 0 && (
        <NotInJellyfin cards={notInJellyfin} inventory={inventory} />
      )}

      <section aria-labelledby={wallTitle} className="grid gap-4">
        <h2 id={wallTitle} className="sr-only">
          {inventory.library.name}
        </h2>
        <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
          <Filters inventory={inventory} page={page} />
          {flagged ? (
            // 牆換掉了要說得出來——螢幕閱讀器看不到格子從 100 格變成 2 格。
            <p aria-live="polite" className="value text-xs text-ink-dim">
              {t('inventory.showing', { count: flagged.cards.length })}
            </p>
          ) : (
            <Pager inventory={inventory} announce />
          )}
        </div>

        {flagged ? (
          flagged.cards.length > 0 ? (
            <Tiles cards={flagged.cards} inventory={inventory} />
          ) : (
            <EmptyFilter library={inventory.library} filter={flagged.filter} page={page} />
          )
        ) : inventory.titles.length > 0 ? (
          <>
            <Tiles cards={inventory.titles} inventory={inventory} />
            {/* 牆底那一組只在真的有別頁時出現：只有一頁時總數已經寫在篩選列旁。 */}
            {(inventory.total > inventory.page_size || inventory.page > 1) && (
              <div className="flex justify-end">
                <Pager inventory={inventory} />
              </div>
            )}
          </>
        ) : inventory.total > 0 || notInJellyfin.length === 0 ? (
          <EmptyWall inventory={inventory} />
        ) : // Jellyfin 裡還沒有任何作品、但上面那一條有：說「這個媒體庫還沒有任何作品」就是謊話。
        null}
      </section>
    </>
  )
}

function Tiles({ cards, inventory }: { cards: InventoryCard[]; inventory: Inventory }) {
  return (
    <div className={WALL_GRID}>
      {cards.map((card) => (
        <InventoryTile
          key={`${card.media_id}|${card.jellyfin_item_id}`}
          card={card}
          web={inventory.jellyfin}
          libraryId={inventory.library.id}
        />
      ))}
    </div>
  )
}

/** 還沒進 Jellyfin 的 Berth 作品。標題不叫「在路上」：失敗的、Jellyfin 找不到的也在這裡。 */
function NotInJellyfin({ cards, inventory }: { cards: InventoryCard[]; inventory: Inventory }) {
  const { t } = useTranslation()
  const titleId = useId()

  return (
    <section aria-labelledby={titleId} className="grid gap-4">
      <div className="flex items-baseline gap-3 border-b-2 border-rule-strong pb-2">
        <h2 id={titleId} className="label text-ink">
          {t('inventory.notInJellyfin')}
        </h2>
        <span aria-hidden="true" className="value text-xs text-ink-dim">
          {cards.length}
        </span>
        <span className="sr-only">
          {t('inventory.notInJellyfinCount', { count: cards.length })}
        </span>
      </div>
      <Tiles cards={cards} inventory={inventory} />
    </section>
  )
}

/**
 * 全部 · 待審 N · Unmatched N。數字是後端算的、整個媒體庫的，不隨篩選變。
 *
 * **每一個都帶著現在的頁碼**：篩選的清單跟著每一頁一起到手，換篩選不必重抓（shape §6）；按回「全部」
 * 也回到原本那一頁。
 */
function Filters({ inventory, page }: { inventory: Inventory; page: number }) {
  const { t } = useTranslation()
  const kept = page > 1 ? { page } : {}
  const options = [
    { search: kept, label: t('inventory.filter.all') },
    {
      search: { ...kept, filter: 'review' as const },
      label: t('inventory.filter.review', { count: inventory.review }),
    },
    {
      search: { ...kept, filter: 'unmatched' as const },
      label: t('inventory.filter.unmatched', { count: inventory.unmatched }),
    },
  ]

  return (
    <nav aria-label={t('inventory.filters')} className="flex flex-wrap gap-2">
      {options.map((option) => (
        <Link
          key={option.label}
          to="/library/$libraryId"
          params={{ libraryId: inventory.library.id }}
          search={option.search}
          // 「全部」的 `{}` 是每一種 search 的子集，不比到一模一樣的話它永遠是當前頁。
          activeOptions={{ exact: true }}
          className={FILTER}
          activeProps={{ className: FILTER_ACTIVE }}
        >
          {option.label}
        </Link>
      ))}
    </nav>
  )
}

/**
 * `1–100 / 523` 加上一頁 / 下一頁（jellyfin-web 的分頁，使用者拍板）。看得見的是數字，聽得見的是
 * 帶單位的那一句（DESIGN.md 的區塊標題規則）；牆上方那一組把它放進 `aria-live`，換頁時念得出來。
 */
function Pager({ inventory, announce = false }: { inventory: Inventory; announce?: boolean }) {
  const { t } = useTranslation()
  const { page, page_size: size, total, library } = inventory
  if (total === 0) return null
  const pages = Math.max(1, Math.ceil(total / size))
  const first = Math.min((page - 1) * size + 1, total)
  const last = Math.min(page * size, total)
  const beyond = page > pages

  return (
    <nav aria-label={t('inventory.pages')} className="flex flex-wrap items-center gap-2">
      <span aria-hidden="true" className="value text-xs text-ink-dim">
        {beyond ? `— / ${total}` : `${first}–${last} / ${total}`}
      </span>
      {announce && (
        <span aria-live="polite" className="sr-only">
          {beyond
            ? t('inventory.rangeBeyond', { total })
            : t('inventory.range', { first, last, total })}
        </span>
      )}
      {(pages > 1 || page > 1) && (
        <>
          <PageKey libraryId={library.id} to={page > 1 ? Math.min(page - 1, pages) : null}>
            {t('inventory.previous')}
          </PageKey>
          <PageKey libraryId={library.id} to={page < pages ? page + 1 : null}>
            {t('inventory.next')}
          </PageKey>
        </>
      )}
    </nav>
  )
}

function PageKey({
  libraryId,
  to,
  children,
}: {
  libraryId: string
  to: number | null
  children: string
}) {
  if (to === null) {
    // 到頭了：位置不變、不是連結，說得出它按不了。
    return (
      <span aria-disabled="true" className={`${PAGE_KEY} border-rule text-ink-dim`}>
        {children}
      </span>
    )
  }
  return (
    <Link
      to="/library/$libraryId"
      params={{ libraryId }}
      search={to > 1 ? { page: to } : {}}
      className={`${PAGE_KEY} border-rule text-ink hover:border-rule-strong`}
    >
      {children}
    </Link>
  )
}

/** 篩完什麼都沒有：給一條回到全部的路（PRODUCT 原則 4：畫面永遠要有下一步）。 */
function EmptyFilter({
  library,
  filter,
  page,
}: {
  library: InventoryLibrary
  filter: InventoryFilter
  page: number
}) {
  const { t } = useTranslation()

  return (
    <div className="grid justify-items-start gap-3 border-2 border-rule bg-well px-4 py-4">
      <p className="max-w-prose text-sm text-ink">{t(`inventory.empty.${filter}`)}</p>
      <Link
        to="/library/$libraryId"
        params={{ libraryId: library.id }}
        search={page > 1 ? { page } : {}}
        className={GHOST_LINK}
      >
        {t('inventory.empty.showAll')}
      </Link>
    </div>
  )
}

/** 這一頁沒有作品：媒體庫是空的，或頁碼超出範圍。兩種下一步不同。 */
function EmptyWall({ inventory }: { inventory: Inventory }) {
  const { t } = useTranslation()
  const beyond = inventory.total > 0

  return (
    <div className="grid justify-items-start gap-3 border-2 border-rule bg-well px-4 py-4">
      <p className="max-w-prose text-sm text-ink">
        {beyond
          ? t('inventory.empty.page')
          : t('inventory.empty.library', { library: inventory.library.name })}
      </p>
      {beyond ? (
        <Link
          to="/library/$libraryId"
          params={{ libraryId: inventory.library.id }}
          search={{}}
          className={GHOST_LINK}
        >
          {t('inventory.empty.toFirstPage')}
        </Link>
      ) : (
        <Link to="/" className={GHOST_LINK}>
          {t('inventory.empty.toDiscover')}
        </Link>
      )}
    </div>
  )
}

/** 這位使用者在 Jellyfin 沒有任何電影或劇集媒體庫。 */
function NoLibraries() {
  const { t } = useTranslation()
  const me = useQuery(meQueryOptions)
  const admin = me.data?.role === 'admin'

  return (
    <div className="grid justify-items-start gap-3 border-2 border-rule bg-well px-4 py-4">
      <p className="max-w-prose text-sm text-ink">{t('inventory.empty.noLibraries')}</p>
      {admin ? (
        <JellyfinLibrariesLink />
      ) : (
        <p className="text-sm text-ink-dim">{t('inventory.empty.askAdmin')}</p>
      )}
    </div>
  )
}

/** 管理員的下一步在 Jellyfin 那邊。主機推不出來時不給一條死連結（票 14a 的同一個規矩）。 */
function JellyfinLibrariesLink() {
  const { t } = useTranslation()
  const address = useQuery(jellyfinAddressQueryOptions)
  const url = address.data ? jellyfinLibrariesUrl(address.data, window.location) : null
  if (!url) return null

  return (
    <a href={url} target="_blank" rel="noreferrer" className={GHOST_LINK}>
      {t('inventory.empty.openJellyfin')}
      <span className="sr-only">{t('inventory.jellyfin.newTab')}</span>
    </a>
  )
}

/**
 * 網址上的媒體庫不存在，或這位使用者看不到它。**同一句話**：分得出來就是在告訴人它存在。
 */
function UnknownLibrary({ first }: { first: InventoryLibrary | undefined }) {
  const { t } = useTranslation()

  return (
    <div className="grid justify-items-start gap-3 border-2 border-rule bg-well px-4 py-4">
      <p className="max-w-prose text-sm text-ink">{t('inventory.empty.unknown')}</p>
      {first && (
        <Link to="/library/$libraryId" params={{ libraryId: first.id }} className={GHOST_LINK}>
          {t('inventory.empty.toFirst', { library: first.name })}
        </Link>
      )}
    </div>
  )
}

/** 讀不到東西的三種樣子：session 被結束、Jellyfin 問不到、Berth 自己沒回應。 */
function Trouble({ error, retry }: { error: Error | null; retry: () => void }) {
  const { t } = useTranslation()
  const refusal = accessRefusal(error)

  if (error instanceof ApiError && error.status === 401) return <SessionEnded />
  if (refusal?.reason === 'jellyfin_unreachable') {
    return (
      <div className="grid max-w-prose justify-items-start gap-3">
        <Notice signal="blocked" label={t('inventory.jellyfin.downLabel')}>
          {t('inventory.jellyfin.down')}
        </Notice>
        {refusal.detail && (
          <p className="value text-xs wrap-anywhere text-ink-dim">{refusal.detail}</p>
        )}
        <div className="flex flex-wrap gap-2">
          <GhostButton type="button" onClick={retry}>
            {t('inventory.jellyfin.retry')}
          </GhostButton>
          <Link to="/health" className={GHOST_LINK}>
            {t('inventory.jellyfin.toHealth')}
          </Link>
        </div>
      </div>
    )
  }
  return <p className="max-w-prose text-sm text-ink-dim">{t('inventory.off')}</p>
}

/**
 * 後端結束了這個 session（帳號在 Jellyfin 被停用）。重跑路由守衛：它問 `GET /auth/me` 拿到 401，
 * 就把人送到 `/login` 並說「登入已失效」——與 session 自然過期同一條路，不另寫一份。
 */
function SessionEnded() {
  const router = useRouter()
  useEffect(() => {
    void router.invalidate()
  }, [router])
  return <Placeholders />
}

/** 讀取中：不動的空位格。這個世界沒有骨架屏動畫。 */
function Placeholders() {
  return (
    <div className={WALL_GRID}>
      {Array.from({ length: PLACEHOLDERS }, (_, index) => (
        <TilePlaceholder key={index} />
      ))}
    </div>
  )
}
