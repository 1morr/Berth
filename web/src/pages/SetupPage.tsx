import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useSearch } from '@tanstack/react-router'
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
  composeQueryOptions,
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
import { type QbittorrentSetup, type ServiceKind, type ServiceOrigin } from '../api/schemas'
import { meQueryOptions } from '../api/auth'
import { healthQueryOptions } from '../api/health'
import { jellyfinAddressQueryOptions } from '../api/settings'
import { routeRefusalOf } from '../api/routes'
import { BERTHS } from '../components/berths'
import { LanguageToggle } from '../components/LanguageToggle'
import { BerthBoard, type BerthSignals } from '../setup/BerthBoard'
import { BerthNav, RevisitNote } from '../setup/BerthNav'
import { CompleteStep, type CompleteFailure } from '../setup/CompleteStep'
import { ServiceDoors } from '../setup/ServiceDoors'
import { IndexerStep } from '../setup/IndexerStep'
import { GAP, indexerGaps } from '../setup/indexerGaps'
import { OwnerStep } from '../setup/OwnerStep'
import { QbittorrentStep } from '../setup/QbittorrentStep'
import { librariesFailed } from '../setup/jellyfinSteps'
import { RouteStep, type DockFailure, type DockPlan } from '../setup/RouteStep'
import { BUILD_REFUSAL, type BuildRefusal } from '../setup/buildRefusal'
import { TmdbStep } from '../setup/TmdbStep'
import {
  BERTH_STEP,
  STEP,
  advanced,
  berthOf,
  go,
  nextOf,
  previousOf,
  reachable,
  shownStep,
  stepOf,
  straying,
} from '../setup/navigation'
import { type ChoiceControls } from '../setup/ServiceChoice'
import { type ChoiceDraft } from '../setup/choiceDraft'
import { PAGE_TITLE, GhostButton, Notice } from '../components/controls'
import { RequestFailed } from '../components/RequestFailed'
import { requestProblem } from '../components/requestProblem'
import { useSignOut } from '../components/useSignOut'
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
 * 這一頁只把它接到按鈕上（票 06d）。畫面上那一頁就是網址的 `?step=N`（M4 票 30）：換頁進瀏覽器的
 * 歷史，上一頁回到上一個看過的頁、重新整理留在原頁。
 *
 * **精靈只管第一次**（票 06i）：跑完之後 `/setup` 導向設定頁（`routes.tsx`），改東西在那裡，
 * 所以這一頁沒有「從外面直接跳到某個泊位」或「跑完之後再回來」的分支。
 */
