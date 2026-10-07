import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { formatList } from '../i18n/list'

import { RequestFailed } from '../components/RequestFailed'
import { useFadingNote } from '../components/useFadingNote'

import {
  deleteSetupRoute,
  type JellyfinSetup,
  type LibraryChoice,
  type LibraryDraft,
  type RouteSelectionInput,
  type RouteSetup,
} from '../api/setup'
import { type RouteView } from '../api/schemas'
import { STICKY_ACTION, Checkbox, GhostButton, Notice, PrimaryButton } from '../components/controls'
import { Cutaway, CutawayRow } from '../components/Cutaway'
import { RouteCheckList } from '../components/RouteCheckList'
import { checking, type ExistingServices } from '../components/routeChecks'
import { RouteDelete } from '../components/RouteDelete'
import { RouteRow } from '../components/RouteRow'
import { jellyfinAddressQueryOptions } from '../api/settings'
import { jellyfinLibrariesUrl } from '../inventory/jellyfinLink'
import { SIGNAL_FILL } from '../components/signal'
import { StepLine } from '../components/StepLine'
import { TechnicalDetails } from '../components/TechnicalDetails'
import { BUILD_REFUSAL, type BuildRefusal } from './buildRefusal'
import { BundledLibraries } from './BundledLibraries'
import { AddPathFailures } from './JellyfinExisting'
import { librariesFailed } from './jellyfinSteps'
import { previewUnder } from './libraryRules'
import { StepFrame } from './StepFrame'
import { useLibraryDraft } from './useLibraryDraft'

/**
 * 頁 3「媒體庫與路徑」（plan §9.3 頁 3、§9.5；M4 票 08，`.scratch/m4/route-berth-shape.md`）。
 *
 * **一顆鈕做完**：這一頁會建媒體庫、在 Jellyfin 加路徑、建 qBittorrent 分類、寫探測檔與硬鏈接測試檔，
 * 按之前把這一輪會做的事列出來（`DockPreview`）。套件內這一顆也建清單上還沒建的媒體庫；既有 Jellyfin 的
 * Berth 路徑是寫入目標的一個選項，按下時才加——沒有「確認加入」那種做了一半、走得過去的狀態（使用者拍板）。
 * **套件內什麼都還沒做時進頁就自己跑一次**（M4 票 43，`.scratch/m4/route-auto-run-shape.md`；判定在
 * `autoDock.startsOnItsOwn`）：那裡沒有選擇要做。既有照舊由人按。
 *
 * 按下之後的順序在 `SetupPage` 的 `dock`：一段失敗就停，後面的不送。跑的時候這一輪的每條 Route 先畫成
 * 一列（還沒輪到的「等待中」），跑到哪一條纜繩就說哪一條。每條 Route 收成一列，紅的自己打開（`RouteRow`）；
 * 失敗說出哪個容器少了哪個掛載，既有服務另說同主機、同容器路徑的條件。
 */

/** 按下「建立並檢查」要做的事，照順序。 */
export type DockPlan =
  | {
      origin: 'bundled'
      /**
       * 先存這一份清單（`bootstrap` 讀的是存下來的那一份）。建不建媒體庫看存下之後回來的「已建立」：
       * 與後端判定頁 3 的是同一條（`libraries_built`，M4 票 24）。
       */
      libraries: LibraryDraft[]
      /** 進頁自己開跑的那一次（M4 票 43）：畫面說一句為什麼沒按就開始了。 */
      onItsOwn?: boolean
    }
  | {
      origin: 'existing'
      /** 按下時先替這幾個媒體庫加 Berth 路徑（plan §9.5）。 */
      newPaths: string[]
      selections: RouteSelectionInput[]
    }

/**
 * 請求沒走完的那一種。後端的拒絕說得出原因就說原因（PRODUCT 原則 4）；其餘照請求的失敗分類說
 * （`RequestFailed`，M4 票 21）——選擇無效的 422 原本也說成「Berth 後端可能沒在跑」。
 */
