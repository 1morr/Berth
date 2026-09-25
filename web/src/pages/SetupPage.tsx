import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { ApiError } from '../api/client'
import {
  addLibraryPath,
  applyIndexers,
  applyQbittorrent,
  bootstrapJellyfin,
  bundledRefusalOf,
  buildRoutes,
  completeSetup,
  connectIndexer,
  connectJellyfin,
  connectService,
  createAdmin,
  detectServices,
  indexerSetupQueryOptions,
  jellyfinSetupQueryOptions,
  qbittorrentSetupQueryOptions,
  removeIndexer,
  routeSetupQueryOptions,
  saveBundledLibraries,
  searchIndexers,
  setupStatusQueryOptions,
  skipIndexers,
  testTmdb,
  tmdbSetupQueryOptions,
  type AdminInput,
  type ConnectInput,
  type IndexerSetup,
  type JellyfinSetup,
  type LibraryDraft,
  type RouteSelectionInput,
  type RouteSetup,
  type SetupStatus,
  type TmdbSetup,
} from '../api/setup'
import { type QbittorrentSetup, type ServiceKind } from '../api/schemas'
import { healthQueryOptions } from '../api/health'
import { routeRefusalOf } from '../api/routes'
import { BERTHS } from '../components/berths'
import { LanguageToggle } from '../components/LanguageToggle'
import { AdminStep } from '../setup/AdminStep'
import { BerthBoard, type BerthSignals } from '../setup/BerthBoard'
import { BerthNav, RevisitNote } from '../setup/BerthNav'
import { CompleteStep, type CompleteFailure } from '../setup/CompleteStep'
import { DetectStep } from '../setup/DetectStep'
import { IndexerStep } from '../setup/IndexerStep'
import { JellyfinStep } from '../setup/JellyfinStep'
import { RedetectButton } from '../setup/MooringLine'
import { QbittorrentStep } from '../setup/QbittorrentStep'
import { RouteStep } from '../setup/RouteStep'
import { TmdbStep } from '../setup/TmdbStep'
import {
  BERTH_STEP,
  STEP,
  TOTAL_STEPS,
  advanced,
  berthOf,
  go,
  nextOf,
  previousOf,
  reachable,
  shownStep,
  straying,
} from '../setup/navigation'
import { PAGE_TITLE, GhostButton, NAV_BOX, NAV_BOX_ACTIVE, Notice } from '../components/controls'
import { type Signal } from '../components/signal'
import { isSettled } from '../components/steps'
import { signalOf } from '../setup/signals'

/** 服務還在啟動時的重探間隔。上限由後端的輪詢窗口決定（`window_seconds`）。 */
const POLL_INTERVAL_MS = 3000

/**
 * bootstrap 進行中的進度輪詢。後端每一步在做之前就把自己標成 `running` 並存下來，
 * 所以請求還在飛的時候讀 `GET /setup/jellyfin` 就看得到序列走到哪裡。
 */
const PROGRESS_INTERVAL_MS = 1500

/**
 * 設定精靈。方向見 `.impeccable/surfaces/web-src-pages-setuppage-tsx.md`：
 * 泊位常駐在頂端，工作面在下；不是八張「下一步」的表單。
 *
 * 導覽的規則（停在結果上、上一個 / 下一個、點得到哪幾格）在 `setup/navigation.ts`，是純函式；
 * 這一頁只把它接到按鈕上（票 06d）。
 */
