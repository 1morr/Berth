import { useEffect, useId, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { meQueryOptions } from '../api/auth'
import { ApiError } from '../api/client'
import { accessRefusal } from '../api/jellyfin'
import {
  inventoriesQueryOptions,
  inventoryFiltersQueryOptions,
  inventoryKey,
  inventoryQueryOptions,
  narrowed,
  wallQuery,
  type Inventory,
  type InventoryCard,
  type InventoryFilter,
  type InventoryFilters,
  type InventoryLibrary,
  type SortOrder,
  type WallQuery,
  type WallSearch,
} from '../api/inventory'
import { libraryReviewQueryOptions, type LibraryReviewKind } from '../api/review'
import { jellyfinAddressQueryOptions } from '../api/settings'
import {
  Checkbox,
  GHOST_LINK,
  GhostButton,
  NAV_BOX,
  NAV_BOX_ACTIVE,
  NAV_LINK,
  TEXT_LINK,
  Notice,
} from '../components/controls'
import { Dot } from '../components/Dot'
import { SessionEnded } from '../components/SessionEnded'
import { TilePlaceholder } from '../components/TilePlaceholder'
import { SEARCH_DEBOUNCE_MS } from '../components/useDebounced'
import { WALL_GRID_CONFIRMABLE } from '../components/wallGrid'
import { InventoryTile } from '../inventory/InventoryTile'
import { LibraryWatching, WatchingElsewhere } from '../watching/WatchingRows'
import { jellyfinLibrariesUrl } from '../inventory/jellyfinLink'
import { TmdbAttribution } from '../components/TmdbAttribution'
import { ReviewItem } from '../review/ReviewItem'

/** 讀取中先畫幾格空位，與探索牆同一個道理：版面不跳。 */
const PLACEHOLDERS = 12

/** 切換列與篩選列的一個方塊。當前那一個重橫線 + `deck` 底，不靠顏色（與頁首導覽同一種）。 */
const SWITCH = `${NAV_LINK} inline-flex items-center px-4 py-2.5`
/** 篩選列的方塊比切換列小一號。 */
const FILTER = `${NAV_BOX} inline-flex items-center px-3 py-1.5`
const FILTER_ACTIVE = `${NAV_BOX_ACTIVE} inline-flex items-center px-3 py-1.5`
/** 分頁鍵：Ghost 的外觀，但它們換網址，所以是連結。到頭的那一顆是同樣大小的一段字。 */
const PAGE_KEY = 'label inline-flex min-h-6 items-center border-2 px-3 py-1.5'
/** 排序的兩個下拉：輸入框那一套外觀（DESIGN.md Inputs），高度與篩選列的方塊對齊。 */
const SELECT =
  'value max-w-full border-2 border-rule bg-hull px-2 py-1 text-sm text-ink focus:border-rule-strong'

/**
 * 媒體庫頁 `/library/:libraryId`（M1.5 票 03、`.scratch/m1.5/library-shape.md`）。
 *
 * 堆場全景加一條待卸貨的碼頭邊：Jellyfin 的牆是已經進倉的整座堆場（一頁 50 箱，照 Jellyfin 的順序），
 * 上方那一條是 Berth 經手、還沒進倉的貨。使用者在兩個時刻打開它——「我想看那部片」與「怎麼那部還沒好」。
 *
 * 一個媒體庫一個網址，頁碼、篩選、排序與類型年份也在網址上：重新整理、分享與上一頁都留得住。排序與類型、
 * 年份是 Jellyfin 的查詢（票 06）。
 *
 * **「待審」「對不到」是審核佇列在這個媒體庫上的子集**（M2 票 14，`.scratch/m2/review-shape.md`）：篩出來的
 * 是要處理的事，不是要看的作品，所以是一列一件事的清單、列就是 `/review` 那一列（`ReviewItem`）。它們是管理員
 * 的工作佇列（使用者拍板）：`user` 看不到這兩個篩選，網址上帶著也照畫整面牆——他碰到停下來的那一筆只能等
 * （PRODUCT.md），卡片上的「待審」色塊與 `/jobs` 的「等管理員審核」已經說了。
 */
export function InventoryPage({
  libraryId,
  page,
  filter,
  search = {},
}: {
  libraryId: string | null
  page: number
  filter?: InventoryFilter
  search?: WallSearch
}) {
  const { t } = useTranslation()
  const libraries = useQuery(inventoriesQueryOptions)
  const me = useQuery(meQueryOptions)
  const admin = me.data?.role === 'admin'
  const adminFilter = admin ? filter : undefined

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
              >
                {/* 媒體庫名是使用者在 Jellyfin 打的字：`.label` 的大寫會把 `Movies` 印成 `MOVIES`（票 15）。 */}
                <span className="normal-case">{row.name}</span>
              </Link>
            ))}
          </nav>
          {/* 接著看在「還沒進 Jellyfin」之前（票 07）。只在打開媒體庫的那一刻：翻頁與篩選是在堆場裡找東西，
              兩列不再把牆往下推，而且它們不照類型年份篩（使用者拍板）。排序不算——它不會讓哪一集不見。 */}
          {libraryId !== null &&
            (page === 1 && !adminFilter && !narrowed(wallQuery(search, undefined)) ? (
              <LibraryWatching libraryId={libraryId} />
            ) : (
              <WatchingElsewhere libraryId={libraryId}>
                {/* 回到會畫那兩列的樣子：第 1 頁、不篩；排序留著，它不會讓哪一集不見。 */}
                <Link
                  to="/library/$libraryId"
                  params={{ libraryId }}
                  search={wallQuery(
                    { sort: search.sort, order: search.order },
                    libraries.data.find((row) => row.id === libraryId),
                  )}
                  className={TEXT_LINK}
                >
                  {t('watching.toFirst')}
                </Link>
              </WatchingElsewhere>
            ))}
          {libraryId !== null && (
            <Wall
              libraryId={libraryId}
              page={page}
              filter={adminFilter}
              admin={admin}
              search={search}
              libraries={libraries.data}
            />
          )}
        </>
      )}

      <TmdbAttribution />
    </div>
  )
}

