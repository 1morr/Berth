import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import {
  deleteSetupRoute,
  type LibraryChoice,
  type RouteSelectionInput,
  type RouteSetup,
} from '../api/setup'
import { type RouteRefusalDetail } from '../api/routes'
import { type RouteView } from '../api/schemas'
import { STICKY_ACTION, Checkbox, GhostButton, Notice, PrimaryButton } from '../components/controls'
import { ROUTE_HEALTH_LABEL, ROUTE_SIGNAL } from '../components/routeChecks'
import { RouteCheckList } from '../components/RouteCheckList'
import { SIGNAL_FILL } from '../components/signal'
import { Cutaway, CutawayRow } from '../components/Cutaway'
import { RouteDelete } from '../components/RouteDelete'

/**
 * 泊位 3：媒體庫路徑 → Library Route（plan §9.3 第 5 步、§9.5）。
 *
 * 套件內 Jellyfin 的三個媒體庫直接導出三個 Route，沒有可選的東西——剖面列的就是將建立的
 * 那三條，而且第一次走到這一格就自動跑（`SetupPage`，票 06d），沒有要按的鍵。既有 Jellyfin
 * 由使用者勾選媒體庫，並從**那個媒體庫自己回報的路徑**裡選寫入目標；想要一條乾淨的
 * Berth 路徑就用「加入 Berth 路徑」（第 3 步的同一支端點，舊路徑原地不動）。
 *
 * 每個 Route 五條纜繩，最後一條真的鏈接一次檔案再比 inode（brief §4.4）。失敗就地展開
 * 那個容器的 compose `volumes:` 片段——這是「哪個容器少了哪個掛載」唯一有用的回答。
 */

/** 使用者對一個媒體庫做的選擇。`Pick` 是 TS 內建型別的名字，所以不用它。 */
interface LibraryPick {
  selected: boolean
  target: string
}