export type DockFailure =
  | { kind: 'route_missing' }
  | { kind: 'refused'; reason: BuildRefusal; detail: string }
  | { kind: 'request'; error: unknown }

/** 這一輪會新建的一條 Route：哪個媒體庫、寫到哪裡。剖面列它。 */
interface Planned {
  library: string
  target: string
}

interface Common {
  setup: RouteSetup
  /**
   * 這一頁做完了（後端已經過了它）：「前往下一個泊位」出現、而且固定在底部，這一頁的主鈕降成
   * 次要、不再固定——兩個 sticky 會疊在同一個位置，一屏也不能有兩顆 `assigned`（code-review）。
   */
  done: boolean
  /** 使用者自己的那幾台：它們的檢查失敗時另說改掛載（票 08）。 */
  existing: ExistingServices
  docking: boolean
  /** 這一頁的建立是進頁自己開跑的（M4 票 43）：說一句為什麼沒按就開始了，留到人自己按為止。 */
  startedOnItsOwn: boolean
  failure: DockFailure | null
  onDock: (plan: DockPlan) => void
  /** 一條 Route 被明確地刪掉了（票 14）：這一步的清單與精靈的進度要重讀（M4 票 24）。 */
  onRouteDeleted: (route: RouteView) => void
  /** 進頁時向 Jellyfin 重讀媒體庫（M4 票 19；套件內也是，票 24）。重讀中、讀不到時說出來。 */
  reread: { pending: boolean; failed: boolean; onReread: () => void }
  /** 回頭看的說明（`RevisitNote`），這一頁做完了才有。 */
  note?: ReactNode
  /** 上一個 / 下一個泊位（`BerthNav`）。 */
  nav?: ReactNode
}

export function RouteStep({
  jellyfin,
  onSaveLibraries,
  savingLibraries,
  saveLibrariesFailed,
  ...common
}: Common & {
  /** 套件內的清單、建媒體庫那一步與版本；既有的「加路徑」失敗也記在它的 `libraries` 那一步。 */
  jellyfin: JellyfinSetup
  /** 清單停手就存（票 06f）。 */
  onSaveLibraries: (libraries: LibraryDraft[]) => void
  savingLibraries: boolean
  /** 清單存不下來的那一句，沒有就是 `null`。 */
  saveLibrariesFailed: string | null
}) {
  return common.setup.origin === 'bundled' ? (
    <BundledRoutes
      {...common}
      jellyfin={jellyfin}
      onSaveLibraries={onSaveLibraries}
      saving={savingLibraries}
      saveFailed={saveLibrariesFailed}
    />
  ) : (
    <ExistingRoutes {...common} jellyfin={jellyfin} />
  )
}

