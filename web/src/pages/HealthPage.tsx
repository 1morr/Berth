import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { meQueryOptions } from '../api/auth'
import { healthDetailQueryOptions, healthQueryOptions, runHealthCheck } from '../api/health'
import type { RouteView } from '../api/schemas'
import { GhostButton, Notice } from '../components/controls'
import { ROUTE_HEALTH_LABEL, ROUTE_SIGNAL } from '../components/routeChecks'
import { RouteCheckList } from '../components/RouteCheckList'
import { SIGNAL_FILL } from '../components/signal'
import { Timestamp } from '../components/Timestamp'
import { HealthBoard } from '../health/HealthBoard'
import { PollerCard } from '../health/PollerCard'
import { ServiceCard } from '../health/ServiceCard'

/**
 * 健康頁 `/health`（票 10、`.scratch/m0/health-shape.md`）。
 *
 * 這一頁的讀者只在兩種時刻打開它：有東西壞了，或剛改了什麼想確認。所以第一個 viewport
 * 就是那塊泊位板——與精靈同一塊板、同一組四個泊位，只是問題從「接上了沒」變成「還繫著嗎」。
 *
 * **全綠時這一頁應該很短**：Route 的五條纜繩收起來，只有紅的那條就地展開原文與修正步驟。
 * **開頁不會自動重測**：那一輪檢查會在 qBittorrent 建 category、在媒體庫寫探測檔，
 * 不該是「重整頁面」的副作用（shape brief §7）。
 */
export function HealthPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const detail = useQuery(healthDetailQueryOptions)
  //  設定頁只有 admin 進得去（後端 403、前端守衛會彈回來），所以那條連結也只給 admin。
  const me = useQuery(meQueryOptions)

  const recheck = useMutation({
    mutationFn: runHealthCheck,
    onSuccess: (fresh) => {
      queryClient.setQueryData(healthDetailQueryOptions.queryKey, fresh)
      // 匿名的 `GET /health` 是路由守衛與 compose 健康檢查看的那一支，它也該跟著更新。
      // `void`：那一支重抓完之前按鈕不必一直轉，回傳的 promise 是刻意不等的。
      void queryClient.invalidateQueries({ queryKey: healthQueryOptions.queryKey, exact: true })
    },
  })

  if (detail.isPending) {
    return <p className="px-6 py-8 text-sm text-ink-dim">{t('health.checking')}</p>
  }

  if (!detail.data) {
    return (
      <div className="px-6 py-8">
        <Notice signal="blocked" label={t('common.failed')}>
          {t('health.unreachable')}
        </Notice>
      </div>
    )
  }

  const report = detail.data

  return (
    <>
      <HealthBoard report={report} />

      <div className="mx-auto w-full max-w-3xl px-6 py-8">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
          <h2 className="value text-lg font-semibold text-ink">{t('health.title')}</h2>
          <p className="label text-ink-dim">
            {t('health.interval', { minutes: Math.round(report.interval_seconds / 60) })}
          </p>
          <span className="ml-auto flex flex-wrap items-center gap-x-3 gap-y-2">
            <span className="text-xs text-ink-dim">
              <span className="label">{t('health.lastChecked')}</span>{' '}
              <Timestamp at={report.checked_at} />
            </span>
            <GhostButton
              type="button"
              disabled={recheck.isPending}
              onClick={() => recheck.mutate()}
            >
              {recheck.isPending ? t('health.rechecking') : t('health.recheck')}
            </GhostButton>
          </span>
        </div>

        {recheck.isError && (
          <div className="mt-4">
            <Notice signal="blocked" label={t('common.failed')}>
              {t('health.recheckFailed')}
            </Notice>
          </div>
        )}

        <div className="mt-6 grid gap-4">
          {report.services.map((row) => (
            <ServiceCard
              key={row.kind}
              row={row}
              // 漂移是這一頁唯一「有東西可以按」的狀態，而按鈕住在設定頁。
              actions={
                row.drift.length > 0 && me.data?.role === 'admin' ? (
                  <Link
                    to="/settings/services"
                    className="label border-2 border-rule px-4 py-2.5 hover:border-rule-strong"
                  >
                    {t('health.toSettings')}
                  </Link>
                ) : undefined
              }
            />
          ))}
        </div>

        {/* 下載迴圈排在四項服務之後、Route 之前：它問的是「Berth 自己的迴圈還在跑嗎」，
            比 Route 的五條纜繩上游（`.scratch/m1/live-jobs-shape.md` §6）。 */}
        <div className="mt-8">
          <PollerCard poller={report.poller} />
        </div>

        <section className="mt-8" aria-labelledby="health-routes">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <span
              className={`label px-2 py-1.5 ${SIGNAL_FILL[ROUTE_SIGNAL[report.routes_status]]}`}
            >
              {t(ROUTE_HEALTH_LABEL[report.routes_status])}
            </span>
            <h3 id="health-routes" className="value text-sm font-semibold text-ink">
              {t('health.routes.title')}
            </h3>
            <span className="value text-xs text-ink-dim">
              {t('health.routes.count', { count: report.routes.length })}
            </span>
          </div>

          {report.routes.length === 0 ? (
            <p className="mt-3 max-w-prose text-xs text-ink-dim">{t('health.routes.empty')}</p>
          ) : (
            <ul className="mt-3 grid gap-3">
              {report.routes.map((route) => (
                <li key={route.slug} className="min-w-0">
                  <RouteRow route={route} />
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </>
  )
}

/**
 * 一條 Route。綠燈只有一行，紅燈就地展開五條纜繩——全綠的時候沒有人要讀那 15 行
 * （shape brief §7 的第三個決定）。用 `<details>` 而不是自己管 state：原生的鍵盤與
 * 螢幕閱讀器行為比重寫一份好（票 05 的決定）。
 */
function RouteRow({ route }: { route: RouteView }) {
  const { t } = useTranslation()
  const failed = route.health === 'failed'

  return (
    <details
      open={failed}
      className={`group min-w-0 border-2 bg-well ${failed ? 'border-rule-strong' : 'border-rule'}`}
    >
      {/* `display: flex` 會吃掉 `<summary>` 的三角形，所以展開與否要自己說出來——
          否則收起來的那一列看不出它是按得開的。 */}
      <summary className="flex cursor-pointer flex-wrap items-center gap-x-3 gap-y-2 px-4 py-3">
        <span className={`label px-2 py-1.5 ${SIGNAL_FILL[ROUTE_SIGNAL[route.health]]}`}>
          {t(ROUTE_HEALTH_LABEL[route.health])}
        </span>
        <span className="value text-sm font-semibold text-ink">{route.name}</span>
        <span className="value text-xs text-ink-dim">{route.category}</span>
        <span className="value min-w-0 grow truncate text-xs text-ink-dim">
          {route.target_path}
        </span>
        <span className="label shrink-0 text-ink-dim group-open:hidden">
          {t('health.routes.expand')}
        </span>
        <span className="label hidden shrink-0 text-ink-dim group-open:inline">
          {t('health.routes.collapse')}
        </span>
      </summary>
      <div className="border-t-2 border-rule px-4 py-4">
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 pb-4 text-xs">
          <dt className="label self-center text-ink-dim">{t('health.lastOk')}</dt>
          <dd className="text-ink">
            <Timestamp at={route.last_ok_at} />
          </dd>
          <dt className="label self-center text-ink-dim">{t('health.lastChecked')}</dt>
          <dd className="text-ink">
            <Timestamp at={route.checked_at} />
          </dd>
        </dl>
        <RouteCheckList route={route} />
      </div>
    </details>
  )
}