function Wall({
  libraryId,
  page,
  filter,
  admin,
  search,
  libraries,
}: {
  libraryId: string
  page: number
  /** 只有 `admin` 會拿到（`InventoryPage`）。 */
  filter?: InventoryFilter
  /** 畫不畫「全部 · 待審 · 對不到」那一排。 */
  admin: boolean
  search: WallSearch
  libraries: InventoryLibrary[]
}) {
  const query = wallQuery(
    search,
    libraries.find((row) => row.id === libraryId),
  )
  const wall = useQuery(inventoryQueryOptions(libraryId, page, query))
  const wallTitle = useId()
  const panel = useId()
  // 一次開一份清單：兩份一起攤開，牆就被推到第二屏。
  const [open, setOpen] = useState<Narrowing | null>(null)

  if (wall.isPending) return <Placeholders />
  if (!wall.data) {
    if (accessRefusal(wall.error)?.reason === 'library_not_visible') {
      return <UnknownLibrary first={libraries[0]} />
    }
    return <Trouble error={wall.error} retry={() => void wall.refetch()} />
  }

  const inventory = wall.data
  const notInJellyfin = inventory.tracked.filter((card) => card.presence !== 'found')
  const narrowing = narrowed(query)

  return (
    <>
      {/* 還沒進 Jellyfin 的作品不在 Jellyfin 的分頁結果裡，所以自己一條，翻到第幾頁都在（使用者拍板）。
          篩類型或年份時收起：它們在 Jellyfin 裡沒有類型，套不上（票 06，使用者拍板）。 */}
      {!filter && !narrowing && notInJellyfin.length > 0 && (
        <NotInJellyfin cards={notInJellyfin} inventory={inventory} />
      )}

      <section
        aria-labelledby={wallTitle}
        aria-busy={wall.isPlaceholderData || undefined}
        className="grid gap-4"
      >
        <h2 id={wallTitle} className="sr-only">
          {inventory.library.name}
        </h2>
        <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
          <div className="flex min-w-0 flex-wrap items-center gap-x-4 gap-y-3">
            {admin && <Filters inventory={inventory} page={page} query={query} filter={filter} />}
            {/* 待審與 Unmatched 是審核佇列的清單：排序、類型年份與名字留在網址上，但套不上，所以不畫。 */}
            {!filter && <SearchBox library={inventory.library} query={query} />}
            {!filter && (
              <Arrange
                library={inventory.library}
                query={query}
                open={open}
                panel={panel}
                onToggle={(kind) => setOpen(open === kind ? null : kind)}
              />
            )}
          </div>
          {filter ? (
            <QueueCount libraryId={libraryId} filter={filter} />
          ) : (
            <Pager inventory={inventory} query={query} announce />
          )}
        </div>
        {!filter && open && (
          <NarrowPanel id={panel} kind={open} library={inventory.library} query={query} />
        )}

        {filter ? (
          <LibraryQueue library={inventory.library} filter={filter} page={page} query={query} />
        ) : inventory.titles.length > 0 ? (
          <>
            <Tiles cards={inventory.titles} inventory={inventory} />
            {/* 牆底那一組只在真的有別頁時出現：只有一頁時總數已經寫在篩選列旁。 */}
            {(inventory.total > inventory.page_size || inventory.page > 1) && (
              <div className="flex justify-end">
                <Pager inventory={inventory} query={query} end />
              </div>
            )}
          </>
        ) : inventory.total > 0 ? (
          <EmptyWall inventory={inventory} query={query} />
        ) : narrowing ? (
          <EmptyNarrowed library={inventory.library} query={query} />
        ) : notInJellyfin.length === 0 ? (
          <EmptyWall inventory={inventory} query={query} />
        ) : // Jellyfin 裡還沒有任何作品、但上面那一條有：說「這個媒體庫還沒有任何作品」就是謊話。
        null}
      </section>
    </>
  )
}

