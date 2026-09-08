import { useEffect, useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import {
  addLibraryPath,
  applyIndexers,
  applyQbittorrent,
  bootstrapJellyfin,
  connectIndexer,
  connectJellyfin,
  connectService,
  createAdmin,
  detectServices,
  indexerSetupQueryOptions,
  installMergeVersions,
  jellyfinSetupQueryOptions,
  qbittorrentSetupQueryOptions,
  setupStatusQueryOptions,
  skipIndexers,
  skipTmdb,
  testTmdb,
  tmdbSetupQueryOptions,
  type AdminInput,
  type ConnectInput,
  type IndexerSetup,
  type JellyfinSetup,
  type QbittorrentSetup,
  type ServiceKind,
  type SetupStatus,
  type TmdbSetup,
} from '../api/setup'
import { LanguageToggle } from '../components/LanguageToggle'
import { AdminStep } from '../setup/AdminStep'
import { BerthBoard } from '../setup/BerthBoard'
import { DetectStep } from '../setup/DetectStep'
import { JellyfinStep } from '../setup/JellyfinStep'
import { QbittorrentStep } from '../setup/QbittorrentStep'
import { SourceStep } from '../setup/SourceStep'
import { GhostButton } from '../components/controls'
import { SIGNAL_FILL, type Signal } from '../components/signal'
import { isSettled } from '../setup/steps'
import { signalOf } from '../setup/signals'

/** plan §9.3 的八步。泊位 4（媒體庫路徑）是票 09，所以畫面目前停在第 6 步。 */
const TOTAL_STEPS = 8
const STEP_DETECT = 2
const STEP_JELLYFIN = 3
const STEP_QBITTORRENT = 4
const STEP_INDEXER = 5
const STEP_TMDB = 6
const LAST_IMPLEMENTED_STEP = STEP_TMDB

/** 步驟 → 泊位碼。第 5、6 步是同一個泊位的兩條纜繩（shape brief §5）。 */
const BERTH_CODE: Record<number, string> = {
  [STEP_JELLYFIN]: 'BTH 1',
  [STEP_QBITTORRENT]: 'BTH 2',
  [STEP_INDEXER]: 'BTH 3',
  [STEP_TMDB]: 'BTH 3',
}

/** 服務還在啟動時的重探間隔。上限由後端的輪詢窗口決定（`window_seconds`）。 */
const POLL_INTERVAL_MS = 3000

/**
 * bootstrap 進行中的進度輪詢。後端每一步在做之前就把自己標成 `running` 並存下來，
 * 所以請求還在飛的時候讀 `GET /setup/jellyfin` 就看得到序列走到哪裡。
 */
const PROGRESS_INTERVAL_MS = 1500

/**
 * 設定精靈。方向見 `.impeccable/surfaces/web-src-pages-setuppage-tsx.md`：
 * 四個泊位常駐在頂端，工作面在下；不是八張「下一步」的表單。
 */
export function SetupPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const status = useQuery(setupStatusQueryOptions)
  // 步驟是由狀態導出的（plan §9.3），所以「回頭看前一步」要靠這個覆寫，不是靠改狀態。
  const [revisit, setRevisit] = useState<number | null>(null)

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
      setRevisit(null)
    },
  })
  const detect = useMutation({
    mutationFn: (restart: boolean) => detectServices(restart),
    onSuccess: (next) => {
      absorb(next)
      // 判定一出來伺服器就把步驟推到 3。直接跟著跳的話，使用者根本看不到自己剛按下的那一輪
      // 靠泊序列；停在第 2 步等他按「前往泊位 1」。
      if (next.current_step > STEP_DETECT) setRevisit(STEP_DETECT)
    },
  })
  const connect = useMutation({
    mutationFn: ({ kind, input }: { kind: ServiceKind; input: ConnectInput }) =>
      connectService(kind, input),
    onSuccess: absorb,
  })
  const bootstrap = useMutation({ mutationFn: bootstrapJellyfin, onSuccess: absorbJellyfin })
  const signIn = useMutation({ mutationFn: connectJellyfin, onSuccess: absorbJellyfin })
  const addPath = useMutation({ mutationFn: addLibraryPath, onSuccess: absorbJellyfin })
  const plugin = useMutation({ mutationFn: installMergeVersions, onSuccess: absorbJellyfin })
  const applyPreferences = useMutation({
    mutationFn: applyQbittorrent,
    onSuccess: (next) => absorbBerth(qbittorrentSetupQueryOptions.queryKey, next),
  })
  const applySites = useMutation({
    mutationFn: applyIndexers,
    onSuccess: (next) => absorbBerth(indexerSetupQueryOptions.queryKey, next),
  })
  const connectSource = useMutation({
    mutationFn: connectIndexer,
    onSuccess: (next) => absorbBerth(indexerSetupQueryOptions.queryKey, next),
  })
  const skipSites = useMutation({
    mutationFn: () => skipIndexers(true),
    onSuccess: (next) => absorbBerth(indexerSetupQueryOptions.queryKey, next),
  })
  const tmdbTest = useMutation({
    mutationFn: testTmdb,
    onSuccess: (next) => absorbBerth(tmdbSetupQueryOptions.queryKey, next),
  })
  const skipTmdbStep = useMutation({
    mutationFn: () => skipTmdb(true),
    onSuccess: (next) => absorbBerth(tmdbSetupQueryOptions.queryKey, next),
  })

  const current = status.data
  const waiting = current?.services.some((row) => row.origin === 'pending') ?? false
  const step = revisit ?? Math.min(current?.current_step ?? 1, LAST_IMPLEMENTED_STEP)
  const inFlight = bootstrap.isPending || plugin.isPending

  const jellyfin = useQuery({
    ...jellyfinSetupQueryOptions,
    enabled: step === STEP_JELLYFIN,
    refetchInterval: inFlight ? PROGRESS_INTERVAL_MS : false,
  })
  // 第 4 步的差異是**現查的**：使用者可能在 qBittorrent 自己的介面上改過東西。
  const qbittorrent = useQuery({
    ...qbittorrentSetupQueryOptions,
    enabled: step === STEP_QBITTORRENT,
  })
  const indexers = useQuery({ ...indexerSetupQueryOptions, enabled: step >= STEP_INDEXER })
  const tmdb = useQuery({ ...tmdbSetupQueryOptions, enabled: step >= STEP_INDEXER })

  // 服務還在啟動就繼續探，直到有結論或後端判逾時（plan §9.3 第 2 步）。
  useEffect(() => {
    if (!waiting || detect.isPending) return
    const timer = window.setTimeout(() => detect.mutate(false), POLL_INTERVAL_MS)
    return () => window.clearTimeout(timer)
  }, [waiting, detect])

  if (!current) {
    return (
      <Shell step={1}>
        <p className="p-6 text-sm text-ink-dim">
          {status.isError ? t('detect.failed') : t('health.checking')}
        </p>
      </Shell>
    )
  }

  const board = {
    step,
    services: current.services,
    signals: {
      jellyfin: jellyfinSignal(current, jellyfin.data, inFlight),
      qbittorrent: qbittorrentSignal(current, qbittorrent.data, applyPreferences.isPending),
      prowlarr: sourceSignal(current, indexers.data, tmdb.data, applySites.isPending),
    } satisfies Partial<Record<ServiceKind, Signal>>,
  }

  if (step === 1) {
    return (
      <Shell {...board}>
        <AdminStep
          status={current}
          pending={admin.isPending}
          failed={admin.isError}
          onSubmit={(input) => admin.mutate(input)}
        />
      </Shell>
    )
  }

  return (
    <Shell {...board}>
      <WizardTrail
        status={current}
        step={step}
        onRevisit={(target) => setRevisit(target === step ? null : target)}
      />
      {step === STEP_DETECT ? (
        <DetectStep
          status={current}
          probing={detect.isPending}
          connectingKind={connect.isPending ? connect.variables.kind : null}
          failed={detect.isError}
          onDetect={(restart) => detect.mutate(restart)}
          onConnect={(kind, input) => connect.mutate({ kind, input })}
          onContinue={() => setRevisit(null)}
        />
      ) : step === STEP_JELLYFIN ? (
        jellyfin.data ? (
          <JellyfinStep
            setup={jellyfin.data}
            running={bootstrap.isPending}
            bootstrapFailed={bootstrap.isError}
            signInFailed={signIn.isError}
            connecting={signIn.isPending}
            addingPath={addPath.isPending ? addPath.variables : null}
            installing={plugin.isPending}
            onBootstrap={() => bootstrap.mutate()}
            onConnect={(input) => signIn.mutate(input)}
            onAddPath={(library) => addPath.mutate(library)}
            onInstallPlugin={() => plugin.mutate()}
          />
        ) : (
          <Waiting failed={jellyfin.isError} message={t('jellyfin.unreachable')} />
        )
      ) : step === STEP_QBITTORRENT ? (
        qbittorrent.data ? (
          <QbittorrentStep
            setup={qbittorrent.data}
            applying={applyPreferences.isPending}
            requestFailed={applyPreferences.isError}
            onApply={() => applyPreferences.mutate()}
          />
        ) : (
          <Waiting failed={qbittorrent.isError} message={t('qbittorrent.unreachable')} />
        )
      ) : indexers.data && tmdb.data ? (
        <SourceStep
          indexers={indexers.data}
          tmdb={tmdb.data}
          applying={applySites.isPending}
          connecting={connectSource.isPending}
          testingTmdb={tmdbTest.isPending}
          onApply={(selected) => applySites.mutate(selected)}
          onConnect={(input) => connectSource.mutate(input)}
          onSkipIndexers={() => skipSites.mutate()}
          onTestTmdb={(apiKey) => tmdbTest.mutate(apiKey)}
          onSkipTmdb={() => skipTmdbStep.mutate()}
        />
      ) : (
        <Waiting failed={indexers.isError || tmdb.isError} message={t('source.unreachable')} />
      )}
    </Shell>
  )
}