/** 套件內：你列的媒體庫一個一條 Route，沒有要選的東西。 */
function BundledRoutes({
  jellyfin,
  onSaveLibraries,
  saving,
  saveFailed,
  ...common
}: Common & {
  jellyfin: JellyfinSetup
  onSaveLibraries: (libraries: LibraryDraft[]) => void
  saving: boolean
  saveFailed: string | null
}) {
  const { t } = useTranslation()
  const { setup, docking } = common
  // 它只在清單真的被改過時才存。
  const draft = useLibraryDraft(jellyfin, onSaveLibraries)
  const unbuilt = draft.rows.filter((row) => !row.built)
  // 清單上、已經在 Jellyfin 上、還沒有 Route 的（建過媒體庫、Route 被刪掉的也是這一種）。使用者
  // 自己在 Jellyfin 加的不算：後端只替清單上的建 Route（`listed`，M4 票 24）。
  // 照清單的順序列（M4 票 31）：Jellyfin 照字母回報，後端建 Route 也照清單排（`_bundled_selections`）。
  const order = (name: string) => {
    const index = draft.rows.findIndex((row) => row.name.trim() === name)
    return index === -1 ? draft.rows.length : index
  }
  const unrouted = setup.libraries
    .filter((library) => library.listed && library.supported && !library.has_route)
    .sort((a, b) => order(a.name) - order(b.name))
  // 建媒體庫那一段：在跑時說在跑（M4 票 43），紅了就地說原文與手動步驟。
  const libraries =
    librariesFailed(jellyfin) ??
    jellyfin.steps.find((row) => row.step === 'libraries' && row.status === 'running')
  const names = unbuilt.map((row) => row.name.trim()).filter(Boolean)
  // 手動步驟開在瀏覽器開得了的位址上（`jellyfinLink.ts`，M4 票 54）：Berth 連它的是 compose 內網那一條。
  // 走到失敗才問；推不出來時只留文字。
  const address = useQuery({
    ...jellyfinAddressQueryOptions,
    enabled: libraries?.status === 'failed',
  })
  const manual = address.data ? jellyfinLibrariesUrl(address.data, window.location) : null

  return (
    <RoutePage
      {...common}
      lede={t('routes.lede.bundled')}
      planned={[
        ...unrouted.map((library) => ({
          library: library.name,
          target: library.locations[0] ?? '',
        })),
        ...unbuilt.map((row) => ({
          library: row.name.trim() || '—',
          target: previewUnder(jellyfin.library_root, row.folder),
        })),
      ]}
      fresh={unrouted.length + unbuilt.length}
      preview={
        unbuilt.length > 0
          ? [<LibrariesLine key="libraries" count={unbuilt.length} names={names} />]
          : []
      }
      blocked={draft.blocked ? t('routes.dock.listBlocked') : null}
      onPress={() =>
        common.onDock({
          origin: 'bundled',
          libraries: draft.drafts,
        })
      }
    >
      {!jellyfin.version_supported && <VersionNotice version={jellyfin.version} />}
      <Reread {...common.reread} count={common.setup.libraries.length} />
      {/* 清單全部建好了就收成一列，要加一個再展開（shape）；還有沒建的就打開。**永遠是同一個
          `<details>`**：兩種樣子換元件的話，展開後按「加一個媒體庫」清單會被重新掛載，焦點掉回 body
          （code-review）。`open` 只在「有沒有沒建的」變了時才動，使用者自己開關的不蓋掉。 */}
      {/* 跑的時候收起（鎖著也改不了）；自動跑的那一次因此一開始就是收著的「預設 3 個」（M4 票 43）。 */}
      <details open={unbuilt.length > 0 && !docking} className="group mt-6">
        <summary className="flex cursor-pointer flex-wrap items-center gap-x-3 gap-y-2 border-2 border-rule bg-well px-4 py-3">
          <span className="label text-ink-dim">{t('routes.listSummary')}</span>
          <span className="value text-xs text-ink">
            {unbuilt.length > 0
              ? t('routes.listPending', { count: unbuilt.length })
              : t('routes.listBuilt', { count: draft.rows.length })}
          </span>
          <span className="label ml-auto text-ink-dim group-open:hidden">{t('common.expand')}</span>
          <span className="label ml-auto hidden text-ink-dim group-open:inline">
            {t('common.collapse')}
          </span>
        </summary>
        {/* 清單自己有框：摘要一條、清單一塊，不疊兩層框。 */}
        <div className="mt-3">
          <BundledLibraries
            draft={draft}
            libraryRoot={jellyfin.library_root}
            locked={docking}
            saving={saving}
            saveFailed={saveFailed}
          />
        </div>
      </details>
      {libraries && (
        <ol className="mt-4 grid gap-3">
          <StepLine
            label={t('jellyfin.step.libraries')}
            service="Jellyfin"
            endpoint="POST /Library/VirtualFolders"
            row={libraries}
            fix={t('jellyfin.fix.libraries')}
            commands={manual ? [manual] : []}
          >
            <p className="mt-3 text-xs text-ink-dim">{t('routes.dock.retryHint')}</p>
          </StepLine>
        </ol>
      )}
    </RoutePage>
  )
}

