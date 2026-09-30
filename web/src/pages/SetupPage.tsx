import { useEffect, useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { ApiError } from '../api/client'
import {
  addLibraryPaths,
  applyIndexers,
  applyQbittorrent,
  bootstrapJellyfin,
  bundledRefusalOf,
  buildRoutes,
  chooseService,
  choiceRefusalOf,
  CLAIM_OWNER_KEY,
  claimOwner,
  completeSetup,
  connectIndexer,
  apiKeyFailed,
  connectJellyfin,
  indexerSetupQueryOptions,
  jellyfinSetupQueryOptions,
  loginRefusalOf,
  ownerRefusalOf,
  qbittorrentSetupQueryOptions,
  removeIndexer,
  rereadRouteLibraries,
  retestService,
  routeSetupQueryOptions,
  saveBundledLibraries,
  searchIndexers,
  setIndexerLogin,
  setupStatusQueryOptions,
  skipIndexers,
  testIndexers,
  testTmdb,
  tmdbSetupQueryOptions,
  type ChoiceInput,
  type IndexerSetup,
  type JellyfinSetup,
  type RouteSetup,
  type SetupStatus,
  type TmdbSetup,
} from '../api/setup'
import { type QbittorrentSetup, type ServiceKind } from '../api/schemas'
import { meQueryOptions } from '../api/auth'
import { healthQueryOptions } from '../api/health'
import { routeRefusalOf } from '../api/routes'
import { BERTHS } from '../components/berths'
import { LanguageToggle } from '../components/LanguageToggle'
import { BerthBoard, type BerthSignals } from '../setup/BerthBoard'
import { BerthNav, RevisitNote } from '../setup/BerthNav'
import { CompleteStep, type CompleteFailure } from '../setup/CompleteStep'
import { IndexerStep } from '../setup/IndexerStep'
import { OwnerStep } from '../setup/OwnerStep'
import { QbittorrentStep } from '../setup/QbittorrentStep'
import { librariesFailed } from '../setup/jellyfinSteps'
import { RouteStep, type DockFailure, type DockPlan } from '../setup/RouteStep'
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
import { type ChoiceControls } from '../setup/ServiceChoice'
import { PAGE_TITLE, GhostButton } from '../components/controls'
import { commonRoot } from '../components/routeChecks'
import { type Signal } from '../components/signal'
import { connected, signalOf } from '../setup/signals'

/** 套件內那一台還在啟動時的重測間隔。上限由後端的輪詢窗口決定（`window_seconds`）。 */
const POLL_INTERVAL_MS = 3000

/**
 * bootstrap 進行中的進度輪詢。後端每一步在做之前就把自己標成 `running` 並存下來，
 * 所以請求還在飛的時候讀 `GET /setup/jellyfin` 就看得到序列走到哪裡。
 */
const PROGRESS_INTERVAL_MS = 1500

/**
 * 設定精靈。方向見 `.impeccable/surfaces/web-src-pages-setuppage-tsx.md`：
 * 泊位常駐在頂端，工作面在下；不是六張「下一步」的表單。
 *
 * **不偵測**（M4 票 15，`.scratch/m4/service-pages-shape.md`）：三個服務頁的頁首是二選一，選了才連。
 * 進頁與選擇之前，這一頁不對任何服務發請求——qBittorrent 的差異在選了、連上之後才讀。
 *
 * 導覽的規則（停在結果上、上一個 / 下一個、點得到哪幾格）在 `setup/navigation.ts`，是純函式；
 * 這一頁只把它接到按鈕上（票 06d）。
 *
 * **精靈只管第一次**（票 06i）：跑完之後 `/setup` 導向設定頁（`routes.tsx`），改東西在那裡，
 * 所以這一頁沒有「從外面直接跳到某個泊位」或「跑完之後再回來」的分支。
 */
export function SetupPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const status = useQuery(setupStatusQueryOptions)
  // 步驟是由狀態導出的（plan §9.3），所以「停在結果上」與「回頭看」都靠這個覆寫，不是靠改狀態。
  const [pinned, setPinned] = useState<number | null>(null)

  const current = status.data
  const backend = current?.current_step ?? STEP.jellyfin
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

  // 頁 1：成為擁有者（M4 票 06）。成功時後端發了 session cookie——從這一刻起精靈要登入，
  // 所以路由守衛讀的那一個位元（`owner_established`）就地改掉，「我是誰」也重問。
  // 成功之後照 06d 的規則停在結果上（「擁有者：名字」，critique：峰值要落地），按了才走。
  const owner = useMutation({
    mutationKey: CLAIM_OWNER_KEY,
    mutationFn: claimOwner,
    onMutate: hold,
    onSuccess: (next) => {
      absorb(next)
      queryClient.setQueryData(healthQueryOptions.queryKey, (old) =>
        old ? { ...old, owner_established: true } : old,
      )
      void queryClient.invalidateQueries({ queryKey: meQueryOptions.queryKey })
    },
  })
  /** 那個服務的頁自己讀的那一份：選擇換了，它說的就是另一台。 */
  function invalidateBerthOf(kind: ServiceKind) {
    const options = {
      jellyfin: jellyfinSetupQueryOptions,
      qbittorrent: qbittorrentSetupQueryOptions,
      prowlarr: indexerSetupQueryOptions,
    }[kind]
    void queryClient.invalidateQueries({ queryKey: options.queryKey })
    // 換了一台 qBittorrent，Route 的檢查作廢了（後端 `forget_route_checks`）。
    if (kind === 'qbittorrent') {
      void queryClient.invalidateQueries({ queryKey: routeSetupQueryOptions.queryKey })
    }
  }
  // 服務頁的二選一（M4 票 15）：存下、測一次。按下去那一刻釘住這一頁，結果回來照樣停在這裡。
  const choose = useMutation({
    mutationFn: ({ kind, input }: { kind: ServiceKind; input: ChoiceInput }) =>
      chooseService(kind, input),
    onMutate: hold,
    onSuccess: (next, { kind }) => {
      absorb(next)
      invalidateBerthOf(kind)
    },
  })
  // 重測：紅燈上的「重新測試」（`restart`），以及套件內那一台還在啟動時的輪詢。輪詢不釘畫面——
  // 使用者在別頁回頭看的時候，背景的重測不該把他拉回去。
  const retest = useMutation({
    mutationFn: ({ kind, restart }: { kind: ServiceKind; restart: boolean }) =>
      retestService(kind, restart),
    onSuccess: (next, { kind }) => {
      absorb(next)
      invalidateBerthOf(kind)
    },
  })
  function choiceOf(kind: ServiceKind): ChoiceControls {
    return {
      choosing: choose.isPending && choose.variables.kind === kind,
      retesting: retest.isPending && retest.variables.kind === kind && retest.variables.restart,
      refusal: choose.variables?.kind === kind ? choiceRefusalOf(choose.error) : null,
      onChoose: (input, done) => choose.mutate({ kind, input }, { onSuccess: done }),
      onRetest: (restart) => {
        if (restart) hold()
        retest.mutate({ kind, restart })
      },
    }
  }
  // 擁有者成立之後 Berth 的 key 被撤了（M4 票 18）：頁 1 就地以管理員重新登入換一把，換到了就重新測試。
  const reSignIn = useMutation({
    mutationFn: connectJellyfin,
    onSuccess: (next) => {
      queryClient.setQueryData(jellyfinSetupQueryOptions.queryKey, next)
      if (!apiKeyFailed(next)) retest.mutate({ kind: 'jellyfin', restart: true })
    },
  })
  // 剖面上的媒體庫清單停手就存（票 06f）。不釘畫面、不重讀精靈狀態：存清單不會讓精靈前進。
  const saveLibraries = useMutation({
    mutationFn: saveBundledLibraries,
    onSuccess: (next) => queryClient.setQueryData(jellyfinSetupQueryOptions.queryKey, next),
  })
  // 頁 3 的「建立並檢查」（M4 票 08）：一顆鈕照順序做完，一段失敗就停、後面的不送。建媒體庫與加路徑
  // 的失敗不是 4xx，而是 Jellyfin 那一份的 `libraries` 那一步變紅——那時不建 Route，畫面讀它說原文。
  const dock = useMutation({
    mutationFn: async (plan: DockPlan): Promise<RouteSetup | null> => {
      if (plan.origin === 'bundled') {
        // 先存清單再建：`bootstrap` 讀的是存下來的那一份，而停手存檔可能還沒送出去。
        await saveBundledLibraries(plan.libraries)
        if (plan.buildLibraries && !(await stepThrough(bootstrapJellyfin()))) return null
        return buildRoutes([])
      }
      // 一次送全部：後端逐個試、逐個回報（M4 票 19），有一個沒加上就不建 Route。
      if (plan.newPaths.length > 0 && !(await stepThrough(addLibraryPaths(plan.newPaths)))) {
        return null
      }
      return buildRoutes(plan.selections)
    },
    onMutate: hold,
    onSuccess: (next) => {
      if (next) absorbBerth(routeSetupQueryOptions.queryKey, next)
      // 媒體庫清單或某個媒體庫的路徑變了：那一份也要重讀。
      else void queryClient.invalidateQueries({ queryKey: routeSetupQueryOptions.queryKey })
    },
  })

  /** Jellyfin 那一段做完了，照實收下；它的 `libraries` 那一步紅了就不往下走。 */
  async function stepThrough(request: Promise<JellyfinSetup>): Promise<boolean> {
    const next = await request
    absorbJellyfin(next)
    return librariesFailed(next) === undefined
  }
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
  // 套件內 Prowlarr 的介面登入是自己的一顆按鈕（M4 票 20），不跟著「加入」送。
  const prowlarrLogin = useMutation({
    mutationFn: setIndexerLogin,
    onMutate: hold,
    onSuccess: (next) => absorbBerth(indexerSetupQueryOptions.queryKey, next),
  })
  // 既有 Prowlarr 或 Torznab 的表單（頁 4 選「既有」時）：這就是選了既有，精靈狀態裡的選擇也跟著變。
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
  // 測試與試搜只讀、不改後端的步驟，所以不經 mutation 也不釘畫面（`IndexerSites` 自己記結果）；
  // 移除最後一站會讓後端退回頁 4，照樣停在這一頁。
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

  // 套件內那一台還在啟動：每 3 秒重測，直到有結論或後端判逾時（M3 票 06g 的三種樣子）。
  const waitingKind = current?.services.find((row) => row.state === 'waiting')?.kind
  // 按下之前那一次存檔被擋下來：那不是「請求沒跑完」，由清單自己說（`librariesFailure`）。
  const dockRefusal = bundledRefusalOf(dock.error)

  // 套件內 Jellyfin 的媒體庫清單在頁 3（M4 票 15 從 Jellyfin 頁搬過來）。這一支不連線，只讀存下的狀態。
  const jellyfin = useQuery({
    ...jellyfinSetupQueryOptions,
    enabled: step === STEP.routes,
    refetchInterval: dock.isPending ? PROGRESS_INTERVAL_MS : false,
  })
  const qbittorrentChoice = current?.services.find((row) => row.kind === 'qbittorrent')
  // 頁 2 的差異是**現查的**：使用者可能在 qBittorrent 自己的介面上改過東西。**選了、連上了才問**
  // ——這一支會去連那一台，選之前不發（M4 票 15）。
  const qbittorrent = useQuery({
    ...qbittorrentSetupQueryOptions,
    enabled: step === STEP.qbittorrent && connected(qbittorrentChoice),
  })
  // 泊位板要畫得出走過的每一格，所以這三份跟著後端走到哪裡，不跟著畫面停在哪裡。
  const routes = useQuery({ ...routeSetupQueryOptions, enabled: backend >= STEP.routes })
  // 頁 3 進頁時向既有 Jellyfin 重讀媒體庫（M4 票 19）：頁 1 之後在 Jellyfin 改的掛載與路徑要看得到。
  // 讀的是 Jellyfin、寫的是 Berth 的快照，不動任何服務，所以不釘畫面。
  const reread = useMutation({
    mutationFn: rereadRouteLibraries,
    onSuccess: (next) => queryClient.setQueryData(routeSetupQueryOptions.queryKey, next),
  })
  const rereadOnEntry = step === STEP.routes && routes.data?.origin === 'existing'
  const { mutate: rereadNow } = reread
  useEffect(() => {
    if (rereadOnEntry) rereadNow()
  }, [rereadOnEntry, rereadNow])
  const indexers = useQuery({ ...indexerSetupQueryOptions, enabled: backend >= STEP.indexer })
  const tmdb = useQuery({ ...tmdbSetupQueryOptions, enabled: backend >= STEP.tmdb })

  useEffect(() => {
    if (!waitingKind || retest.isPending || choose.isPending) return
    const timer = window.setTimeout(
      () => retest.mutate({ kind: waitingKind, restart: false }),
      POLL_INTERVAL_MS,
    )
    return () => window.clearTimeout(timer)
  }, [waitingKind, retest, choose.isPending])

  if (!current) {
    return (
      <Shell step={STEP.jellyfin}>
        <p className="p-6 text-sm text-ink-dim">
          {status.isError ? t('setup.statusFailed') : t('health.checking')}
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
  const note = advanced(step, backend) ? (
    <RevisitNote
      step={step}
      origin={current.services.find((row) => row.kind === 'prowlarr')?.origin}
    />
  ) : null

  /** 媒體庫清單沒存下來的那一句：後端說得出是哪一列就說，說不出就是請求沒跑完（票 06f）。 */
  function librariesFailure(): string | null {
    // 停手存檔的失敗（任何一種）優先；按下之前那一次存檔被擋下來也算——那時 `dock` 失敗的原因就是它。
    const refusal = saveLibraries.isError ? bundledRefusalOf(saveLibraries.error) : dockRefusal
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
    status: current,
    indexers: indexers.data,
    tmdb: tmdb.data,
    signals: {
      jellyfin: jellyfinSignal(current),
      qbittorrent: qbittorrentSignal(current, qbittorrent.data, applyPreferences.isPending),
      library: librarySignal(current, routes.data, jellyfin.data, dock.isPending),
      prowlarr: indexerSignal(
        current,
        applySites.isPending ||
          connectSource.isPending ||
          removeSite.isPending ||
          prowlarrLogin.isPending,
      ),
      tmdb: tmdbSignal(current, tmdb.data, tmdbTest.isPending),
    } satisfies BerthSignals,
    onGo: goTo,
    onReturn: () => setPinned(null),
  }

  return (
    <Shell {...shell}>
      {step === STEP.jellyfin ? (
        <OwnerStep
          status={current}
          choice={choiceOf('jellyfin')}
          claiming={owner.isPending}
          refusal={ownerRefusalOf(owner.error)}
          claimFailed={owner.isError}
          onClaim={(input) => owner.mutate(input)}
          reSignIn={{
            connecting: reSignIn.isPending,
            failed:
              reSignIn.isError || (reSignIn.data !== undefined && apiKeyFailed(reSignIn.data)),
            onConnect: (input) => reSignIn.mutate(input),
          }}
          note={note}
          nav={advanced(step, backend) ? nav : undefined}
        />
      ) : step === STEP.qbittorrent ? (
        <QbittorrentStep
          status={current}
          setup={qbittorrent.data}
          setupFailed={qbittorrent.isError}
          owner={current.owner}
          applying={applyPreferences.isPending}
          requestFailed={applyPreferences.isError}
          loginRefusal={loginRefusalOf(applyPreferences.error)}
          onApply={(login) => applyPreferences.mutateAsync(login)}
          choice={choiceOf('qbittorrent')}
          note={note}
          nav={nav}
        />
      ) : step === STEP.routes ? (
        routes.data && jellyfin.data ? (
          <RouteStep
            setup={routes.data}
            done={advanced(step, backend)}
            jellyfin={jellyfin.data}
            existing={{
              jellyfin: routes.data.origin === 'existing',
              qbittorrent: qbittorrentChoice?.origin === 'existing',
              root: commonRoot(routes.data.complete_root, routes.data.library_root),
            }}
            reread={{
              pending: reread.isPending,
              failed: reread.isError,
              onReread: () => reread.mutate(),
            }}
            docking={dock.isPending}
            failure={dockFailure(dock.error)}
            onDock={(plan) => dock.mutate(plan)}
            onSaveLibraries={(libraries) => saveLibraries.mutate(libraries)}
            savingLibraries={saveLibraries.isPending}
            saveLibrariesFailed={librariesFailure()}
            onRouteDeleted={() =>
              void queryClient.invalidateQueries({ queryKey: routeSetupQueryOptions.queryKey })
            }
            note={note}
            nav={nav}
          />
        ) : (
          <Waiting
            failed={routes.isError || jellyfin.isError}
            message={t('routes.unreachable')}
            nav={nav}
          />
        )
      ) : step === STEP.complete ? (
        routes.data ? (
          <CompleteStep
            routes={routes.data}
            indexers={indexers.data}
            owner={current.owner}
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
        // 讀回來才掛：先掛上的話 `StepFrame` 的焦點接手比試搜清單的「移除之後接到下一列」先跑，
        // 移除一站之後焦點會被搶到標題上（票 15 的測試抓到的退化）。
        indexers.data ? (
          <IndexerStep
            status={current}
            indexers={indexers.data}
            indexersFailed={indexers.isError}
            owner={current.owner}
            applying={applySites.isPending}
            connecting={connectSource.isPending}
            login={{
              saving: prowlarrLogin.isPending,
              refusal: loginRefusalOf(prowlarrLogin.error),
              onSave: (login) => prowlarrLogin.mutateAsync(login),
            }}
            onApply={(selected) => applySites.mutateAsync(selected)}
            onConnect={(input) => connectSource.mutate(input)}
            onSkip={() => skipSites.mutate()}
            choice={choiceOf('prowlarr')}
            sites={{
              onTest: testIndexers,
              onSearch: searchIndexers,
              removing: removeSite.isPending ? removeSite.variables : null,
              removeFailed: removeSite.isError,
              onRemove: (id) => removeSite.mutate(id),
            }}
            note={note}
            nav={nav}
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
function Waiting({ failed, message, nav }: { failed: boolean; message: string; nav: ReactNode }) {
  const { t } = useTranslation()

  return (
    <div className="p-6">
      <p className="text-sm text-ink-dim">{failed ? message : t('health.checking')}</p>
      {nav}
    </div>
  )
}

/**
 * 「建立並檢查」沒走完的那一種。清單被擋下來不算（清單自己說，`librariesFailure`）；建 Route 途中有一條
 * 被另一個分頁刪掉說得出原因（M2 票 01）；其餘是請求沒走完。
 */
function dockFailure(error: unknown): DockFailure | null {
  if (error === null || error === undefined || bundledRefusalOf(error)) return null
  return routeRefusalOf(error)?.reason === 'route_missing' ? 'route_missing' : 'request'
}

/**
 * 泊位 1 的信號：Jellyfin 那一頁的事是成立擁有者。成立了就繫上；之前看選擇的測試結果。
 */
function jellyfinSignal(status: SetupStatus): Signal {
  if (status.owner || status.current_step > STEP.jellyfin) return 'secured'
  return pageSignal(status.services.find((row) => row.kind === 'jellyfin'))
}

/**
 * 那一頁還沒做完時，選擇的測試結果在板上怎麼塗：連上了只是「輪到你」（`assigned`），不是繫上——
 * 那一頁自己的事（擁有者、偏好、索引站）還在等人。其餘照測試的結果。
 */
function pageSignal(chosen: SetupStatus['services'][number] | undefined): Signal {
  const signal = signalOf(chosen)
  return signal === 'secured' ? 'assigned' : signal
}

/** 泊位 2 的信號。版本太舊或連不上是阻擋——那一步在使用者升級之前做不下去。 */
function qbittorrentSignal(
  status: SetupStatus,
  setup: QbittorrentSetup | undefined,
  applying: boolean,
): Signal {
  const chosen = status.services.find((row) => row.kind === 'qbittorrent')
  if (applying) return 'working'
  if (setup?.blocked || setup?.steps.some((row) => row.status === 'failed')) return 'blocked'
  if (status.current_step > STEP.qbittorrent) return 'secured'
  return pageSignal(chosen)
}

/**
 * 索引站那一格的信號。逐站失敗**不算阻擋**：公開站裡有幾個連不上是常態，只要接上了一個
 * 就走得下去。做完了沒只看後端的頁序（`_indexer_settled`）：加了站而介面登入還沒設、既有 Prowlarr
 * 一站都沒有，都還沒做完（M4 票 20），從纜繩猜會猜成已繫上。
 */
function indexerSignal(status: SetupStatus, busy: boolean): Signal {
  const chosen = status.services.find((row) => row.kind === 'prowlarr')
  if (busy) return 'working'
  if (status.current_step > STEP.indexer) return 'secured'
  return pageSignal(chosen)
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
 * 媒體庫路徑那一格的信號。這一格沒有對應的服務，看的是媒體庫清單與 Route 自己的健康：有紅的就是
 * 阻擋，後端過了這一頁才是已繫上（套件內的清單也要建完，後端 `_libraries_built`）。
 */
function librarySignal(
  status: SetupStatus,
  routes: RouteSetup | undefined,
  jellyfin: JellyfinSetup | undefined,
  building: boolean,
): Signal {
  if (building) return 'working'
  if (jellyfin?.steps.some((row) => row.step === 'libraries' && row.status === 'failed')) {
    return 'blocked'
  }
  // 停用的 Route 不是目的地，完成條件也不算它（票 14，後端 `routes_ready` 同一條規則）。
  if (routes?.routes.some((route) => route.enabled && route.health === 'failed')) return 'blocked'
  if (status.current_step > STEP.routes) return 'secured'
  if (status.current_step >= STEP.routes) return 'assigned'
  return 'neutral'
}

function Shell({
  step,
  backend = STEP.jellyfin,
  status,
  signals,
  indexers,
  tmdb,
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
  /** 索引站那一格的詳情列（接上的是哪一種、幾站）。頁 4 起才問得到。 */
  indexers?: IndexerSetup
  /** TMDB 那一格的詳情列（憑證驗過了沒）。頁 5 起才問得到。 */
  tmdb?: TmdbSetup
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
          {code ? t('setup.stage.berth', { code }) : t('setup.stage.final')} ·{' '}
          {t('setup.step', { current: step, total: TOTAL_STEPS })}
        </p>
        <LanguageToggle />
      </header>

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
        <StrayBand backend={backend} code={code} onReturn={onReturn} />
      )}

      <main className="flex flex-1 flex-col">{children}</main>

      <footer className="px-6 py-6">
        <p className="text-xs text-ink-dim">{t('setup.resumed')}</p>
      </footer>
    </div>
  )
}

/**
 * 回頭看得比「剛做完的那一格」更前面時，板下一條帶子說出在哪裡、目前走到哪，給一顆直接回去的鍵
 * （票 06d：回頭看的時候永遠有出口）。剛做完、停在結果上的那一格不需要它——
 * 「前往下一個泊位」就是回去的路。
 */
function StrayBand({
  backend,
  code,
  onReturn,
}: {
  backend: number
  code: string | undefined
  onReturn: () => void
}) {
  const { t } = useTranslation()
  const berth = code ? BERTHS.find((row) => row.code === code) : undefined
  // 每一頁（除了完成）都是板上的一格；回頭看的一定是其中一格。
  const place = berth ? `${berth.code} ${t(berth.nameKey)}` : ''

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