export function SetupPage({
  berth,
}: {
  /**
   * 直接停在哪一個泊位（1 起算）。從網址來，但由路由讀了再傳進來——這個元件的測試刻意
   * 不掛 router（`test/render.tsx` 的 `renderWithProviders`），而路由的知識本來就該
   * 留在 `routes.tsx`。
   */
  berth?: number
}) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const status = useQuery(setupStatusQueryOptions)
  // 步驟是由狀態導出的（plan §9.3），所以「停在結果上」與「回頭看」都靠這個覆寫，不是靠改狀態。
  const [pinned, setPinned] = useState<number | null>(() => {
    const slot = berth ? BERTHS[berth - 1]?.slot : undefined
    return slot ? BERTH_STEP[slot] : null
  })
  // 精靈跑完之後再進來的人：他是來改一個設定的，不是來重跑一次的。
  const revisited = useQuery(healthQueryOptions).data?.setup_completed ?? false

  const current = status.data
  const backend = current?.current_step ?? STEP.admin
  const step = shownStep(backend, pinned)

  /** 去某一步。去後端目前那一頁就是解除覆寫（`go`）。 */
  function goTo(target: number) {
    setPinned(go(target, backend))
  }

  /**
   * 按下這一頁的動作那一刻釘住這一頁：做完之後後端就前進了，畫面照樣停在結果上，
   * 使用者按「前往下一個泊位」才走（票 06d）。
   */
  function hold() {
    setPinned(step)
  }

  function absorb(next: SetupStatus) {
    queryClient.setQueryData(setupStatusQueryOptions.queryKey, next)
  }

  function absorbJellyfin(next: JellyfinSetup) {
    absorbBerth(jellyfinSetupQueryOptions.queryKey, next)
  }

  /** 一個泊位的動作做完，精靈就可能前進，所以整份狀態要重讀（步驟是導出的，不是游標）。 */
  function absorbBerth<T>(key: readonly unknown[], next: T) {
    queryClient.setQueryData(key, next)
    void queryClient.invalidateQueries({ queryKey: setupStatusQueryOptions.queryKey })
  }

  const admin = useMutation({
    mutationFn: (input: AdminInput) => createAdmin(input),
    onSuccess: (next) => {
      absorb(next)
      setPinned(null)
    },
  })
  // 探測本身連續失敗的起點（票 06g）。後端沒回判定就沒有 `waited_seconds`，視窗由前端自己量；
  // 還在視窗內的失敗算「還在探測」，過了才說失敗、等人按。
  const failingSince = useRef<number | null>(null)
  const [failingInWindow, setFailingInWindow] = useState(false)
  const windowMs = (status.data?.window_seconds ?? 0) * 1000
  // 背景輪詢也走這一支，所以釘住畫面的是按鍵那一刻（`onDetect`），不是這裡：輪詢若也釘，
  // 在泊位頁上重新偵測、服務還在啟動的那幾秒會把畫面釘回第 2 步，判定出來之後回不去原本那一頁。
  const detect = useMutation({
    mutationFn: (restart: boolean) => detectServices(restart),
    onSuccess: (next) => {
      failingSince.current = null
      absorb(next)
    },
    onError: () => {
      failingSince.current ??= Date.now()
      setFailingInWindow(Date.now() - failingSince.current < windowMs)
    },
  })
  // 「重新偵測這個服務」（票 06d）：只探那一個，然後泊位的狀態也重讀——連不上的通常是它。
  // 不重啟輪詢窗口：其他服務的等待不該因為這一個被重算（整輪重試才重啟，`restart`）。
  const redetect = useMutation({
    mutationFn: (kind: ServiceKind) => detectServices(false, kind),
    onMutate: hold,
    onSuccess: (next) => {
      // 拿到新的判定，上一輪整輪探測的失敗就是舊的了：不清掉的話它會蓋掉新判定的「探測中」，
      // 輪詢不會恢復（票 06g code review）。
      failingSince.current = null
      detect.reset()
      absorb(next)
      for (const options of [
        jellyfinSetupQueryOptions,
        qbittorrentSetupQueryOptions,
        indexerSetupQueryOptions,
      ]) {
        void queryClient.invalidateQueries({ queryKey: options.queryKey })
      }
    },
  })
  const connect = useMutation({
    mutationFn: ({ kind, input }: { kind: ServiceKind; input: ConnectInput }) =>
      connectService(kind, input),
    onMutate: hold,
    onSuccess: absorb,
  })
  // 剖面上的媒體庫清單停手就存（票 06f）。不釘畫面、不重讀精靈狀態：存清單不會讓精靈前進。
  const saveLibraries = useMutation({
    mutationFn: saveBundledLibraries,
    onSuccess: (next) => queryClient.setQueryData(jellyfinSetupQueryOptions.queryKey, next),
  })
  // 先存剖面上的那一份再跑：`bootstrap` 讀的是存下來的清單，而停手存檔可能還沒送出去。
  const bootstrap = useMutation({
    mutationFn: async (libraries: LibraryDraft[]) => {
      await saveBundledLibraries(libraries)
      return bootstrapJellyfin()
    },
    onMutate: hold,
    onSuccess: absorbJellyfin,
  })
  const signIn = useMutation({
    mutationFn: connectJellyfin,
    onMutate: hold,
    onSuccess: absorbJellyfin,
  })
  const addPath = useMutation({
    mutationFn: addLibraryPath,
    onMutate: hold,
    onSuccess: (next) => {
      absorbJellyfin(next)
      // 媒體庫路徑那一格的清單裡多了一條路徑，那份也要重讀。
      void queryClient.invalidateQueries({ queryKey: routeSetupQueryOptions.queryKey })
    },
  })
  const applyPreferences = useMutation({
    mutationFn: applyQbittorrent,
    onMutate: hold,
    onSuccess: (next) => absorbBerth(qbittorrentSetupQueryOptions.queryKey, next),
  })
  const applySites = useMutation({
    mutationFn: applyIndexers,
    onMutate: hold,
    onSuccess: (next) => absorbBerth(indexerSetupQueryOptions.queryKey, next),
  })
  const connectSource = useMutation({
    mutationFn: connectIndexer,
    onMutate: hold,
    onSuccess: (next) => absorbBerth(indexerSetupQueryOptions.queryKey, next),
  })
  const skipSites = useMutation({
    mutationFn: () => skipIndexers(true),
    onMutate: hold,
    onSuccess: (next) => absorbBerth(indexerSetupQueryOptions.queryKey, next),
  })
  // 試搜只讀、不改後端的步驟，所以不釘畫面；移除最後一站會讓後端退回第 6 步，照樣停在這一頁。
  const trialSearch = useMutation({ mutationFn: searchIndexers })
  const removeSite = useMutation({
    mutationFn: removeIndexer,
    onMutate: hold,
    onSuccess: (next) => absorbBerth(indexerSetupQueryOptions.queryKey, next),
  })
  const tmdbTest = useMutation({
    mutationFn: testTmdb,
    onMutate: hold,
    onSuccess: (next) => absorbBerth(tmdbSetupQueryOptions.queryKey, next),
  })
  const build = useMutation({
    mutationFn: (selections: RouteSelectionInput[]) => buildRoutes(selections),
    onMutate: hold,
    onSuccess: (next) => absorbBerth(routeSetupQueryOptions.queryKey, next),
  })
  const finish = useMutation({
    mutationFn: completeSetup,
    onSuccess: (next) => {
      absorb(next)
      // 路由守衛讀的是 `GET /health` 的 `setup_completed`（票 07），而它走的是
      // `ensureQueryData`——**快取裡有值就直接回，不會重抓**。所以這裡要就地把那一個位元
      // 改掉；只作廢的話下一次導航仍然拿到 `false`，人就被彈回這一頁，而這一頁已經 401 了。
      queryClient.setQueryData(healthQueryOptions.queryKey, (old) =>
        old ? { ...old, setup_completed: true } : old,
      )
      void navigate({ to: '/' })
    },
  })

  const waiting = current?.services.some((row) => row.origin === 'pending') ?? false
  const inFlight = bootstrap.isPending
  // 靠泊之前那一次存檔被擋下來：那不是「請求沒跑完」，由剖面自己說（`librariesFailure`）。
  const bootstrapRefusal = bundledRefusalOf(bootstrap.error)

  const jellyfin = useQuery({
    ...jellyfinSetupQueryOptions,
    enabled: step === STEP.jellyfin,
    refetchInterval: inFlight ? PROGRESS_INTERVAL_MS : false,
  })
  // 第 4 步的差異是**現查的**：使用者可能在 qBittorrent 自己的介面上改過東西。
  const qbittorrent = useQuery({
    ...qbittorrentSetupQueryOptions,
    enabled: step === STEP.qbittorrent,
  })
  // 泊位板要畫得出走過的每一格，所以這三份跟著後端走到哪裡，不跟著畫面停在哪裡。
  const routes = useQuery({ ...routeSetupQueryOptions, enabled: backend >= STEP.routes })
  const indexers = useQuery({ ...indexerSetupQueryOptions, enabled: backend >= STEP.indexer })
  const tmdb = useQuery({ ...tmdbSetupQueryOptions, enabled: backend >= STEP.tmdb })

  // 服務還在啟動就繼續探，直到有結論或後端判逾時（plan §9.3 第 2 步）。
  // 探測本身失敗（非 2xx）也照樣排下一次（票 06g）：四個容器同時起來時探測會在拿到任何判定
  // 之前就失敗，那時沒有 `pending` 可看。失敗時不看上一份判定——它是舊的——只看從第一次失敗
  // 起算有沒有過輪詢上限；過了就停在「探測沒跑完」等人按。
  const probing = detect.isPending || (detect.isError && failingInWindow)
  const failed = detect.isError && !failingInWindow
  useEffect(() => {
    if (detect.isPending || redetect.isPending) return
    if (detect.isError ? !failingInWindow : !waiting) return
    const timer = window.setTimeout(() => detect.mutate(false), POLL_INTERVAL_MS)
    return () => window.clearTimeout(timer)
  }, [waiting, detect, redetect.isPending, failingInWindow])

  // 套件內的媒體庫路徑沒有要選的東西：第一次走到這一格就自動建 Route、跑五條檢查（票 06d）。
  // 只在「後端正停在這一步、一條 Route 都還沒有」時跑一次；回頭看不重跑，要重跑有按鈕。
  const autoBuilt = useRef(false)
  const routeSetup = routes.data
  useEffect(() => {
    if (autoBuilt.current || step !== STEP.routes || backend !== STEP.routes) return
    if (routeSetup?.origin !== 'bundled' || routeSetup.routes.length > 0) return
    autoBuilt.current = true
    build.mutate([])
  }, [step, backend, routeSetup, build])

  if (!current) {
    return (
      <Shell step={STEP.admin}>
        <p className="p-6 text-sm text-ink-dim">
          {status.isError ? t('detect.failed') : t('health.checking')}
        </p>
      </Shell>
    )
  }

  const previous = previousOf(step)
  const next = nextOf(step)
  const nav = (
    <BerthNav
      onPrevious={previous !== null ? () => goTo(previous) : undefined}
      onNext={next !== null && advanced(step, backend) ? () => goTo(next) : undefined}
    />
  )
  const note = advanced(step, backend) ? <RevisitNote step={step} /> : null
  // 手動接好的服務後端不重探（它不在 compose 主機名上），給它這顆鍵等於一顆按了沒反應的鍵——
  // 那種服務改位址或帳密在第 2 步的連線表單上。
  const redetectButton = (kind: ServiceKind) =>
    current.services.find((row) => row.kind === kind)?.configured ? null : (
      <RedetectButton
        kind={kind}
        busy={redetect.isPending && redetect.variables === kind}
        onRedetect={(which) => redetect.mutate(which)}
      />
    )

  /** 媒體庫清單沒存下來的那一句：後端說得出是哪一列就說，說不出就是請求沒跑完（票 06f）。 */
  function librariesFailure(): string | null {
    // 停手存檔的失敗（任何一種）優先；靠泊之前那一次存檔被擋下來也算——那時 `bootstrap` 失敗的原因就是它。
    const refusal = saveLibraries.isError ? bundledRefusalOf(saveLibraries.error) : bootstrapRefusal
    if (saveLibraries.isError && !refusal) return t('jellyfin.bundled.list.saveFailed')
    if (!refusal) return null
    const reason = t(`jellyfin.bundled.list.problem.${refusal.reason}`)
    return refusal.row === undefined
      ? t('jellyfin.bundled.list.refused', { reason })
      : t('jellyfin.bundled.list.refusedRow', { position: refusal.row + 1, reason })
  }

  const shell = {
    step,
    backend,
    revisited,
    status: current,
    indexers: indexers.data,
    tmdb: tmdb.data,
    signals: {
      jellyfin: jellyfinSignal(current, jellyfin.data, inFlight),
      qbittorrent: qbittorrentSignal(current, qbittorrent.data, applyPreferences.isPending),
      library: librarySignal(current, routes.data, build.isPending),
      prowlarr: indexerSignal(
        current,
        indexers.data,
        applySites.isPending || connectSource.isPending || removeSite.isPending,
      ),
      tmdb: tmdbSignal(current, tmdb.data, tmdbTest.isPending),
    } satisfies BerthSignals,
    onGo: goTo,
    onReturn: () => setPinned(null),
  }

  return (
    <Shell {...shell}>
      {step === STEP.admin ? (
        <AdminStep
          status={current}
          pending={admin.isPending}
          failed={admin.isError}
          onSubmit={(input) => admin.mutate(input)}
          nav={advanced(step, backend) ? nav : undefined}
        />
      ) : step === STEP.detect ? (
        <DetectStep
          status={current}
          probing={probing}
          connectingKind={connect.isPending ? connect.variables.kind : null}
          redetectingKind={redetect.isPending ? redetect.variables : null}
          failed={failed}
          onDetect={(restart) => {
            hold()
            // 使用者自己按的是新的一輪：失敗的視窗重新算。
            failingSince.current = null
            detect.mutate(restart)
          }}
          onConnect={(kind, input) => connect.mutate({ kind, input })}
          onRedetect={(kind) => redetect.mutate(kind)}
          onContinue={() => goTo(STEP.jellyfin)}
          nav={<BerthNav onPrevious={() => goTo(STEP.admin)} />}
        />
      ) : step === STEP.jellyfin ? (
        jellyfin.data ? (
          <JellyfinStep
            setup={jellyfin.data}
            running={bootstrap.isPending}
            bootstrapFailed={bootstrap.isError && !bootstrapRefusal}
            signInFailed={signIn.isError}
            connecting={signIn.isPending}
            addingPath={addPath.isPending ? addPath.variables : null}
            onBootstrap={(libraries) => bootstrap.mutate(libraries)}
            onSaveLibraries={(libraries) => saveLibraries.mutate(libraries)}
            savingLibraries={saveLibraries.isPending}
            saveLibrariesFailed={librariesFailure()}
            onConnect={(input) => signIn.mutate(input)}
            onAddPath={(library) => addPath.mutate(library)}
            note={note}
            nav={nav}
            redetect={redetectButton('jellyfin')}
          />
        ) : (
          <Waiting
            failed={jellyfin.isError}
            message={t('jellyfin.unreachable')}
            redetect={redetectButton('jellyfin')}
            nav={nav}
          />
        )
      ) : step === STEP.qbittorrent ? (
        qbittorrent.data ? (
          <QbittorrentStep
            setup={qbittorrent.data}
            applying={applyPreferences.isPending}
            requestFailed={applyPreferences.isError}
            onApply={() => applyPreferences.mutate()}
            note={note}
            nav={nav}
            redetect={redetectButton('qbittorrent')}
          />
        ) : (
          <Waiting
            failed={qbittorrent.isError}
            message={t('qbittorrent.unreachable')}
            redetect={redetectButton('qbittorrent')}
            nav={nav}
          />
        )
      ) : step === STEP.routes ? (
        routes.data ? (
          <RouteStep
            setup={routes.data}
            building={build.isPending}
            addingPath={addPath.isPending ? addPath.variables : null}
            requestFailed={build.isError}
            refusal={routeRefusalOf(build.error)}
            onBuild={(selections) => build.mutate(selections)}
            onAddPath={(library) => addPath.mutate(library)}
            onRouteDeleted={() =>
              void queryClient.invalidateQueries({ queryKey: routeSetupQueryOptions.queryKey })
            }
            autoBuilding={build.isIdle || build.isPending}
            note={note}
            nav={nav}
          />
        ) : (
          <Waiting failed={routes.isError} message={t('routes.unreachable')} nav={nav} />
        )
      ) : step === STEP.complete ? (
        routes.data ? (
          <CompleteStep
            routes={routes.data}
            indexers={indexers.data}
            completing={finish.isPending}
            failure={completeFailure(finish.error, tmdb.data, routes.data)}
            onComplete={() => finish.mutate()}
            onFixTmdb={() => goTo(STEP.tmdb)}
            nav={nav}
          />
        ) : (
          <Waiting failed={routes.isError} message={t('routes.unreachable')} nav={nav} />
        )
      ) : step === STEP.indexer ? (
        indexers.data ? (
          <IndexerStep
            indexers={indexers.data}
            applying={applySites.isPending}
            connecting={connectSource.isPending}
            onApply={(selected) => applySites.mutate(selected)}
            onConnect={(input) => connectSource.mutate(input)}
            onSkip={() => skipSites.mutate()}
            trial={{
              result: trialSearch.data,
              searching: trialSearch.isPending,
              failed: trialSearch.isError,
              onSearch: (query) => trialSearch.mutate(query),
              removing: removeSite.isPending ? removeSite.variables : null,
              removeFailed: removeSite.isError,
              onRemove: (id) => removeSite.mutate(id),
            }}
            note={note}
            nav={nav}
            redetect={redetectButton('prowlarr')}
          />
        ) : (
          <Waiting failed={indexers.isError} message={t('indexer.unreachable')} nav={nav} />
        )
      ) : tmdb.data ? (
        <TmdbStep
          tmdb={tmdb.data}
          testing={tmdbTest.isPending}
          onTest={(apiKey) => tmdbTest.mutate(apiKey)}
          note={note}
          nav={nav}
        />
      ) : (
        <Waiting failed={tmdb.isError} message={t('tmdbStep.unreachable')} nav={nav} />
      )}
    </Shell>
  )
}