function LibrariesLine({ count, names }: { count: number; names: string[] }) {
  const { t, i18n } = useTranslation()
  const list = names.length > 0 ? formatList(names, i18n.language) : '—'
  return <>{t('routes.dock.libraries', { count, names: list })}</>
}

/**
 * 版本太舊（brief §16.4、§19、§20.9）。**擺在清單之前**：升級之前按幾次都是同一個結果，而升級是
 * 不可逆的，那幾件先做的事要在按之前就看得到。
 */
function VersionNotice({ version }: { version: string }) {
  const { t } = useTranslation()

  return (
    <div className="mt-4 grid gap-2">
      <Notice signal="blocked" label={t('jellyfin.version.label')}>
        {t('jellyfin.version.current', { version })}
      </Notice>
      <p className="max-w-prose text-xs text-ink-dim">{t('jellyfin.version.why')}</p>
      <p className="max-w-prose text-xs text-ink">{t('jellyfin.version.upgrade')}</p>
    </div>
  )
}

/** 使用者對一個媒體庫做的選擇。`Pick` 是 TS 內建型別的名字，所以不用它。 */
interface LibraryPick {
  selected: boolean
  target: string
}

/**
 * 既有 Jellyfin：勾媒體庫、從**那個媒體庫自己回報的路徑**裡選寫入目標（brief §4.3）。還沒有 Berth 路徑的
 * 媒體庫，Berth 路徑是多出來的一個選項，按下時才加（plan §9.5：舊路徑原地不動）。
 */
function ExistingRoutes({ jellyfin, ...common }: Common & { jellyfin: JellyfinSetup }) {
  const { t } = useTranslation()
  const { setup } = common
  const [picks, setPicks] = useState<Record<string, LibraryPick>>({})

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

  /** Route 刪掉了：它的媒體庫回到沒勾的樣子，否則下一次「建立並檢查」又把它送出去（M4 票 24）。 */
  function forget(route: RouteView) {
    setPicks((was) =>
      Object.fromEntries(Object.entries(was).filter(([name]) => name !== route.library)),
    )
    common.onRouteDeleted(route)
  }

  /**
   * 這條路徑已經被誰拿去當寫入目標了（票 03 第 6 條）。兩個來源與後端的略過規則一致：已經存在的
   * Route，以及**同一批裡前面已經選走它**的別的媒體庫。自己選的那一條不算佔用，否則勾完就再也改不回來。
   */
  function takenBy(library: LibraryChoice, path: string): string | null {
    const route = setup.routes.find((row) => row.target_path === path)
    if (route) return route.name
    const other = setup.libraries.find(
      (row) => row.name !== library.name && pickOf(row).selected && pickOf(row).target === path,
    )
    return other ? other.name : null
  }

  // 已經有 Route 的媒體庫不送：精靈只新增，不改也不刪（票 14，使用者拍板）。
  const ticked = setup.libraries.filter(
    (library) => library.supported && !library.has_route && pickOf(library).selected,
  )
  // 送得出去的是「目標是這個媒體庫的路徑之一，或按下時才加的 Berth 路徑」：伺服器用同一條規則擋
  // （回 422），但那時候畫面只說得出「請求沒走完」。
  const ready = ticked.filter((library) => {
    const target = pickOf(library).target
    return library.locations.includes(target) || isNewBerthPath(library, target)
  })
  const missing = ticked.find((library) => !ready.includes(library))
  const newPaths = ready.filter((library) => isNewBerthPath(library, pickOf(library).target))
  const selections = ready.map((library) => ({
    library: library.name,
    target_path: pickOf(library).target,
  }))
  return (
    <RoutePage
      {...common}
      onRouteDeleted={forget}
      lede={t('routes.lede.existing')}
      planned={selections.map((row) => ({ library: row.library, target: row.target_path }))}
      fresh={selections.length}
      preview={newPaths.map((library) => (
        <span key={library.name}>
          {t('routes.dock.berthPath', { library: library.name, path: library.berth_path })}
        </span>
      ))}
      blocked={
        missing
          ? t('routes.dock.pickTarget', { library: missing.name })
          : selections.length === 0 && setup.routes.length === 0
            ? t('routes.dock.pickOne')
            : null
      }
      onPress={() =>
        common.onDock({
          origin: 'existing',
          newPaths: newPaths.map((library) => library.name),
          selections,
        })
      }
    >
      <Reread {...common.reread} count={setup.libraries.length} />
      {setup.libraries.length === 0 ? (
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
          onChange={change}
        />
      )}
      {/* 加路徑沒加上的那幾個，一個一條：原因與怎麼改掛載（plan §9.5、票 19）。建 Route 那一段沒有送出。 */}
      {/* 只說還選著「新的 Berth 路徑」的那幾個：改選既有資料夾之後，上一次的失敗已經不是這一輪的事。 */}
      <AddPathFailures
        results={jellyfin.berth_paths.filter((row) =>
          newPaths.some((library) => library.name === row.library),
        )}
        root={common.existing.root}
      />
    </RoutePage>
  )
}