export function RouteStep({
  setup,
  building,
  addingPath,
  requestFailed,
  refusal,
  onBuild,
  onAddPath,
  onRouteDeleted,
  autoBuilding,
  note,
  nav,
}: {
  setup: RouteSetup
  building: boolean
  /** 正在為這個媒體庫加 Berth 路徑（第 3 步的端點）。 */
  addingPath: string | null
  /** 請求本身沒跑完。逐項檢查的失敗在 `routes[].checks` 裡，各自貼在它那一行。 */
  requestFailed: boolean
  /** 後端說不行的那一份。認不得的（或根本不是拒絕）是 `null`，落回一句通用的話。 */
  refusal: RouteRefusalDetail | null
  onBuild: (selections: RouteSelectionInput[]) => void
  onAddPath: (library: string) => void
  /** 一條 Route 被明確地刪掉了（票 14）：這一步的清單要重讀。 */
  onRouteDeleted: () => void
  /**
   * 套件內的自動建立還沒送出或正在跑（票 06d）。跑過之後又把 Route 全刪光的人要拿得到鍵，
   * 所以「一條都沒有」本身不代表自動建立會接手。
   */
  autoBuilding: boolean
  /** 回頭看的說明（`RevisitNote`），這一頁做完了才有。 */
  note?: ReactNode
  /** 上一個 / 下一個泊位（`BerthNav`）。 */
  nav?: ReactNode
}) {
  const { t } = useTranslation()
  const bundled = setup.origin === 'bundled'
  const [picks, setPicks] = useState<Record<string, LibraryPick>>({})
  // 刪掉的那一條連同它的訊息一起卸載，所以「已刪除」由這一層說（票 14a）。
  const [announcement, setAnnouncement] = useState('')
  const routable = setup.libraries.filter((library) => library.supported)

  function pickOf(library: LibraryChoice): LibraryPick {
    return (
      picks[library.name] ?? {
        selected: library.has_route,
        target: library.target_path,
      }
    )
  }

  function change(library: LibraryChoice, patch: Partial<LibraryPick>) {
    setPicks((was) => ({ ...was, [library.name]: { ...pickOf(library), ...patch } }))
  }

  /**
   * 這條路徑已經被誰拿去當寫入目標了（票 03 第 6 條）。兩個來源與 plan §9.3 第 5 步
   * 的略過規則一致：已經存在的 Route，以及**同一批裡前面已經選走它**的別的媒體庫。
   * 自己選的那一條不算佔用，否則勾完就再也改不回來。
   */
  function takenBy(library: LibraryChoice, path: string): string | null {
    const route = setup.routes.find((row) => row.target_path === path)
    if (route) return route.name
    const other = setup.libraries.find(
      (row) => row.name !== library.name && pickOf(row).selected && pickOf(row).target === path,
    )
    return other ? other.name : null
  }

  // 送得出去的只有「勾了、而且目標真的是這個媒體庫的路徑之一」的那幾個：伺服器用同一條
  // 規則擋（回 422），但那時候畫面只說得出「請求沒走完」。最典型的情況是「加入 Berth 路徑」
  // 失敗——那條路徑沒真的加上去，選它就會被退回來。
  const selections = setup.libraries
    .filter((library) => {
      const pick = pickOf(library)
      // 已經有 Route 的媒體庫不送：精靈只新增，不改也不刪（票 14，使用者拍板）。
      return (
        library.supported &&
        !library.has_route &&
        pick.selected &&
        library.locations.includes(pick.target)
      )
    })
    .map((library) => ({ library: library.name, target_path: pickOf(library).target }))
  // 按下去會新建幾條。沒有新的時候這一顆就是「全部重驗」——重跑第 5 步只剩這個意思。
  const fresh = bundled
    ? routable.filter((library) => !library.has_route).length
    : selections.length
  // 套件內第一次走到這一格是自動跑的（票 06d）：沒有要選的東西，那一顆鍵只是儀式。
  // 請求沒走完時才把鍵還給他——那時候總得有辦法再試一次。
  const automatic = bundled && setup.routes.length === 0 && !requestFailed && autoBuilding

  return (
    <div className="grid flex-1 gap-px bg-rule lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
      <div className="min-w-0 bg-hull p-6">
        <div className="lg:sticky lg:top-6">
          <RouteCutaway setup={setup} planned={bundled ? undefined : selections} />
        </div>
      </div>

      <div className="min-w-0 bg-hull p-6">
        <h2 className="text-lg font-semibold text-ink">{t('routes.title')}</h2>
        <p className="mt-2 max-w-prose text-sm text-ink-dim">
          {t(bundled ? 'routes.lede.bundled' : 'routes.lede.existing')}
        </p>
        {note}

        {!bundled &&
          (setup.libraries.length === 0 ? (
            <div className="mt-6">
              {/* Berth 不替既有伺服器建媒體庫（brief §16.4 的紅線），所以這裡沒有動作。 */}
              <Notice signal="assigned" label={t('common.warning')}>
                {t('routes.empty')}
              </Notice>
            </div>
          ) : (
            <LibraryPicker
              libraries={setup.libraries}
              pickOf={pickOf}
              takenBy={takenBy}
              addingPath={addingPath}
              onChange={change}
              onAddPath={(library) => {
                // 按了就是要寫在那裡：路徑加完之後它就是這個媒體庫的寫入目標。
                change(library, { selected: true, target: library.berth_path })
                onAddPath(library.name)
              }}
            />
          ))}

        {automatic ? (
          <p aria-live="polite" className="value mt-6 text-sm text-ink-dim">
            {t('routes.automatic')}
          </p>
        ) : fresh === 0 && setup.ready ? (
          // 全綠、沒有新的可建：這一顆只剩「全部重驗」，是次要的——主要動作是前往下一個泊位。
          <div className="mt-6">
            <GhostButton
              type="button"
              busy={building}
              onClick={() => onBuild(bundled ? [] : selections)}
            >
              {building
                ? t('routes.building')
                : t('routes.recheck', { count: setup.routes.length })}
            </GhostButton>
          </div>
        ) : (
          <div className={`mt-6 ${STICKY_ACTION}`}>
            <PrimaryButton
              type="button"
              busy={building}
              disabled={fresh === 0 && setup.routes.length === 0}
              onClick={() => onBuild(bundled ? [] : selections)}
            >
              {building
                ? t('routes.building')
                : fresh > 0 || setup.routes.length === 0
                  ? t('routes.build', { count: fresh })
                  : t('routes.recheck', { count: setup.routes.length })}
            </PrimaryButton>
          </div>
        )}

        {requestFailed && (
          <div className="mt-4">
            <Notice signal="blocked" label={t('common.failed')}>
              {/* 後端說得出原因的那一種就說原因與下一步（PRODUCT 原則 4），與設定頁上的
                  三處同一個形狀（`RouteDelete`、`AddRoute`、`RouteSettingsPage`）。這一步
                  順帶重跑既有 Route 的檢查，所以 `route_missing` 到得了這裡（M2 票 01）。 */}
              {refusal?.reason === 'route_missing'
                ? t('routes.routeMissing')
                : t('routes.requestFailed')}
            </Notice>
          </div>
        )}

        {/* 先在畫面上、內容再換：`aria-live` 區塊要在變化之前就存在，螢幕閱讀器才念得到。 */}
        <p aria-live="polite" className="mt-4 max-w-prose text-sm text-ink">
          {announcement}
        </p>

        {setup.routes.map((route) => (
          <RouteSequence
            key={route.slug}
            route={route}
            building={building}
            onDeleted={() => {
              setAnnouncement(t('routeSettings.delete.done', { name: route.name }))
              onRouteDeleted()
            }}
          />
        ))}
        {nav}
      </div>
    </div>
  )
}