/** 還沒讀到那個泊位的狀態。讀不到與還在讀是兩件事，說法也不一樣。 */
function Waiting({ failed, message }: { failed: boolean; message: string }) {
  const { t } = useTranslation()

  return <p className="p-6 text-sm text-ink-dim">{failed ? message : t('health.checking')}</p>
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
  if (status.current_step > STEP_JELLYFIN) return 'secured'
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
  if (status.current_step > STEP_QBITTORRENT) return 'secured'
  return signalOf(detection)
}

/**
 * 泊位 3 的信號。索引站逐站失敗**不算阻擋**：十個公開站裡有幾個連不上是常態，
 * 只要接上了一個就走得下去（後端的步驟判定用的是同一條規則）。
 */
function sourceSignal(
  status: SetupStatus,
  indexers: IndexerSetup | undefined,
  tmdb: TmdbSetup | undefined,
  applying: boolean,
): Signal {
  const detection = status.services.find((row) => row.kind === 'prowlarr')
  if (applying) return 'working'
  if (status.current_step > STEP_TMDB) return 'secured'
  const settled =
    (indexers?.skipped ?? false) || (indexers?.steps.some((row) => isSettled(row.status)) ?? false)
  if (settled && (tmdb?.skipped || tmdb?.steps.some((row) => isSettled(row.status)))) {
    return 'secured'
  }
  return signalOf(detection)
}