/**
 * 頁 1 之後在 Jellyfin 改的掛載、路徑與媒體庫要看得到（M4 票 19；套件內也是，票 24）：進頁就重讀一次，
 * 也可以再按。
 */
/**
 * 「重新讀取」。讀到了也說一聲（M4 票 31，實測 #33：清單沒變時按下去像沒反應）：只在人按的那一次說，
 * 進頁自動的那一次不說。`count` 是讀回來之後清單上的媒體庫數。
 */
function Reread({ pending, failed, onReread, count }: Common['reread'] & { count: number }) {
  const { t } = useTranslation()
  const [note, setNote] = useFadingNote()
  const pressed = useRef(false)

  useEffect(() => {
    if (pending || !pressed.current) return
    pressed.current = false
    if (!failed) setNote(t('routes.rereadDone', { count }))
  }, [pending, failed, count, setNote, t])

  return (
    <div className="mt-6 flex flex-wrap items-center gap-x-4 gap-y-2">
      <GhostButton
        type="button"
        busy={pending}
        onClick={() => {
          pressed.current = true
          setNote('')
          onReread()
        }}
      >
        {pending ? t('routes.rereading') : t('routes.reread')}
      </GhostButton>
      {failed && <p className="text-xs text-blocked-ink">{t('routes.rereadFailed')}</p>}
      <p aria-live="polite" className="text-xs text-ink-dim">
        {note}
      </p>
    </div>
  )
}

/** 這個目標是還沒加到 Jellyfin 上的 Berth 路徑：按下「建立並檢查」時才加。 */
function isNewBerthPath(library: LibraryChoice, target: string): boolean {
  return !library.has_berth_path && target === library.berth_path
}