/** 還沒讀到那個泊位的狀態。讀不到與還在讀是兩件事，說法也不一樣。 */
function Waiting({
  failed,
  message,
  redetect,
  nav,
}: {
  failed: boolean
  message: string
  /** 讀不到的是某個服務時：就地重新偵測它（票 06d）。 */
  redetect?: ReactNode
  nav: ReactNode
}) {
  const { t } = useTranslation()

  return (
    <div className="p-6">
      <p className="text-sm text-ink-dim">{failed ? message : t('health.checking')}</p>
      {failed && redetect && <div className="mt-4">{redetect}</div>}
      {nav}
    </div>
  )
}

/**
 * 泊位 1 的信號。探到了不等於這個泊位的事做完了，所以它看的是第 3 步自己的狀態：
 * 有步驟在跑 → 進行中；有步驟失敗 → 阻擋；精靈已經前進到下一個泊位 → 已繫上。
 */
function jellyfinSignal(
  status: SetupStatus,
  setup: JellyfinSetup | undefined,
  inFlight: boolean,
): Signal {
  const detection = status.services.find((row) => row.kind === 'jellyfin')
  if (inFlight || setup?.steps.some((row) => row.status === 'running')) return 'working'
  if (setup?.steps.some((row) => row.status === 'failed')) return 'blocked'
  if (status.current_step > STEP.jellyfin) return 'secured'
  return signalOf(detection)
}