/** 類型或年份：兩個勾選清單各一顆開關。 */
type Narrowing = 'genres' | 'years'

/**
 * 換排序或篩選：換網址、回到第 1 頁（jellyfin-web 同樣把 `StartIndex` 歸零）。`replace` 給邊打邊搜：
 * 打一個名字不該在上一頁留下每一段打到一半的字。
 */
function useRearrange(library: InventoryLibrary, { replace = false } = {}) {
  const navigate = useNavigate()
  return (next: WallQuery) =>
    void navigate({
      to: '/library/$libraryId',
      params: { libraryId: library.id },
      search: wallQuery(next, library),
      replace,
    })
}

/**
 * 牆上按名字找（M2 票 14，critique P2：「真正擁有答案的那一頁反而不能問問題」）。Jellyfin 的 `searchTerm`，
 * 寫進網址（`q`），重新整理與分享都還在。
 *
 * **邊打邊搜**（使用者拍板，Sonarr / Radarr 工具列的搜尋框）：停手 500ms 才換網址，與探索頁同一個間隔；
 * 換網址用 `replace`、回到第 1 頁。網址自己換了（上一頁、「清除搜尋」）時框裡的字跟著換——但只在兩邊真的
 * 說的是不同的名字時：打「the 」停下來，網址是 `the`，不能把使用者正要接著打的那個空白吃掉。
 *
 * 計時器在事件裡而不是 `useDebounced` + effect：換網址只該由打字觸發。effect 版要把 `query` 與導覽放進相依
 * （exhaustive-deps），於是換排序、翻頁這些與打字無關的變動也會跑一次它，再靠比對擋下來。
 */