/** 兩種來源共用的那一半：剖面、「按下之後會」、主鈕、請求失敗、Route 列。 */
function RoutePage({
  setup,
  done,
  existing,
  docking,
  startedOnItsOwn,
  failure,
  onRouteDeleted,
  note,
  nav,
  lede,
  planned,
  fresh,
  preview,
  blocked,
  onPress,
  children,
}: Common & {
  lede: string
  planned: Planned[]
  /** 按下去會新建幾條。沒有新的時這一顆就是「全部重驗」。 */
  fresh: number
  /** 這一種來源自己要先做的事（建媒體庫、加路徑），排在分類與測試檔之前。 */
  preview: ReactNode[]
  /** 還差哪一步，說得出來就擋住主鈕。 */
  blocked: string | null
  onPress: () => void
  children: ReactNode
}) {
  const { t } = useTranslation()
  const [announcement, setAnnouncement] = useFadingNote()
  const total = setup.routes.length + fresh
  // 做完了：主要動作是前往下一個泊位，這一顆（重驗、或回頭補建）是次要的
  // （每屏一顆 `assigned`，票 15 的 critique）。
  const quiet = done
  const Button = quiet ? GhostButton : PrimaryButton
  const label = docking
    ? t('routes.docking')
    : fresh > 0 || setup.routes.length === 0
      ? t('routes.dock.build')
      : t('routes.recheck', { count: setup.routes.length })

  const action = (
    <>
      <DockPreview items={preview} total={total} yours={existing.qbittorrent} />
      <div className={`mt-4 ${quiet ? '' : STICKY_ACTION}`}>
        {blocked && <p className="mb-3 text-xs text-blocked-ink">{blocked}</p>}
        <Button
          type="button"
          busy={docking}
          disabled={blocked !== null || total === 0}
          onClick={onPress}
        >
          {label}
        </Button>
      </div>

      {failure && (
        <div className="mt-4">
          {/* 這一步順帶重跑既有 Route 的檢查，所以 `route_missing` 到得了這裡（M2 票 01）。 */}
          {failure.kind === 'route_missing' ? (
            <Notice signal="blocked" label={t('common.failed')}>
              {t('routes.routeMissing')}
            </Notice>
          ) : failure.kind === 'refused' ? (
            <div className="grid gap-1">
              <Notice signal="blocked" label={t('common.failed')}>
                {t(BUILD_REFUSAL[failure.reason])}
              </Notice>
              <TechnicalDetails lines={[failure.detail]} />
            </div>
          ) : (
            <RequestFailed error={failure.error} />
          )}
        </div>
      )}
    </>
  )

  // 跑的時候這一輪會建、還沒建出來的 Route 先佔一列（M4 票 43）：一開始就看得到總共有幾條、輪到誰。
  // **用開跑那一刻的 `planned`**：建完媒體庫、Route 還沒建出來的那一下，快照裡兩邊都沒有它們，照當下
  // 算的話那幾列會消失再冒出來。
  const [atStart, setAtStart] = useState({ docking, planned })
  if (atStart.docking !== docking) setAtStart({ docking, planned })
  const waiting = docking
    ? atStart.planned.filter((row) => !setup.routes.some((route) => route.library === row.library))
    : []
  // 這一輪還在跑：這一頁送出的，或伺服器說有纜繩在跑（跑到一半重新整理，這一頁沒有送出中的請求）。
  const running = docking || setup.routes.some(checking)
  const rows = (setup.routes.length > 0 || waiting.length > 0) && (
    <ul className="mt-4 grid gap-3" aria-label={t('routes.list')} aria-busy={running}>
      {setup.routes.map((route) => (
        <li key={route.slug} className="min-w-0">
          <RouteRow
            route={route}
            attention={route.health === 'failed'}
            extra={
              running && route.checks.length === 0 ? (
                <span className="label shrink-0 text-ink-dim">{t('routes.waiting')}</span>
              ) : undefined
            }
            expandLabel={t('common.expand')}
            collapseLabel={t('common.collapse')}
          >
            <RouteCheckList route={route} busy={docking} existing={existing} />
            {/* 精靈只新增不改不刪；選錯了、紅燈卡住時的出路是明確地刪掉這一條（票 14）。
                打的是精靈自己的那一支，跟著精靈的門禁；停用在 Route 設定頁，這裡不給（票 14a）。 */}
            <RouteDelete
              route={route}
              onDelete={() => deleteSetupRoute(route.id)}
              onChanged={() => {
                setAnnouncement(t('routeSettings.delete.done', { name: route.name }))
                onRouteDeleted(route)
              }}
            />
          </RouteRow>
        </li>
      ))}
      {waiting.map((row, index) => (
        <li key={`waiting-${row.library}-${index}`} className="min-w-0">
          <WaitingRow planned={row} />
        </li>
      ))}
    </ul>
  )

  return (
    <StepFrame cutaway={<RouteCutaway setup={setup} planned={planned} />}>
      <h2 className="text-lg font-semibold text-ink">{t('routes.title')}</h2>
      <p className="mt-2 max-w-prose text-sm text-ink-dim">{lede}</p>
      {note}
      {children}

      {/* 先在畫面上、內容再換：`aria-live` 區塊要在變化之前就存在，螢幕閱讀器才念得到。 */}
      <p aria-live="polite" className="mt-4 max-w-prose text-sm text-ink">
        {announcement || (startedOnItsOwn ? t('routes.autoRun') : '')}
      </p>
      {/* 做完了（全過、沒有新的）：結果在前，重新檢查是次要的、排在後面。還有事要做時，動作在前。 */}
      {quiet ? (
        <>
          {rows}
          {action}
        </>
      ) : (
        <>
          {action}
          {rows}
        </>
      )}
      {nav}
    </StepFrame>
  )
}

