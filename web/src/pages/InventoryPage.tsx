import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { ApiError } from '../api/client'
import {
  inventoriesQueryOptions,
  inventoryQueryOptions,
  type Inventory,
  type InventoryRoute,
} from '../api/inventory'
import { GHOST_LINK, NAV_BOX, NAV_BOX_ACTIVE } from '../components/controls'
import { SetupHint } from '../components/SetupHint'
import { TilePlaceholder } from '../discover/MediaTile'
import { WALL_GRID } from '../discover/MediaWall'
import { InventoryTile } from '../inventory/InventoryTile'
import tmdbLogo from '../assets/tmdb.svg'

/** 網址上的篩選（`?filter=`）。Issue 那一種留給 M2（票 13 驗收）。 */
export type InventoryFilter = 'review' | 'unmatched'

/** 讀取中先畫幾格空位，與探索牆同一個道理：版面不跳。 */
const PLACEHOLDERS = 12

/** 切換列與篩選列的一個方塊。當前那一個重橫線 + `deck` 底，不靠顏色（與頁首導覽同一種）。 */
const SWITCH = `${NAV_BOX} inline-flex items-center gap-2 px-4 py-2.5`
const SWITCH_ACTIVE = `${NAV_BOX_ACTIVE} inline-flex items-center gap-2 px-4 py-2.5`
/** 篩選列的方塊比切換列小一號。 */
const FILTER = `${NAV_BOX} inline-flex items-center px-3 py-1.5`
const FILTER_ACTIVE = `${NAV_BOX_ACTIVE} inline-flex items-center px-3 py-1.5`

/**
 * 媒體庫頁 `/library/:routeSlug`（票 13、`.scratch/m1/library-shape.md`）。
 *
 * 同一座堆場的盤點表：探索牆是港外的船，這裡是已經靠岸的貨。使用者在兩個時刻打開它——
 * 「我想看那部片」（認出作品、一鍵到 Jellyfin）與「怎麼那部還沒好」（一眼看出哪一部需要人）。
 *
 * 一條 Route 一個網址，篩選也在網址上：重新整理、分享與上一頁都留得住。資料一次到手，
 * 篩選在這裡做——清單是幾十到幾百筆，而兩個篩選的數字已經由後端算好。
 */
export function InventoryPage({ slug, filter }: { slug: string | null; filter?: InventoryFilter }) {
  const { t } = useTranslation()
  const routes = useQuery(inventoriesQueryOptions)

  return (
    <div className="mx-auto grid w-full max-w-[110rem] gap-6 px-6 py-8">
      <div className="border-b-2 border-rule-strong pb-2">
        <h1 className="label text-ink">{t('inventory.title')}</h1>
      </div>

      {routes.isPending ? (
        <Placeholders />
      ) : !routes.data ? (
        <p className="max-w-prose text-sm text-ink-dim">{t('inventory.off')}</p>
      ) : routes.data.length === 0 ? (
        <NoRoutes />
      ) : (
        <>
          <nav aria-label={t('inventory.routes')} className="flex flex-wrap gap-2">
            {routes.data.map((row) => (
              <Link
                key={row.slug}
                to="/library/$routeSlug"
                params={{ routeSlug: row.slug }}
                // 換 Route 時篩選不跟著走：那個數字是上一條 Route 的。
                activeOptions={{ exact: true, includeSearch: false }}
                className={SWITCH}
                activeProps={{ className: SWITCH_ACTIVE }}
              >
                {/* Route 名是使用者打的字：`.label` 的大寫會把 `Movies` 印成 `MOVIES`（票 15）。 */}
                <span className="normal-case">{row.name}</span>
                <span className="value text-xs text-ink-dim">
                  {t('inventory.titles', { count: row.titles })}
                </span>
                {!row.enabled && (
                  <span className="label bg-deck px-1.5 py-0.5 text-ink">
                    {t('inventory.disabled')}
                  </span>
                )}
              </Link>
            ))}
          </nav>
          {slug !== null && <Wall slug={slug} filter={filter} routes={routes.data} />}
        </>
      )}

      {/* 牆上的海報與標題來自 TMDB（brief §20.3）。它是法定聲明，不是頁尾裝飾。 */}
      <footer className="flex flex-wrap items-center gap-x-3 gap-y-2 border-t-2 border-rule pt-4">
        <img src={tmdbLogo} alt="TMDB" height={16} className="h-4 w-auto" />
        <p className="max-w-prose text-xs text-ink-dim">{t('discover.attribution')}</p>
      </footer>
    </div>
  )
}