function SearchBox({ library, query }: { library: InventoryLibrary; query: WallQuery }) {
  const { t } = useTranslation()
  const rearrange = useRearrange(library, { replace: true })
  const id = useId()
  const asked = query.q ?? ''
  const [text, setText] = useState(asked)
  const [seen, setSeen] = useState(asked)
  const timer = useRef<number | undefined>(undefined)

  if (asked !== seen) {
    setSeen(asked)
    if (asked !== text.trim()) setText(asked)
  }
  useEffect(() => () => window.clearTimeout(timer.current), [])

  const change = (value: string) => {
    setText(value)
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => {
      const next = value.trim()
      if (next !== asked) rearrange({ ...query, q: next || undefined })
    }, SEARCH_DEBOUNCE_MS)
  }

  return (
    <div className="flex min-w-0 items-center gap-2">
      <label htmlFor={id} className="label shrink-0 text-ink-dim">
        {t('inventory.search.label')}
      </label>
      <input
        id={id}
        type="search"
        value={text}
        onChange={(event) => change(event.target.value)}
        className={`${SELECT} w-44 min-w-0 placeholder:text-ink-dim sm:w-56`}
      />
    </div>
  )
}

/**
 * 排序、方向、類型、年份的開關（票 06；使用者拍板：兩個原生下拉，類型與年份各一份就地展開、勾了就套用的清單）。
 *
 * 排序選單是這個媒體庫的 `sorts`（照 jellyfin-web）。類型與年份的開關是 `aria-expanded` 的按鈕，清單畫在整列
 * 控制項下方（`NarrowPanel`）：`<details>` 的內容只能長在它自己裡面，展開時不是把旁邊的開關擠到下一行，
 * 就是困在半欄寬裡（實跑量到）。
 */
function Arrange({
  library,
  query,
  open,
  panel,
  onToggle,
}: {
  library: InventoryLibrary
  query: WallQuery
  open: Narrowing | null
  panel: string
  onToggle: (kind: Narrowing) => void
}) {
  const { t } = useTranslation()
  const rearrange = useRearrange(library)
  const sortId = useId()
  const orderId = useId()

  return (
    <div className="flex min-w-0 flex-wrap items-center gap-2">
      <label htmlFor={sortId} className="label text-ink-dim">
        {t('inventory.sort.label')}
      </label>
      <select
        id={sortId}
        value={query.sort ?? library.sorts[0]}
        onChange={(event) =>
          rearrange({ ...query, sort: library.sorts.find((key) => key === event.target.value) })
        }
        className={SELECT}
      >
        {library.sorts.map((key) => (
          <option key={key} value={key}>
            {t(`inventory.sort.by.${key}`)}
          </option>
        ))}
      </select>
      {/* 看得見的標籤（票 13）：只有 `aria-label` 的話，看得到畫面的人只能從選項猜這一個下拉在管什麼。 */}
      <label htmlFor={orderId} className="label text-ink-dim">
        {t('inventory.sort.order')}
      </label>
      <select
        id={orderId}
        value={query.order ?? ORDERS[0]}
        onChange={(event) => {
          const order = ORDERS.find((key) => key === event.target.value)
          rearrange({ ...query, order: order === 'Descending' ? order : undefined })
        }}
        className={SELECT}
      >
        {ORDERS.map((order) => (
          <option key={order} value={order}>
            {t(`inventory.sort.${order}`)}
          </option>
        ))}
      </select>
      {NARROWINGS.map((kind) => {
        const chosen = query[kind]?.length ?? 0
        return (
          <button
            key={kind}
            type="button"
            aria-expanded={open === kind}
            aria-controls={open === kind ? panel : undefined}
            onClick={() => onToggle(kind)}
            className={`${chosen > 0 ? FILTER_ACTIVE : FILTER} gap-2`}
          >
            <span>{t(`inventory.narrow.${kind}`)}</span>
            {chosen > 0 && (
              <>
                <span aria-hidden="true" className="value text-xs leading-none">
                  {chosen}
                </span>
                <span className="sr-only">{t('inventory.narrow.chosen', { count: chosen })}</span>
              </>
            )}
            {/* 看得見的展開狀態；聽得見的是 `aria-expanded`。 */}
            <span aria-hidden="true" className="text-ink-dim">
              {open === kind ? t('common.collapse') : t('common.expand')}
            </span>
          </button>
        )
      })}
    </div>
  )
}