/** 泊位 2 的信號。版本太舊或連不上是阻擋——那一步在使用者升級之前做不下去。 */
function qbittorrentSignal(
  status: SetupStatus,
  setup: QbittorrentSetup | undefined,
  applying: boolean,
): Signal {
  const detection = status.services.find((row) => row.kind === 'qbittorrent')
  if (applying) return 'working'
  if (setup?.blocked || setup?.steps.some((row) => row.status === 'failed')) return 'blocked'
  if (status.current_step > STEP.qbittorrent) return 'secured'
  return signalOf(detection)
}

/**
 * 索引站那一格的信號。逐站失敗**不算阻擋**：公開站裡有幾個連不上是常態，只要接上了一個
 * 就走得下去（後端的步驟判定用的是同一條規則）。
 */
function indexerSignal(
  status: SetupStatus,
  indexers: IndexerSetup | undefined,
  busy: boolean,
): Signal {
  const detection = status.services.find((row) => row.kind === 'prowlarr')
  if (busy) return 'working'
  if (status.current_step > STEP.indexer) return 'secured'
  const settled =
    (indexers?.skipped ?? false) || (indexers?.steps.some((row) => isSettled(row.status)) ?? false)
  if (settled) return 'secured'
  return signalOf(detection)
}

/**
 * TMDB 那一格的信號。它是閘門，沒有索引站那種寬容：綠燈由後端的 `verified` 說了算（票 02b），
 * 測過而不過是阻擋，走到了還沒測是待靠泊。
 */