function Shell({
  step,
  services = [],
  signals,
  children,
}: {
  step: number
  services?: SetupStatus['services']
  signals?: Partial<Record<ServiceKind, Signal>>
  children: ReactNode
}) {
  const { t } = useTranslation()

  return (
    <div className="flex min-h-dvh flex-col bg-hull text-ink">
      <header className="flex flex-wrap items-center gap-x-6 gap-y-3 border-b-2 border-rule-strong px-6 py-4">
        <p className="value text-lg font-semibold tracking-tight">{t('app.name')}</p>
        <p className="label text-ink-dim">{t('setup.title')}</p>
        <p className="label ml-auto text-ink-dim">
          {step in BERTH_CODE
            ? t('setup.stage.berth', { code: BERTH_CODE[step] })
            : t('setup.stage.pre')}{' '}
          · {t('setup.step', { current: step, total: TOTAL_STEPS })}
        </p>
        <LanguageToggle />
      </header>

      <BerthBoard services={services} signals={signals} />

      <main className="flex flex-1 flex-col">{children}</main>

      <footer className="px-6 py-6">
        <p className="text-xs text-ink-dim">{t('setup.resumed')}</p>
      </footer>
    </div>
  )
}

/**
 * 走過的步驟留一條線索。步驟由狀態導出，所以「回去改」不能靠改狀態——這一條是唯一的入口，
 * 而且它同時是證據：帳號是哪一個、偵測完了幾個服務。
 */
function WizardTrail({
  status,
  step,
  onRevisit,
}: {
  status: SetupStatus
  step: number
  onRevisit: (step: number) => void
}) {
  const { t } = useTranslation()
  const detected = status.services.length

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-3 border-b-2 border-rule px-6 py-3">
      <span className={`label px-2 py-1.5 ${SIGNAL_FILL.secured}`}>{t('admin.chip')}</span>
      <span className="value text-sm text-ink">
        {t('admin.saved', { username: status.admin_username })}
      </span>
      <GhostButton type="button" onClick={() => onRevisit(1)}>
        {t('admin.change')}
      </GhostButton>
      {detected > 0 && step > 2 && (
        <>
          <span className="value text-sm text-ink-dim">
            {t('detect.done', { count: detected })}
          </span>
          <GhostButton type="button" onClick={() => onRevisit(2)}>
            {t('detect.rerun')}
          </GhostButton>
        </>
      )}
    </div>
  )
}