/** 排序方向。第一個是打開牆時的方向，不寫進網址。 */
const ORDERS: readonly SortOrder[] = ['Ascending', 'Descending']

const NARROWINGS: readonly Narrowing[] = ['genres', 'years']

/**
 * 兩份清單各自從哪裡讀、寫回網址的哪一格。年份在網址與後端是數字，勾選框的值是字串。
 */
const NARROWING: Record<
  Narrowing,
  {
    chosen: (query: WallQuery) => string[]
    listed: (options: InventoryFilters) => string[]
    with: (query: WallQuery, next: string[]) => WallQuery
  }
> = {
  genres: {
    chosen: (query) => query.genres ?? [],
    listed: (options) => options.genres,
    with: (query, genres) => ({ ...query, genres }),
  },
  years: {
    chosen: (query) => (query.years ?? []).map(String),
    listed: (options) => options.years.map(String),
    with: (query, years) => ({ ...query, years: years.map(Number) }),
  },
}

/**
 * 類型或年份的勾選清單。勾了就套用、可多選（同一種之間是「或」，研究 §3.1）。打開才向後端要選項。
 *
 * **選著的不在清單上時照樣列出來**，才取消得了——分享來的連結可能帶著這個媒體庫沒有的類型（jellyfin-web 的
 * 篩選面板也是把兩份併起來）。
 */
function NarrowPanel({
  id,
  kind,
  library,
  query,
}: {
  id: string
  kind: Narrowing
  library: InventoryLibrary
  query: WallQuery
}) {
  const { t } = useTranslation()
  const rearrange = useRearrange(library)
  const filters = useQuery(inventoryFiltersQueryOptions(library.id))
  const titleId = useId()
  const narrowing = NARROWING[kind]
  const chosen = narrowing.chosen(query)
  const listed = filters.data ? narrowing.listed(filters.data) : []
  const shown = [...listed, ...chosen.filter((value) => !listed.includes(value))]
  const change = (next: string[]) => rearrange(narrowing.with(query, next))

  return (
    <div
      id={id}
      role="group"
      aria-labelledby={titleId}
      className="grid justify-items-start gap-3 border-2 border-rule bg-well px-4 py-3"
    >
      <p id={titleId} className="label text-ink-dim">
        {t(`inventory.narrow.${kind}`)}
      </p>
      {shown.length > 0 ? (
        <div className="grid w-full grid-cols-[repeat(auto-fill,minmax(9rem,1fr))] gap-x-4 gap-y-2">
          {shown.map((value) => (
            <Checkbox
              key={value}
              label={value}
              checked={chosen.includes(value)}
              onChange={(checked) =>
                change(checked ? [...chosen, value] : chosen.filter((item) => item !== value))
              }
            />
          ))}
        </div>
      ) : filters.isPending ? (
        <p className="text-sm text-ink-dim">{t('inventory.narrow.loading')}</p>
      ) : filters.isError ? (
        <div className="grid justify-items-start gap-2">
          <p className="text-sm text-ink">{t('inventory.narrow.failed')}</p>
          <GhostButton type="button" onClick={() => void filters.refetch()}>
            {t('inventory.narrow.retry')}
          </GhostButton>
        </div>
      ) : (
        <p className="text-sm text-ink-dim">{t(`inventory.narrow.none.${kind}`)}</p>
      )}
      {chosen.length > 0 && (
        <GhostButton type="button" onClick={() => change([])}>
          {t(`inventory.narrow.clear.${kind}`)}
        </GhostButton>
      )}
    </div>
  )
}