/** 剖面即預覽：按下去會建立哪幾條 Route，各自寫到哪裡、用哪個 category。 */
function RouteCutaway({
  setup,
  planned,
}: {
  setup: RouteSetup
  /** 既有路徑：使用者現在勾了什麼。套件內是 `undefined`（三條由伺服器導出）。 */
  planned?: RouteSelectionInput[]
}) {
  const { t } = useTranslation()
  // 套件內沒有可選的東西，剖面列的就是伺服器**這一輪**會建的那幾條——只有建得了 Route、而且
  // 還沒有 Route 的媒體庫算數。已經建好的列在右邊；精靈只新增（票 14），剖面若照樣列三條
  // 「將建立」就是在說一件不會發生的事（票 14、14e 留下、票 15 收掉）。
  const rows =
    planned ??
    setup.libraries
      .filter((library) => library.supported && !library.has_route)
      .map((library) => ({ library: library.name, target_path: library.locations[0] ?? '' }))

  return (
    <div className="grid gap-6">
      <Cutaway title={t('routes.cutaway.paths')}>
        <CutawayRow term={t('routes.cutaway.libraryRoot')} value={setup.library_root} />
        <CutawayRow term={t('routes.cutaway.completeRoot')} value={setup.complete_root} />
        <CutawayRow term={t('routes.cutaway.count')} value={String(rows.length)} />
      </Cutaway>

      {rows.length > 0 && (
        <section className="border-2 border-rule bg-well">
          <h3 className="label border-b-2 border-rule bg-deck px-4 py-2.5 text-ink-dim">
            {t('routes.cutaway.plan')}
          </h3>
          <table className="w-full table-fixed border-collapse text-left">
            <thead>
              <tr className="border-b-2 border-rule">
                <th scope="col" className="label px-4 py-2 text-ink-dim">
                  {t('routes.cutaway.library')}
                </th>
                <th scope="col" className="label px-4 py-2 text-ink-dim">
                  {t('routes.cutaway.target')}
                </th>
                <th scope="col" className="label px-4 py-2 text-ink-dim">
                  {t('routes.cutaway.category')}
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-rule">
              {rows.map((row) => (
                <tr key={row.library}>
                  <th scope="row" className="value px-4 py-3 text-xs font-normal wrap-anywhere">
                    {row.library}
                  </th>
                  <td className="value px-4 py-3 text-xs wrap-anywhere text-ink">
                    {row.target_path || '—'}
                  </td>
                  <td className="value px-4 py-3 text-xs wrap-anywhere text-ink-dim">
                    {categoryOf(setup, row.library)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  )
}

/**
 * category 名稱是伺服器算的（`berth-<slug>`）。已經建過的 Route 顯示它真的用的那一個，
 * 還沒建的就先留白——這裡不重寫一份 slug 演算法，兩份遲早會分岔。
 */
function categoryOf(setup: RouteSetup, library: string): string {
  return setup.routes.find((route) => route.library === library)?.category ?? '—'
}

/** 既有 Jellyfin：勾媒體庫、選寫入目標（brief §4.3）。路徑用選的，不用打的。 */
function LibraryPicker({
  libraries,
  pickOf,
  takenBy,
  addingPath,
  onChange,
  onAddPath,
}: {
  libraries: LibraryChoice[]
  pickOf: (library: LibraryChoice) => LibraryPick
  /** 這條路徑被誰佔著（對這個媒體庫而言）。`null` 代表還空著。 */
  takenBy: (library: LibraryChoice, path: string) => string | null
  addingPath: string | null
  onChange: (library: LibraryChoice, patch: Partial<LibraryPick>) => void
  onAddPath: (library: LibraryChoice) => void
}) {
  const { t } = useTranslation()

  return (
    <section className="mt-6">
      <h3 className="label text-ink-dim">{t('routes.picker.title')}</h3>
      <p className="mt-2 max-w-prose text-sm text-ink-dim">{t('routes.picker.lede')}</p>

      <ul className="mt-4 grid gap-3">
        {libraries.map((library) => {
          const pick = pickOf(library)

          return (
            <li key={library.name} className="min-w-0 border-2 border-rule bg-well px-4 py-3">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                {library.supported ? (
                  <Checkbox
                    label={library.name}
                    checked={library.has_route || pick.selected}
                    disabled={library.has_route}
                    onChange={(selected) => onChange(library, { selected })}
                  />
                ) : (
                  <span className="text-sm text-ink-dim">{library.name}</span>
                )}
                {/* 機器字串（Jellyfin 的 collection type）走 `.value`：`.label` 會把它大寫掉。 */}
                <span className="value ml-auto text-xs text-ink-dim">
                  {library.collection_type || t('routes.picker.mixed')}
                </span>
              </div>

              {!library.supported && (
                <p className="mt-2 max-w-prose text-xs text-ink-dim">
                  {t('routes.picker.unsupported')}
                </p>
              )}
              {library.uses_tvdb && (
                <p className="mt-2 max-w-prose text-xs text-ink-dim">{t('routes.picker.tvdb')}</p>
              )}

              {library.has_route && (
                <p className="mt-2 max-w-prose text-xs text-ink-dim">{t('routes.picker.routed')}</p>
              )}
              {library.supported && !library.has_route && pick.selected && (
                <div className="mt-3 grid gap-3 border-t-2 border-rule pt-3">
                  <Targets
                    library={library}
                    target={pick.target}
                    takenBy={(path) => takenBy(library, path)}
                    onPick={(target) => onChange(library, { target })}
                  />
                  {!library.has_berth_path && (
                    <div>
                      <GhostButton
                        type="button"
                        busy={addingPath !== null}
                        onClick={() => onAddPath(library)}
                      >
                        {addingPath === library.name
                          ? t('routes.picker.adding')
                          : t('routes.picker.addBerthPath')}
                      </GhostButton>
                      <p className="mt-2 max-w-prose text-xs text-ink-dim">
                        {t('routes.picker.addHint', { path: library.berth_path })}
                      </p>
                    </div>
                  )}
                </div>
              )}
            </li>
          )
        })}
      </ul>
    </section>
  )
}

/**
 * 這個媒體庫回報的路徑，選一條當寫入目標。其他的仍然唯讀（brief §4.3）。
 *
 * **已經被佔用的選不了**（票 03 第 6 條）：同一個目標兩條 Route，帳本就認不出檔案是誰的，
 * 所以後端本來就會擋（plan §9.3 第 5 步：被別的 Route 或同一批前面的選擇佔走的一律略過）。
 * 在按下去之前就說出來——`/settings/routes` 的新增表是同一個做法。
 */
function Targets({
  library,
  target,
  takenBy,
  onPick,
}: {
  library: LibraryChoice
  target: string
  /** 路徑 → 佔著它的那條 Route（或同一批裡先選走它的媒體庫）的名字。 */
  takenBy: (path: string) => string | null
  onPick: (target: string) => void
}) {
  const { t } = useTranslation()

  if (library.locations.length === 0) {
    return <p className="text-xs text-ink-dim">{t('routes.picker.noPath')}</p>
  }

  return (
    <fieldset className="grid gap-2">
      <legend className="label text-ink-dim">{t('routes.picker.target')}</legend>
      {library.locations.map((location) => {
        const holder = takenBy(location)
        const takenId = `taken-${library.name}-${location}`
        return (
          <label key={location} className="flex flex-wrap items-start gap-x-3 gap-y-1">
            <input
              type="radio"
              name={`target-${library.name}`}
              value={location}
              checked={target === location}
              disabled={holder !== null}
              aria-describedby={holder !== null ? takenId : undefined}
              onChange={() => onPick(location)}
              className="mt-0.5 size-4 shrink-0 accent-[var(--color-assigned)] disabled:cursor-not-allowed"
            />
            <span className="value min-w-0 text-xs wrap-anywhere text-ink">{location}</span>
            {holder !== null && (
              <span id={takenId} className="text-xs text-ink-dim">
                {t('routeSettings.add.taken', { name: holder })}
              </span>
            )}
          </label>
        )
      })}
    </fieldset>
  )
}

/** 一個 Route 的靠泊序列：五條纜繩，失敗就地展開手動步驟與 compose 片段。 */
function RouteSequence({
  route,
  building,
  onDeleted,
}: {
  route: RouteView
  building: boolean
  onDeleted: () => void
}) {
  const { t } = useTranslation()

  return (
    <section className="mt-6">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <span className={`label px-2 py-1.5 ${SIGNAL_FILL[ROUTE_SIGNAL[route.health]]}`}>
          {t(ROUTE_HEALTH_LABEL[route.health])}
        </span>
        <span className="value text-sm font-semibold text-ink">{route.name}</span>
        <span className="value text-xs text-ink-dim">{route.category}</span>
        <span className="value ml-auto min-w-0 truncate text-xs text-ink-dim">
          {route.target_path}
        </span>
      </div>

      <div className="mt-3">
        <RouteCheckList route={route} busy={building} />
      </div>
      {/* 精靈只新增不改不刪；選錯了、紅燈卡住時的出路是明確地刪掉這一條（票 14）。
          打的是精靈自己的那一支，跟著精靈的門禁；停用在 Route 設定頁，這裡不給（票 14a）。 */}
      <div className="mt-3">
        <RouteDelete
          route={route}
          onDelete={() => deleteSetupRoute(route.id)}
          onChanged={onDeleted}
        />
      </div>
    </section>
  )
}