function tmdbSignal(status: SetupStatus, tmdb: TmdbSetup | undefined, testing: boolean): Signal {
  if (testing) return 'working'
  if (tmdb?.verified) return 'secured'
  if (tmdb?.steps.some((row) => row.status === 'failed')) return 'blocked'
  if (status.current_step >= STEP.tmdb) return 'assigned'
  return 'neutral'
}

/**
 * 按下「完成設定」失敗的原因（票 03 第 5 條）。
 *
 * **422 不是後端出錯**：`complete_setup` 用它說「第 5 步或第 7 步還沒做完」
 * （`berth/services/setup.py`）。是哪一步前端自己答得出來——TMDB 的綠燈就在手上的
 * `tmdb.verified`，不必去解那句英文散文。其餘（5xx、連不上）才是後端的問題。
 */
function completeFailure(
  error: unknown,
  tmdb: TmdbSetup | undefined,
  routes: RouteSetup | undefined,
): CompleteFailure | undefined {
  if (error === null || error === undefined) return undefined
  if (!(error instanceof ApiError) || error.status !== 422) return 'backend'
  // 是哪一步用手上的兩份狀態答，而不是去解那句英文散文。**兩份都得明確說不行才指名**：
  // 還沒載回來時 `verified` 是 `undefined`，拿它當「沒驗過」會在真正卡住的是 Route 時說錯話
  // （票 03 的 code review）。兩份都說沒問題卻仍被擋，代表我們這一份過期或後端多了一種 422——
  // 那就別猜，說「還有一步沒做完」。
  // 照步驟的順序問（Route 是第 5 步、TMDB 是第 7 步），與後端 `complete_setup` 同一個順序。
  if (routes?.ready === false) return 'routes'
  if (tmdb?.verified === false) return 'tmdb'
  return 'unfinished'
}