/** 一面牆是一份清單（票 13）：與探索牆、繼續觀看與下一集同一種語意，螢幕閱讀器念得出有幾項。 */
function Tiles({ cards, inventory }: { cards: InventoryCard[]; inventory: Inventory }) {
  return (
    <ul className={WALL_GRID_CONFIRMABLE}>
      {cards.map((card) => (
        <li key={`${card.media_id}|${card.jellyfin_item_id}`} className="grid">
          <InventoryTile card={card} web={inventory.jellyfin} libraryId={inventory.library.id} />
        </li>
      ))}
    </ul>
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

/** 某一頁的網址：第 1 頁不寫頁碼，排序與類型年份照帶。 */
function onPage(page: number, query: WallQuery) {
  return { ...(page > 1 ? { page } : {}), ...query }
}

/** 每一個篩選是審核佇列的哪一類。 */
const QUEUE_KIND: Record<InventoryFilter, LibraryReviewKind> = {
  review: 'plan',
  unmatched: 'unmatched',
}

/** 這個媒體庫上、這一個篩選的那幾件。清單與牆上方的件數讀同一份（同一個快取鍵，只問一次）。 */
function useLibraryQueue(libraryId: string, filter: InventoryFilter) {
  const queue = useQuery(libraryReviewQueryOptions(libraryId))
  const rows = queue.data?.rows.filter((row) => row.kind === QUEUE_KIND[filter]) ?? []
  return { queue, rows }
}

/** 牆換成清單了要說得出來——螢幕閱讀器看不到格子從 50 格變成 2 列。 */
function QueueCount({ libraryId, filter }: { libraryId: string; filter: InventoryFilter }) {
  const { t } = useTranslation()
  const { queue, rows } = useLibraryQueue(libraryId, filter)

  return (
    <p aria-live="polite" className="value text-xs text-ink-dim">
      {queue.data && t('inventory.showing', { count: rows.length })}
    </p>
  )
}

/**
 * 「待審」「對不到」：審核佇列在這個媒體庫上的那一類（M2 票 14、`.scratch/m2/review-shape.md`「媒體庫的子集」）。
 *
 * **列就是 `/review` 那一列**（`ReviewItem`，同一個 import），就地按；兩類同屬「要你決定」那一段，所以不畫段落
 * 抬頭。按完那一列從佇列上消失（它自己重問 `['review']`），這裡另外重問牆：篩選鍵上的數字是同一支查詢數的。
 * 清單下方一句連到 `/review`，說審核佇列裡還有幾件不在這一份裡。
 */
function LibraryQueue({
  library,
  filter,
  page,
  query,
}: {
  library: InventoryLibrary
  filter: InventoryFilter
  page: number
  query: WallQuery
}) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { queue, rows } = useLibraryQueue(library.id, filter)
  // 按完那一列就消失了，焦點與畫面上都不剩任何東西說「成了」——這一句給看不見畫面的人（同 `/review`）。
  const [said, setSaid] = useState('')

  if (queue.isPending) return <QueueLoading />
  if (!queue.data) return <p className="max-w-prose text-sm text-ink-dim">{t('review.off')}</p>

  const rest = queue.data.queue_total - rows.length
  const done = (text: string) => {
    setSaid(text)
    void queryClient.invalidateQueries({ queryKey: inventoryKey(library.id) })
  }

  return (
    <div className="grid max-w-[80rem] gap-3">
      <p aria-live="polite" className="sr-only">
        {said}
      </p>
      {rows.length > 0 ? (
        <ul aria-label={t(`inventory.queue.${filter}`)} className="grid gap-3">
          {rows.map((row) => (
            <li key={`${row.kind}:${row.ref}`} className="min-w-0">
              <ReviewItem row={row} onDone={done} />
            </li>
          ))}
        </ul>
      ) : (
        <EmptyFilter library={library} filter={filter} page={page} query={query} />
      )}
      {/* 超過上限時照實說（同 `/review`）：這兩類加起來超過 200 件時清單只有最舊的那幾件。 */}
      {queue.data.total > queue.data.rows.length && (
        <p className="text-xs text-ink-dim">
          {t('review.truncated', { shown: queue.data.rows.length, total: queue.data.total })}
        </p>
      )}
      {rest > 0 && (
        <p className="text-sm">
          <Link to="/review" className={TEXT_LINK}>
            {t('inventory.queue.rest', { count: rest })}
          </Link>
        </p>
      )}
    </div>
  )
}

/** 清單讀取中：兩列靜態方塊，沒有動畫（同 `/review`）。 */
function QueueLoading() {
  return (
    <div className="grid max-w-[80rem] gap-3" aria-hidden="true">
      <div className="h-24 border-2 border-rule bg-well" />
      <div className="h-24 border-2 border-rule bg-well" />
    </div>
  )
}

/**
 * 全部 · 待審 N · 對不到 N。數字是後端數的、整個媒體庫的審核佇列件數（與清單同一支查詢），不隨篩選變。
 *
 * **每一個都帶著現在的頁碼、排序與類型年份**：換篩選不重抓牆；按回「全部」回到原本排好、篩好的那一頁
 * （票 06）。
 *
 * **選著的那一個不是連結**，是一段 `aria-current="true"` 的字（票 13，M1.5 audit P3）：TanStack 的 `Link` 在
 * 當前時一定掛 `aria-current="page"`、改不掉，而同一頁的媒體庫切換列已經有一個「當前頁」——篩選是這一頁裡的
 * 一組選項，不是另一頁。按它本來就什麼都不會發生。
 */
function Filters({
  inventory,
  page,
  query,
  filter,
}: {
  inventory: Inventory
  page: number
  query: WallQuery
  filter: InventoryFilter | undefined
}) {
  const { t } = useTranslation()
  const kept = onPage(page, query)
  const options = [
    { filter: undefined, label: t('inventory.filter.all') },
    { filter: 'review' as const, label: t('inventory.filter.review', { count: inventory.review }) },
    {
      filter: 'unmatched' as const,
      label: t('inventory.filter.unmatched', { count: inventory.unmatched }),
    },
  ]

  return (
    <nav aria-label={t('inventory.filters')} className="flex flex-wrap gap-2">
      {options.map((option) =>
        option.filter === filter ? (
          <span key={option.label} aria-current="true" className={`${FILTER_ACTIVE} text-ink`}>
            {option.label}
          </span>
        ) : (
          <Link
            key={option.label}
            to="/library/$libraryId"
            params={{ libraryId: inventory.library.id }}
            search={option.filter ? { ...kept, filter: option.filter } : kept}
            // 「全部」的 search 是每一種的子集，模糊比對會讓它在待審頁上也被當成當前、掛上 `aria-current`。
            activeOptions={{ exact: true }}
            className={FILTER}
          >
            {option.label}
          </Link>
        ),
      )}
    </nav>
  )
}

/**
 * `1–50 / 523` 加上一頁 / 下一頁（jellyfin-web 的分頁，使用者拍板）。看得見的是數字，聽得見的是
 * 帶單位的那一句（DESIGN.md 的區塊標題規則）；牆上方那一組把它放進 `aria-live`，換頁時念得出來。
 *
 * 牆上下各一組，**兩個 landmark 名字不同**（`end`，票 13）：地標清單裡兩個同名的「分頁」分不出哪個是哪個
 * （WAI-ARIA landmark 的慣例：同一種出現兩次就各給一個名字）。
 */
function Pager({
  inventory,
  query,
  announce = false,
  end = false,
}: {
  inventory: Inventory
  query: WallQuery
  announce?: boolean
  /** 牆底那一組。 */
  end?: boolean
}) {
  const { t } = useTranslation()
  const { page, page_size: size, total, library } = inventory
  if (total === 0) return null
  const pages = Math.max(1, Math.ceil(total / size))
  const first = Math.min((page - 1) * size + 1, total)
  const last = Math.min(page * size, total)
  const beyond = page > pages

  return (
    <nav
      aria-label={end ? t('inventory.pagesEnd') : t('inventory.pages')}
      className="flex flex-wrap items-center gap-2"
    >
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
          <PageKey
            libraryId={library.id}
            to={page > 1 ? Math.min(page - 1, pages) : null}
            query={query}
          >
            {t('inventory.previous')}
          </PageKey>
          <PageKey libraryId={library.id} to={page < pages ? page + 1 : null} query={query}>
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
  query,
  children,
}: {
  libraryId: string
  to: number | null
  query: WallQuery
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
      search={onPage(to, query)}
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
  query,
}: {
  library: InventoryLibrary
  filter: InventoryFilter
  page: number
  query: WallQuery
}) {
  const { t } = useTranslation()

  return (
    <div className="grid justify-items-start gap-3 border-2 border-rule bg-well px-4 py-4">
      <p className="max-w-prose text-sm text-ink">{t(`inventory.empty.${filter}`)}</p>
      <Link
        to="/library/$libraryId"
        params={{ libraryId: library.id }}
        search={onPage(page, query)}
        className={GHOST_LINK}
      >
        {t('inventory.empty.showAll')}
      </Link>
    </div>
  )
}

/**
 * 篩類型、年份或名字之後一部都沒有（票 06、M2 票 14）。說出篩了什麼——空的是篩選的結果，不是媒體庫本身——
 * 並給清掉的路：名字與類型年份各一條，清一種留另一種；排序一律留著，它不會讓作品不見。
 */
function EmptyNarrowed({ library, query }: { library: InventoryLibrary; query: WallQuery }) {
  const { t, i18n } = useTranslation()
  // 同一種之間是「或」（研究 §3.1），照語言的習慣列出來。
  const either = new Intl.ListFormat(i18n.language, { type: 'disjunction' })
  const { genres, years, q } = query
  const listed = [
    q && t('inventory.narrow.listed.q', { q }),
    genres && t('inventory.narrow.listed.genres', { list: either.format(genres) }),
    years && t('inventory.narrow.listed.years', { list: either.format(years.map(String)) }),
  ].filter((line) => typeof line === 'string')

  return (
    <div className="grid justify-items-start gap-3 border-2 border-rule bg-well px-4 py-4">
      <p aria-live="polite" className="max-w-prose text-sm text-ink">
        {t('inventory.narrow.nothing')}
      </p>
      <p className="value flex flex-wrap gap-x-2 text-xs wrap-anywhere text-ink-dim">
        {listed.map((line, index) => (
          <span key={line} className="contents">
            {index > 0 && <Dot />}
            <span>{line}</span>
          </span>
        ))}
      </p>
      <div className="flex flex-wrap gap-2">
        {q && (
          <Link
            to="/library/$libraryId"
            params={{ libraryId: library.id }}
            search={wallQuery({ ...query, q: undefined }, library)}
            className={GHOST_LINK}
          >
            {t('inventory.narrow.clearSearch')}
          </Link>
        )}
        {(genres || years) && (
          <Link
            to="/library/$libraryId"
            params={{ libraryId: library.id }}
            search={wallQuery({ sort: query.sort, order: query.order, q }, library)}
            className={GHOST_LINK}
          >
            {t('inventory.narrow.clearBoth')}
          </Link>
        )}
      </div>
    </div>
  )
}

/** 這一頁沒有作品：媒體庫是空的，或頁碼超出範圍。兩種下一步不同。 */
function EmptyWall({ inventory, query }: { inventory: Inventory; query: WallQuery }) {
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
          search={query}
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

  if (error instanceof ApiError && error.status === 401) {
    return <SessionEnded pending={<Placeholders />} />
  }
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

/** 讀取中：不動的空位格。這個世界沒有骨架屏動畫。 */
function Placeholders() {
  return (
    <div className={WALL_GRID_CONFIRMABLE}>
      {Array.from({ length: PLACEHOLDERS }, (_, index) => (
        <TilePlaceholder key={index} inventory />
      ))}
    </div>
  )
}