/**
 * 這一輪會建、還沒建出來的一條 Route（M4 票 43）：與 `RouteRow` 的摘要列同一個框與排法，只有名稱與寫入
 * 目標——分類與檢查結果要等它真的建出來。不能展開：底下還沒有東西。
 */
function WaitingRow({ planned }: { planned: Planned }) {
  const { t } = useTranslation()

  return (
    <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-2 border-2 border-rule bg-well px-4 py-3">
      <span className={`label px-2 py-1.5 ${SIGNAL_FILL.neutral}`}>{t('routes.waiting')}</span>
      <span className="value text-sm font-semibold text-ink">{planned.library}</span>
      <span className="value min-w-0 grow wrap-anywhere text-xs text-ink-dim">
        {planned.target || '—'}
      </span>
    </div>
  )
}

/**
 * 「按下之後會」（票 08）：這一輪真的會做的事，數字照目前的選擇算。分類與測試檔每條 Route 都有，
 * 包括已經建好的那幾條——重新檢查一樣會核對分類、寫測試檔再刪掉。
 */
/**
 * `yours`：qBittorrent 是使用者自己的那一台。探測 torrent 校驗到 100% 會觸發「完成時執行外部程式」，
 * 只有那一台可能設了它；套件內那一台是 Berth 自己設的，不提（M4 票 31）。
 */
function DockPreview({
  items,
  total,
  yours,
}: {
  items: ReactNode[]
  total: number
  yours: boolean
}) {
  const { t } = useTranslation()
  if (total === 0) return null

  return (
    <section aria-labelledby="dock-preview" className="mt-6">
      <h3 id="dock-preview" className="label text-ink-dim">
        {t('routes.dock.title')}
      </h3>
      <ul className="mt-2 grid max-w-prose list-disc gap-1 pl-5 text-xs text-ink">
        {items.map((item, index) => (
          <li key={index}>{item}</li>
        ))}
        <li>{t('routes.dock.categories', { count: total })}</li>
        <li>{t(yours ? 'routes.dock.probesYours' : 'routes.dock.probes', { count: total })}</li>
      </ul>
    </section>
  )
}

/**
 * 剖面只放 Route 列沒有的（票 15 的 critique：原本把纜繩列的端點再列一遍）：兩個根目錄，以及這一輪會
 * 新建的 Route 寫到哪裡。建好的那幾條在右邊自己有一列，這裡不再說一次；沒有新的就不畫那張表。
 */