/**
 * 媒體庫路徑那一格的信號。這一格沒有對應的服務判定，看的是 Route 自己的健康：有紅的就是阻擋，
 * 全綠才是已繫上（`ready` 與後端「第 5 步做完了沒」是同一條規則）。
 */
function librarySignal(
  status: SetupStatus,
  routes: RouteSetup | undefined,
  building: boolean,
): Signal {
  if (building) return 'working'
  // 停用的 Route 不是目的地，完成條件也不算它（票 14，後端 `routes_ready` 同一條規則）。
  if (routes?.routes.some((route) => route.enabled && route.health === 'failed')) return 'blocked'
  if (routes?.ready) return 'secured'
  if (status.current_step >= STEP.routes) return 'assigned'
  return 'neutral'
}

function Shell({
  step,
  backend = STEP.admin,
  status,
  signals,
  indexers,
  tmdb,
  revisited = false,
  onGo,
  onReturn,
  children,
}: {
  /** 畫面上是哪一步。 */
  step: number
  /** 後端說現在是第幾步。兩者不同就是在回頭看或停在結果上。 */
  backend?: number
  status?: SetupStatus
  signals?: BerthSignals
  /** 索引站那一格的詳情列（接上的是哪一種、幾站）。第 6 步起才問得到。 */
  indexers?: IndexerSetup
  /** TMDB 那一格的詳情列（憑證驗過了沒）。第 7 步起才問得到。 */
  tmdb?: TmdbSetup
  /**
   * 精靈已經跑完過。這時候它是設定入口而不是 onboarding，所以要有出口——
   * 否則從設定頁點「改位址或憑證」進來的人，只剩瀏覽器的上一頁可按。（票 06i 刪掉這條路。）
   */
  revisited?: boolean
  onGo?: (step: number) => void
  /** 回到目前這一步：解除覆寫。 */
  onReturn?: () => void
  children: ReactNode
}) {
  const { t } = useTranslation()
  const berth = berthOf(step)
  const code = berth ? BERTHS.find((row) => row.slot === berth)?.code : undefined

  return (
    <div className="flex min-h-dvh flex-col bg-hull text-ink">
      <header className="flex flex-wrap items-center gap-x-6 gap-y-3 border-b-2 border-rule-strong px-6 py-4">
        <p className="value text-lg font-semibold tracking-tight">{t('app.name')}</p>
        {/* 精靈這一頁的標題。每一步自己的 `<h2>` 掛在它底下（票 03 第 13 條）。 */}
        <h1 className={PAGE_TITLE}>{t('setup.title')}</h1>
        <p className="label ml-auto text-ink-dim">
          {code
            ? t('setup.stage.berth', { code })
            : t(step === STEP.complete ? 'setup.stage.final' : 'setup.stage.pre')}{' '}
          · {t('setup.step', { current: step, total: TOTAL_STEPS })}
        </p>
        {revisited && (
          <Link to="/health" className="label text-ink-dim underline hover:text-ink">
            {t('setup.exit')}
          </Link>
        )}
        <LanguageToggle />
      </header>

      {status?.admin_created && onGo && <Prelude status={status} step={step} onGo={onGo} />}

      <BerthBoard
        services={status?.services ?? []}
        signals={signals}
        indexers={indexers}
        tmdb={tmdb}
        current={code}
        reachable={onGo && ((slot) => reachable(BERTH_STEP[slot], backend))}
        onSelect={onGo && ((slot) => onGo(BERTH_STEP[slot]))}
      />

      {onReturn && straying(step, backend) && (
        <StrayBand step={step} backend={backend} code={code} onReturn={onReturn} />
      )}

      {revisited && (
        <div className="border-b-2 border-rule px-6 py-3">
          <Notice signal="assigned" label={t('status.ok')}>
            {t('setup.revisited')}
          </Notice>
        </div>
      )}

      <main className="flex flex-1 flex-col">{children}</main>

      <footer className="px-6 py-6">
        <p className="text-xs text-ink-dim">{t('setup.resumed')}</p>
      </footer>
    </div>
  )
}