function Wall({
  slug,
  filter,
  routes,
}: {
  slug: string
  filter?: InventoryFilter
  routes: InventoryRoute[]
}) {
  const { t } = useTranslation()
  const wall = useQuery(inventoryQueryOptions(slug))

  if (wall.isPending) return <Placeholders />
  if (!wall.data) {
    if (wall.error instanceof ApiError && wall.error.status === 404) {
      return <UnknownRoute slug={slug} routes={routes} />
    }
    return <p className="max-w-prose text-sm text-ink-dim">{t('inventory.off')}</p>
  }

  const shown = wall.data.items.filter((item) =>
    filter === 'review' ? item.needs_review : filter === 'unmatched' ? item.has_unmatched : true,
  )

  return (
    <section className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
        <Filters slug={slug} route={wall.data.route} />
        {/* 牆換掉了要說得出來——螢幕閱讀器看不到格子從 30 格變成 2 格。 */}
        <p aria-live="polite" className="value text-xs text-ink-dim">
          {t('inventory.showing', { count: shown.length })}
        </p>
      </div>

      {shown.length > 0 ? (
        <div className={WALL_GRID}>
          {shown.map((item) => (
            <InventoryTile key={item.media_id} item={item} web={wall.data.jellyfin} />
          ))}
        </div>
      ) : (
        <Empty inventory={wall.data} slug={slug} filter={filter} />
      )}
    </section>
  )
}

/** 全部 · 待審 N · Unmatched N。數字是後端算的，而且是整條 Route 的，不隨篩選變。 */
function Filters({ slug, route }: { slug: string; route: InventoryRoute }) {
  const { t } = useTranslation()
  const options = [
    { search: {}, label: t('inventory.filter.all') },
    {
      search: { filter: 'review' as const },
      label: t('inventory.filter.review', { count: route.review }),
    },
    {
      search: { filter: 'unmatched' as const },
      label: t('inventory.filter.unmatched', { count: route.unmatched }),
    },
  ]

  return (
    <nav aria-label={t('inventory.filters')} className="flex flex-wrap gap-2">
      {options.map((option) => (
        <Link
          key={option.label}
          to="/library/$routeSlug"
          params={{ routeSlug: slug }}
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

/** 空手而歸的三種樣子，三種下一步（PRODUCT 原則 4：畫面永遠要有下一步）。 */
function Empty({
  inventory,
  slug,
  filter,
}: {
  inventory: Inventory
  slug: string
  filter?: InventoryFilter
}) {
  const { t } = useTranslation()

  return (
    <div className="grid justify-items-start gap-3 border-2 border-rule bg-well px-4 py-4">
      {filter ? (
        <>
          <p className="max-w-prose text-sm text-ink">{t(`inventory.empty.${filter}`)}</p>
          <Link
            to="/library/$routeSlug"
            params={{ routeSlug: slug }}
            search={{}}
            className={GHOST_LINK}
          >
            {t('inventory.empty.showAll')}
          </Link>
        </>
      ) : (
        <>
          <p className="max-w-prose text-sm text-ink">
            {t('inventory.empty.route', { route: inventory.route.name })}
          </p>
          <Link to="/" className={GHOST_LINK}>
            {t('inventory.empty.toDiscover')}
          </Link>
        </>
      )}
    </div>
  )
}

function NoRoutes() {
  const { t } = useTranslation()

  return (
    <div className="grid justify-items-start gap-3 border-2 border-rule bg-well px-4 py-4">
      <p className="max-w-prose text-sm text-ink">{t('inventory.empty.noRoutes')}</p>
      <SetupHint
        berth={4}
        label={t('inventory.empty.toSetup')}
        fallback={t('inventory.empty.askAdmin')}
      />
    </div>
  )
}

/** 網址上的 slug 不存在（Route 改名或被刪了）。說清楚，並給一條到第一條 Route 的路。 */
function UnknownRoute({ slug, routes }: { slug: string; routes: InventoryRoute[] }) {
  const { t } = useTranslation()
  const first = routes.find((row) => row.enabled) ?? routes[0]

  return (
    <div className="grid justify-items-start gap-3 border-2 border-rule bg-well px-4 py-4">
      <p className="max-w-prose text-sm text-ink">{t('inventory.empty.unknown', { slug })}</p>
      {first && (
        <Link to="/library/$routeSlug" params={{ routeSlug: first.slug }} className={GHOST_LINK}>
          {t('inventory.empty.toFirst', { route: first.name })}
        </Link>
      )}
    </div>
  )
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