function RouteCutaway({ setup, planned }: { setup: RouteSetup; planned: Planned[] }) {
  const { t } = useTranslation()

  return (
    <div className="grid gap-6">
      <Cutaway title={t('routes.cutaway.paths')}>
        <CutawayRow term={t('routes.cutaway.libraryRoot')} value={setup.library_root} />
        <CutawayRow term={t('routes.cutaway.completeRoot')} value={setup.complete_root} />
      </Cutaway>

      {planned.length > 0 && (
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
              </tr>
            </thead>
            <tbody className="divide-y divide-rule">
              {planned.map((row, index) => (
                <tr key={`${row.library}-${index}`}>
                  <th scope="row" className="value px-4 py-3 text-xs font-normal wrap-anywhere">
                    {row.library}
                  </th>
                  <td className="value px-4 py-3 text-xs wrap-anywhere text-ink">
                    {row.target || '—'}
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

/** 既有 Jellyfin：勾媒體庫、選寫入目標（brief §4.3）。路徑用選的，不用打的。 */
function LibraryPicker({
  libraries,
  pickOf,
  takenBy,
  onChange,
}: {
  libraries: LibraryChoice[]
  pickOf: (library: LibraryChoice) => LibraryPick
  /** 這條路徑被誰佔著（對這個媒體庫而言）。`null` 代表還空著。 */
  takenBy: (library: LibraryChoice, path: string) => string | null
  onChange: (library: LibraryChoice, patch: Partial<LibraryPick>) => void
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
                {/* 認得的類型說人話（M4 票 21：原本顯示 movies / tvshows）；Berth 不支援的類型照 Jellyfin
                    的字面，走 `.value`——`.label` 會把它大寫掉。 */}
                <span className="value ml-auto text-xs text-ink-dim">
                  {library.collection_type === 'movies' || library.collection_type === 'tvshows'
                    ? t(`jellyfin.bundled.list.types.${library.collection_type}`)
                    : library.collection_type || t('routes.picker.mixed')}
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
                <div className="mt-3 border-t-2 border-rule pt-3">
                  <Targets
                    library={library}
                    target={pick.target}
                    takenBy={(path) => takenBy(library, path)}
                    onPick={(target) => onChange(library, { target })}
                  />
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
 * 這個媒體庫回報的路徑，選一條當寫入目標。其他的仍然唯讀（brief §4.3）。還沒有 Berth 路徑的，多一個
 * 「新的」選項：選它就是要 Berth 按下時替這個媒體庫加上那一條（票 08，使用者拍板併進同一顆鈕）。
 *
 * **已經被佔用的選不了**（票 03 第 6 條）：同一個目標兩條 Route，帳本就認不出檔案是誰的，所以後端本來
 * 就會擋。在按下去之前就說出來——`/settings/routes` 的新增表是同一個做法。
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
  // 說明的 id 不能用媒體庫名或路徑拼：`aria-describedby` 以空白分隔，「TV Shows」就斷成兩個 id（code-review）。
  const idBase = useId()
  const options = library.has_berth_path
    ? library.locations
    : [...library.locations, library.berth_path]

  return (
    <fieldset className="grid gap-2">
      <legend className="label text-ink-dim">{t('routes.picker.target')}</legend>
      {library.locations.length === 0 && (
        <p className="text-xs text-ink-dim">{t('routes.picker.noPath')}</p>
      )}
      {options.map((location, index) => {
        const fresh = isNewBerthPath(library, location)
        const holder = fresh ? null : takenBy(location)
        const noteId = `${idBase}-${index}`
        return (
          // 說明不放進 `<label>`：radio 的名字只是那條路徑，說明走 `aria-describedby`。
          <div key={location} className="flex flex-wrap items-start gap-x-3 gap-y-1">
            <label className="flex min-w-0 items-start gap-x-3">
              <input
                type="radio"
                name={`target-${library.name}`}
                value={location}
                checked={target === location}
                disabled={holder !== null}
                aria-describedby={holder !== null || fresh ? noteId : undefined}
                onChange={() => onPick(location)}
                className="mt-0.5 size-4 shrink-0 accent-[var(--color-assigned)] disabled:cursor-not-allowed"
              />
              <span className="value min-w-0 text-xs wrap-anywhere text-ink">{location}</span>
            </label>
            {holder !== null && (
              <span id={noteId} className="text-xs text-ink-dim">
                {t('routeSettings.add.taken', { name: holder })}
              </span>
            )}
            {fresh && (
              <span id={noteId} className="text-xs text-ink-dim">
                {t('routes.picker.newBerthPath')}
              </span>
            )}
          </div>
        )
      })}
    </fieldset>
  )
}