/**
 * 前置列：第 1、2 步不是泊位，不上板，但走過了就要點得回去（票 06d 的 shape）。
 * 兩格同時是證據（管理員是誰、判定了幾個服務）與入口——原本那條 trail 的「改帳密」
 * 「重新探測」兩顆鍵拿掉了，那兩件事在它們自己的那一步上做。
 */
function Prelude({
  status,
  step,
  onGo,
}: {
  status: SetupStatus
  step: number
  onGo: (step: number) => void
}) {
  const { t } = useTranslation()
  const detected = status.services.length
  const items = [
    { step: STEP.admin, text: t('admin.saved', { username: status.admin_username }) },
    {
      step: STEP.detect,
      text: detected > 0 ? t('detect.done', { count: detected }) : t('setup.place.detect'),
    },
  ]

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b-2 border-rule px-6 py-3">
      <span className="label text-ink-dim">{t('setup.prelude')}</span>
      {items.map((item) => (
        <button
          key={item.step}
          type="button"
          aria-current={item.step === step ? 'step' : undefined}
          onClick={() => onGo(item.step)}
          // 模板字的 `.label` 會把帳號大寫掉，所以字用 `.value`，外框借 NAV_BOX 的方塊。
          className={`${item.step === step ? NAV_BOX_ACTIVE : NAV_BOX} px-3 py-1.5 normal-case`}
        >
          <span className="value text-sm tracking-normal text-ink">{item.text}</span>
        </button>
      ))}
    </div>
  )
}

/**
 * 回頭看得比「剛做完的那一格」更前面時，板下一條帶子說出在哪裡、目前走到哪，給一顆直接回去的鍵
 * （票 06d：回頭看的時候永遠有出口）。剛做完、停在結果上的那一格不需要它——
 * 「前往下一個泊位」就是回去的路。
 */
function StrayBand({
  step,
  backend,
  code,
  onReturn,
}: {
  step: number
  backend: number
  code: string | undefined
  onReturn: () => void
}) {
  const { t } = useTranslation()
  const berth = code ? BERTHS.find((row) => row.code === code) : undefined
  const place = berth
    ? `${berth.code} ${t(berth.nameKey)}`
    : t(step === STEP.admin ? 'setup.place.admin' : 'setup.place.detect')

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b-2 border-rule bg-deck px-6 py-3">
      <p className="text-sm text-ink">
        {t('setup.stray.where', { place })}
        <span className="text-ink-dim"> · {t('setup.stray.current', { current: backend })}</span>
      </p>
      <div className="sm:ml-auto">
        <GhostButton type="button" onClick={onReturn}>
          {t('setup.stray.back')}
        </GhostButton>
      </div>
    </div>
  )
}