export function SetupPage() {
  const { t } = useTranslation()
  const berthName = useBerthName()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const status = useQuery(setupStatusQueryOptions)
  // 步驟是由狀態導出的（plan §9.3），所以「停在結果上」與「回頭看」都靠網址上的這一頁，不是靠改狀態：
  // 網址一直寫著畫面上那一頁，後端前進時畫面不動（M4 票 30；原本是按下動作那一刻釘住的覆寫）。
  const requested = stepOf(useSearch({ strict: false }).step)
  // 服務頁上選著、還沒存下的那一格（M4 票 09）。由這一頁持有而不是那一頁：泊位板要跟著它，不再寫著
  // 原本那一台的「失敗 · 套件內」（M4 票 21）。記著是哪一步的——離開那一頁就不算數了。
  const [draft, setDraft] = useState<{
    step: number
    kind: ServiceKind
    origin: ServiceOrigin
  } | null>(null)

  const current = status.data
  const backend = current?.current_step ?? STEP.jellyfin
  const step = shownStep(backend, requested)

  /** 去某一步：進瀏覽器的歷史，上一頁回到這裡。 */
  function goTo(target: number) {
    void navigate({ to: '/setup', search: { step: go(target, backend) } })
  }

  // 網址沒寫、或指到後端還沒到的那一頁（手打的、後端退回去了）：改成畫面上那一頁，不多一筆歷史。
  // 狀態讀回來之前不改——那時的 `backend` 是預設的頁 1，會把網址上的頁蓋掉。
  const loaded = status.data !== undefined
  useEffect(() => {
    if (loaded && requested !== step) {
      void navigate({ to: '/setup', search: { step }, replace: true })
    }
  }, [loaded, requested, step, navigate])

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
  /**
   * 選擇或使用者按的重測做完，重問主機名（M4 票 35）：容器停了又起回來，卡片的「沒在跑」不停在進頁那一刻。
   * 啟動中每 3 秒的輪詢不問：一次問三個名字，解不到的那一個要一秒多（brief §20.14）。
   */
  function reaskHosts() {
    void queryClient.invalidateQueries({ queryKey: composeQueryOptions.queryKey })
  }
  // 服務頁的二選一（M4 票 15）：存下、測一次。結果回來照樣停在這一頁（網址沒變）。
  const choose = useMutation({
    mutationFn: ({ kind, input }: { kind: ServiceKind; input: ChoiceInput }) =>
      chooseService(kind, input),
    onMutate: ({ kind }) => forgetResults(kind),
    onSuccess: (next, { kind }) => {
      absorb(next)
      invalidateBerthOf(kind)
      reaskHosts()
    },
  })
  // 重測：紅燈上的「重新測試」（`restart`），以及套件內那一台還在啟動時的輪詢。
  const retest = useMutation({
    mutationFn: ({ kind, restart }: { kind: ServiceKind; restart: boolean }) =>
      retestService(kind, restart),
    // 使用者按的重測才清：啟動中每 3 秒的那一次不動畫面上的東西。
    onMutate: ({ kind, restart }) => {
      if (restart) forgetResults(kind)
    },
    onSuccess: (next, { kind, restart }) => {
      absorb(next)
      invalidateBerthOf(kind)
      if (restart) reaskHosts()
    },
  })
  function choiceOf(kind: ServiceKind): ChoiceControls & ChoiceDraft {
    const mine = choose.variables?.kind === kind
    return {
      composeHosts: composeHosts.data,
      choosing: choose.isPending && choose.variables.kind === kind,
      retesting: retest.isPending && retest.variables.kind === kind && retest.variables.restart,
      refusal: mine ? choiceRefusalOf(choose.error) : null,
      requestError:
        mine && choose.isError && !choiceRefusalOf(choose.error)
          ? choose.error
          : retest.variables?.kind === kind && retest.isError
            ? retest.error
            : null,
      draft: draftOf(kind),
      onDraft: (origin) => setDraft(origin === null ? null : { step, kind, origin }),
      onChoose: (input, done) => choose.mutate({ kind, input }, { onSuccess: done }),
      onRetest: (restart) => {
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
  // 剖面上的媒體庫清單停手就存（票 06f）。精靈狀態要重讀：多一列還沒建的，頁 3 就還沒做完
  // （後端 `libraries_built`，M4 票 24）。
  const saveLibraries = useMutation({
    mutationFn: saveBundledLibraries,
    onSuccess: absorbJellyfin,
  })
  // 頁 3 的「建立並檢查」（M4 票 08）：一顆鈕照順序做完，一段失敗就停、後面的不送。建媒體庫與加路徑
  // 的失敗不是 4xx，而是 Jellyfin 那一份的 `libraries` 那一步變紅——那時不建 Route，畫面讀它說原文。
  const dock = useMutation({
    mutationFn: async (plan: DockPlan): Promise<RouteSetup | null> => {
      if (plan.origin === 'bundled') {
        // 先向 Jellyfin 重讀（M4 票 24）：進頁之後在 Jellyfin 刪掉的媒體庫要回到「還沒建」，
        // Route 也照它現在報的建。
        queryClient.setQueryData(routeSetupQueryOptions.queryKey, await rereadRouteLibraries())
        // 再存清單：`bootstrap` 讀的是存下來的那一份，而停手存檔可能還沒送出去。回來的「已建立」
        // 照剛重讀的快照算，與後端判定頁 3 的是同一條。
        const saved = await saveBundledLibraries(plan.libraries)
        absorbJellyfin(saved)
        const unbuilt = saved.bundled.some((row) => !row.built)
        if (unbuilt && !(await stepThrough(bootstrapJellyfin()))) return null
        return buildRoutes([])
      }
      // 一次送全部：後端逐個試、逐個回報（M4 票 19），有一個沒加上就不建 Route。
      if (plan.newPaths.length > 0 && !(await stepThrough(addLibraryPaths(plan.newPaths)))) {
        return null
      }
      return buildRoutes(plan.selections)
    },
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
    onSuccess: (next) => absorbBerth(qbittorrentSetupQueryOptions.queryKey, next),
  })
  const applySites = useMutation({
    mutationFn: applyIndexers,
    onSuccess: (next) => absorbBerth(indexerSetupQueryOptions.queryKey, next),
  })
  // 套件內 Prowlarr 的介面登入是自己的一顆按鈕（M4 票 20），不跟著「加入」送。
  const prowlarrLogin = useMutation({
    mutationFn: setIndexerLogin,
    onSuccess: (next) => absorbBerth(indexerSetupQueryOptions.queryKey, next),
  })
  // 既有 Prowlarr 的表單（頁 4 選「既有」時）：這就是選了既有，精靈狀態裡的選擇也跟著變。
  const connectSource = useMutation({
    mutationFn: connectIndexer,
    onSuccess: (next) => absorbBerth(indexerSetupQueryOptions.queryKey, next),
  })
  const skipSites = useMutation({
    mutationFn: () => skipIndexers(true),
    onSuccess: (next) => absorbBerth(indexerSetupQueryOptions.queryKey, next),
  })
  // 測試與試搜只讀、不改後端的步驟，所以不經 mutation（`IndexerSites` 自己記結果）；
  // 移除最後一站會讓後端退回頁 4，照樣停在這一頁。
  const removeSite = useMutation({
    mutationFn: removeIndexer,
    onSuccess: (next) => absorbBerth(indexerSetupQueryOptions.queryKey, next),
  })
  /**
   * 換了來源、換了位址、按了重新測試：那一頁上一次的結果與錯誤說的是之前那一台，清掉（M4 票 21）。
   * 原本換一台 Jellyfin 之後上一台的版本錯誤還掛著、Prowlarr 的狀態列停在上一次。
   */
  function forgetResults(kind: ServiceKind) {
    if (kind === 'jellyfin') {
      owner.reset()
      reSignIn.reset()
    } else if (kind === 'qbittorrent') {
      applyPreferences.reset()
    } else {
      applySites.reset()
      connectSource.reset()
      prowlarrLogin.reset()
      removeSite.reset()
    }
  }

  /** 畫面上選著、還沒存下的那一格；是這一步的才算。 */
  function draftOf(kind: ServiceKind): ServiceOrigin | null {
    return draft && draft.step === step && draft.kind === kind ? draft.origin : null
  }

  const tmdbTest = useMutation({
    mutationFn: testTmdb,
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
    // 422 是後端照頁序再問一次而某一頁不再成立（M4 票 31）：多半是另一個分頁回去改了，
    // 手上這份進度是舊的。重讀之後網址指到後端還沒到的頁會被拉回那一頁（`navigation`）；完成頁
    // 跟著卸下，它自己的那一句也就沒了，所以拉回去的那一頁頂上另說一句（`pulledBack`，審查 P1）。
    onError: async (error) => {
      if (!(error instanceof ApiError) || error.status !== 422) return
      await queryClient.invalidateQueries({ queryKey: setupStatusQueryOptions.queryKey })
      const next = queryClient.getQueryData(setupStatusQueryOptions.queryKey)
      if (next && next.current_step < STEP.complete) setPulledBack(true)
    },
  })
  // 完成被擋、被拉回某一頁：走回完成頁之前，那一頁頂上說為什麼回來。
  const [pulledBack, setPulledBack] = useState(false)
  useEffect(() => {
    if (step === STEP.complete) setPulledBack(false)
  }, [step])

  // 套件內那一台還在啟動：每 3 秒重測，直到有結論或後端判逾時（M3 票 06g 的三種樣子）。只測畫面上
  // 等著的那一個：別頁的服務不在這裡轉圈，它的重測只會與這一頁的命令搶同一組設定（M4 票 23）。
  const shownBerth = berthOf(step)
  const waitingKind = current?.services.find(
    (row) => row.kind === shownBerth && row.state === 'waiting',
  )?.kind
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
  // ——這一支會去連那一台，選之前不發（M4 票 15）。完成頁也讀：WebUI 開在哪、帳號是誰（M4 票 31）。
  const qbittorrent = useQuery({
    ...qbittorrentSetupQueryOptions,
    enabled: (step === STEP.qbittorrent || step === STEP.complete) && connected(qbittorrentChoice),
  })
  // 讀差異或套用時 qBittorrent 連不上了，連線卡卻還是上一次的綠燈（M4 票 25，實測 B9-04～07）：重新測試
  // 一次。卡片照這一次的例外變紅、出現「重新測試」，後端的頁 2 也就不算做完（前進鍵收起）。同一份讀到的
  // 結果只測一次：測完是綠的而差異仍讀不到時不來回打。
  const qbittorrentLostAt =
    qbittorrent.data && !qbittorrent.data.reachable && connected(qbittorrentChoice)
      ? qbittorrent.dataUpdatedAt
      : null
  const retestedLoss = useRef<number | null>(null)
  const { mutate: retestNow, isPending: retesting } = retest
  useEffect(() => {
    if (qbittorrentLostAt === null || retesting || retestedLoss.current === qbittorrentLostAt)
      return
    retestedLoss.current = qbittorrentLostAt
    retestNow({ kind: 'qbittorrent', restart: true })
  }, [qbittorrentLostAt, retesting, retestNow])
  // 服務頁進頁問一次套件內的主機名解不解得到（M4 票 30），每次測完再問（票 35）：只查 DNS，不對服務發請求（brief §19）。
  const composeHosts = useQuery({
    ...composeQueryOptions,
    enabled: step === STEP.jellyfin || step === STEP.qbittorrent || step === STEP.indexer,
  })
  // 泊位板要畫得出走過的每一格，所以這三份跟著後端走到哪裡，不跟著畫面停在哪裡。
  const routes = useQuery({ ...routeSetupQueryOptions, enabled: backend >= STEP.routes })
  // 頁 3 進頁時向 Jellyfin 重讀媒體庫（M4 票 19；套件內也是，票 24）：頁 1 之後在 Jellyfin 改的掛載、
  // 路徑與媒體庫要看得到。讀的是 Jellyfin、寫的是 Berth 的快照，不動任何服務；但快照決定清單哪幾列
  // 已建立、頁 3 走不走得過去，所以重讀清單與精靈狀態——後端因此前進時畫面停在這裡（網址沒變）。
  const reread = useMutation({
    mutationFn: rereadRouteLibraries,
    onSuccess: (next) => {
      absorbBerth(routeSetupQueryOptions.queryKey, next)
      void queryClient.invalidateQueries({ queryKey: jellyfinSetupQueryOptions.queryKey })
    },
  })
  const rereadOnEntry = step === STEP.routes && routes.data !== undefined
  const { mutate: rereadNow } = reread
  useEffect(() => {
    if (rereadOnEntry) rereadNow()
  }, [rereadOnEntry, rereadNow])
  const indexers = useQuery({ ...indexerSetupQueryOptions, enabled: backend >= STEP.indexer })
  // 完成頁列出 Jellyfin 開在哪（M4 票 31）：與媒體庫深連結同一份推導（`/settings/jellyfin`）。
  const jellyfinAddress = useQuery({
    ...jellyfinAddressQueryOptions,
    enabled: step === STEP.complete,
  })
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
        {status.isError ? (
          <StatusFailed error={status.error} />
        ) : (
          <p className="p-6 text-sm text-ink-dim">{t('health.checking')}</p>
        )}
      </Shell>
    )
  }

  const previous = previousOf(step)
  const next = nextOf(step)
  // 頁 4 還差什麼，說在前進鍵的位置（M4 票 27）。
  const gaps = step === STEP.indexer && indexers.data ? indexerGaps(current, indexers.data) : []
  const nav = (
    <BerthNav
      onPrevious={previous !== null ? () => goTo(previous) : undefined}
      onNext={next !== null && advanced(step, backend) ? () => goTo(next) : undefined}
      missing={gaps.map((gap) => ({ label: t(GAP[gap].label), target: GAP[gap].target }))}
    />
  )
  const note = advanced(step, backend) ? (
    <RevisitNote
      step={step}
      origin={
        current.services.find(
          (row) => row.kind === (step === STEP.jellyfin ? 'jellyfin' : 'prowlarr'),
        )?.origin
      }
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

  // 泊位板照畫面上選著的那一格畫：換另一格還沒測時，那一格是「輪到你」，不是原本那一台的結果。
  const drafted = current.services.find(
    (row) => draftOf(row.kind) !== null && draftOf(row.kind) !== row.origin,
  )
  const board: SetupStatus = drafted
    ? {
        ...current,
        services: current.services.map((row) =>
          row === drafted
            ? {
                ...row,
                origin: draftOf(row.kind)!,
                state: null,
                reason: null,
                detail: '',
                error: '',
              }
            : row,
        ),
      }
    : current
  const signals: BerthSignals = {
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
  }
  if (drafted) signals[drafted.kind] = 'assigned'

  const shell = {
    step,
    backend,
    status: board,
    // 換另一格還沒測時，索引站那一格的站數說的是原本那一台，不畫。
    indexers: drafted?.kind === 'prowlarr' ? undefined : indexers.data,
    tmdb: tmdb.data,
    routes: routes.data,
    signals,
    onGo: goTo,
    onReturn: () => goTo(backend),
  }

  return (
    <Shell {...shell}>
      {pulledBack && step !== STEP.complete && (
        <div role="alert" className="px-6 pt-6">
          <Notice signal="blocked" label={t('common.failed')}>
            {t('complete.pulledBack', { place: berthName(backend) })}
          </Notice>
        </div>
      )}
      {step === STEP.jellyfin ? (
        <OwnerStep
          status={current}
          choice={choiceOf('jellyfin')}
          claiming={owner.isPending}
          refusal={ownerRefusalOf(owner.error)}
          claimError={ownerRefusalOf(owner.error) ? null : owner.error}
          onClaim={(input) => owner.mutate(input)}
          onClaimReset={owner.reset}
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
          requestError={applyPreferences.error}
          loginRefusal={loginRefusalOf(applyPreferences.error)}
          onApply={(login) => applyPreferences.mutateAsync(login)}
          choice={choiceOf('qbittorrent')}
          done={advanced(step, backend)}
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
            onRouteDeleted={() => {
              // 刪掉最後一條紅的，後端就過了這一頁（M4 票 24）：重讀進度，前進鍵才出現。畫面不跳頁：
              // 網址寫著這一頁。
              void queryClient.invalidateQueries({ queryKey: routeSetupQueryOptions.queryKey })
              void queryClient.invalidateQueries({ queryKey: setupStatusQueryOptions.queryKey })
            }}
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
            doors={
              <ServiceDoors
                owner={current.owner}
                jellyfin={jellyfinAddress.data}
                qbittorrent={qbittorrent.data}
                indexers={indexers.data}
              />
            }
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

/**
 * 讀不到精靈的狀態（M4 票 25，實測 E10-05）。登得進 Jellyfin 而不是管理員的人在擁有者成立之後進得了
 * 這一頁（守衛只要 session），讀狀態卻是 403——原本說「Berth 後端可能沒在跑」，叫人去查容器。他要的是
 * 換一個管理員帳號：說出來、給登出。其餘照請求的失敗說（`RequestFailed`）。
 */
function StatusFailed({ error }: { error: unknown }) {
  const { t } = useTranslation()

  if (requestProblem(error) === 'notAdministrator') return <NotAdministrator />
  return (
    <div className="p-6">
      <RequestFailed error={error} lead={t('setup.statusFailed')} />
    </div>
  )
}

function NotAdministrator() {
  const { t } = useTranslation()
  const me = useQuery(meQueryOptions)
  const leave = useSignOut()

  return (
    <div className="grid gap-3 p-6">
      <Notice signal="blocked" label={t('common.failed')}>
        {t('setup.notAdministrator', { name: me.data?.name ?? '' })}
      </Notice>
      <div>
        <GhostButton type="button" busy={leave.isPending} onClick={() => leave.mutate()}>
          {leave.isPending ? t('nav.signingOut') : t('nav.signOut')}
        </GhostButton>
      </div>
    </div>
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
  const refusal = routeRefusalOf(error)
  if (refusal?.reason === 'route_missing') return { kind: 'route_missing' }
  if (refusal && refusal.reason in BUILD_REFUSAL) {
    return { kind: 'refused', reason: refusal.reason as BuildRefusal, detail: refusal.detail }
  }
  return { kind: 'request', error }
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
 * **422 不是後端出錯**：`complete_setup` 照頁序把每一頁再問一次，用它說「某一頁還沒做完」
 * （`berth/services/setup.py`，M4 票 31）。頁 3、頁 5 前端自己答得出來；其餘的頁在重讀進度之後
 * 由網址拉回去（`finish` 的 `onError`）。其餘（5xx、連不上）才是後端的問題。
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
  // 照頁序問（Route 是頁 3、TMDB 是頁 5），與後端 `complete_setup` 同一個順序。
  if (routes?.ready === false) return 'routes'
  if (tmdb?.verified === false) return 'tmdb'
  return 'unfinished'
}

/**
 * 媒體庫路徑那一格的信號。這一格沒有對應的服務，看的是媒體庫清單與 Route 自己的健康：有紅的就是
 * 阻擋，後端過了這一頁才是已繫上（套件內的清單也要建完，後端 `libraries_built`）。
 */
function librarySignal(
  status: SetupStatus,
  routes: RouteSetup | undefined,
  jellyfin: JellyfinSetup | undefined,
  building: boolean,
): Signal {
  if (building) return 'working'
  if (jellyfin && librariesFailed(jellyfin)) return 'blocked'
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
  routes,
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
  /** 媒體庫路徑那一格的詳情列（建了幾條 Route）。頁 3 起才問得到。 */
  routes?: RouteSetup
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
        {/* 數的是泊位板上的格子：板上五格，頁首原本寫「共 6 步」（完成頁也算一步，M4 票 21）。
            完成頁不是泊位，只說「收尾」。頁序與泊位號一一對應（`navigation.BERTH_STEP`）。 */}
        <p className="label ml-auto text-ink-dim">
          {code
            ? `${t('setup.stage.berth', { code })} · ${t('setup.step', { current: step, total: BERTHS.length })}`
            : t('setup.stage.final')}
        </p>
        <LanguageToggle />
      </header>

      <BerthBoard
        services={status?.services ?? []}
        signals={signals}
        indexers={indexers}
        tmdb={tmdb}
        routes={routes}
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
  // 目前走到哪也用泊位說，不說「第 6 步」：頁首數的是泊位（共 5 個），完成頁不是泊位（M4 票 31）。
  const current = useBerthName()(backend)

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b-2 border-rule bg-deck px-6 py-3">
      <p className="text-sm text-ink">
        {t('setup.stray.where', { place })}
        <span className="text-ink-dim"> · {t('setup.stray.current', { place: current })}</span>
      </p>
      <div className="sm:ml-auto">
        <GhostButton type="button" onClick={onReturn}>
          {t('setup.stray.back')}
        </GhostButton>
      </div>
    </div>
  )
}

/** 一頁的泊位名（「BTH 2 qBittorrent」）；完成頁不是泊位，說「收尾」（M4 票 31）。 */
function useBerthName(): (step: number) => string {
  const { t } = useTranslation()
  return (step) => {
    const berth = BERTHS.find((row) => row.slot === berthOf(step))
    return berth ? `${berth.code} ${t(berth.nameKey)}` : t('setup.stage.final')
  }
}
