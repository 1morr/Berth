import { useEffect, useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import {
  connectService,
  createAdmin,
  detectServices,
  setupStatusQueryOptions,
  type AdminInput,
  type ConnectInput,
  type ServiceKind,
  type SetupStatus,
} from '../api/setup'
import { LanguageToggle } from '../components/LanguageToggle'
import { AdminStep } from '../setup/AdminStep'
import { BerthBoard } from '../setup/BerthBoard'
import { DetectStep } from '../setup/DetectStep'
import { GhostButton } from '../components/controls'
import { SIGNAL_FILL } from '../components/signal'

/** 前置兩步；泊位 1–4 從票 06 起接手（plan §9.3）。 */
const PRE_BERTH_STEPS = 2

/** 服務還在啟動時的重探間隔。上限由後端的輪詢窗口決定（`window_seconds`）。 */
const POLL_INTERVAL_MS = 3000

/**
 * 設定精靈。方向見 `.impeccable/surfaces/web-src-pages-setuppage-tsx.md`：
 * 四個泊位常駐在頂端，工作面在下；不是八張「下一步」的表單。
 */
export function SetupPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const status = useQuery(setupStatusQueryOptions)
  // 建完管理員之後伺服器就把步驟推到 2；想回頭改帳密時用這個覆寫。
  const [editingAdmin, setEditingAdmin] = useState(false)

  function absorb(next: SetupStatus) {
    queryClient.setQueryData(setupStatusQueryOptions.queryKey, next)
  }

  const admin = useMutation({
    mutationFn: (input: AdminInput) => createAdmin(input),
    onSuccess: (next) => {
      absorb(next)
      setEditingAdmin(false)
    },
  })
  const detect = useMutation({
    mutationFn: (restart: boolean) => detectServices(restart),
    onSuccess: absorb,
  })
  const connect = useMutation({
    mutationFn: ({ kind, input }: { kind: ServiceKind; input: ConnectInput }) =>
      connectService(kind, input),
    onSuccess: absorb,
  })

  const current = status.data
  const waiting = current?.services.some((row) => row.origin === 'pending') ?? false

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

  const step = editingAdmin ? 1 : Math.min(current.current_step, PRE_BERTH_STEPS)

  return (
    <Shell step={step} services={current.services}>
      {step === 1 ? (
        <AdminStep
          status={current}
          pending={admin.isPending}
          failed={admin.isError}
          onSubmit={(input) => admin.mutate(input)}
        />
      ) : (
        <>
          <AdminSummary username={current.admin_username} onEdit={() => setEditingAdmin(true)} />
          <DetectStep
            status={current}
            probing={detect.isPending}
            connectingKind={connect.isPending ? connect.variables.kind : null}
            failed={detect.isError}
            onDetect={(restart) => detect.mutate(restart)}
            onConnect={(kind, input) => connect.mutate({ kind, input })}
          />
        </>
      )}
    </Shell>
  )
}

function Shell({
  step,
  services = [],
  children,
}: {
  step: number
  services?: SetupStatus['services']
  children: ReactNode
}) {
  const { t } = useTranslation()

  return (
    <div className="flex min-h-dvh flex-col bg-hull text-ink">
      <header className="flex flex-wrap items-center gap-x-6 gap-y-3 border-b-2 border-rule-strong px-6 py-4">
        <p className="value text-lg font-semibold tracking-tight">{t('app.name')}</p>
        <p className="label text-ink-dim">{t('setup.title')}</p>
        <p className="label ml-auto text-ink-dim">
          {t('setup.stage')} · {t('setup.step', { current: step, total: PRE_BERTH_STEPS })}
        </p>
        <LanguageToggle />
      </header>

      <BerthBoard services={services} />

      <main className="flex flex-1 flex-col">{children}</main>

      <footer className="px-6 py-6">
        <p className="text-xs text-ink-dim">{t('setup.resumed')}</p>
      </footer>
    </div>
  )
}

function AdminSummary({ username, onEdit }: { username: string; onEdit: () => void }) {
  const { t } = useTranslation()

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-3 border-b-2 border-rule px-6 py-3">
      <span className={`label px-2 py-1.5 ${SIGNAL_FILL.secured}`}>{t('admin.chip')}</span>
      <span className="value text-sm text-ink">{t('admin.saved', { username })}</span>
      <span className="ml-auto">
        <GhostButton type="button" onClick={onEdit}>
          {t('admin.change')}
        </GhostButton>
      </span>
    </div>
  )
}
