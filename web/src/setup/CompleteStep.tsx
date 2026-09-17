import { useTranslation } from 'react-i18next'

import type { IndexerSetup, RouteSetup } from '../api/setup'
import { STICKY_ACTION, GhostButton, Notice, PrimaryButton } from '../components/controls'
import { SIGNAL_FILL } from '../components/signal'
import { ROUTE_SIGNAL } from '../components/routeChecks'
import { Cutaway, CutawayRow } from '../components/Cutaway'

/**
 * 第 8 步：完成（plan §9.3 第 8 步）。
 *
 * 兩件事：把跑出來的結果攤出來（幾條 Route、各自寫到哪裡），以及**說出跳過了什麼與在哪裡補**
 * ——可以「之後再說」的只有第 5 步（票 02b），完成頁是他最後一次看到那件事的地方。
 *
 * 按下去之後 `settings.setup.completed` 就寫下去了，`setup/*` 從此要登入（票 07），
 * 所以按鈕文案講的是「完成設定」而不是「下一步」。
 */
export function CompleteStep({
  routes,
  indexers,
  completing,
  failed,
  onComplete,
  onRevisit,
}: {
  routes: RouteSetup
  indexers: IndexerSetup | undefined
  completing: boolean
  failed: boolean
  onComplete: () => void
  onRevisit: () => void
}) {
  const { t } = useTranslation()
  const skippedIndexers = indexers?.skipped ?? false

  return (
    <div className="grid flex-1 gap-px bg-rule lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
      <div className="min-w-0 bg-hull p-6">
        <div className="lg:sticky lg:top-6">
          <Cutaway title={t('complete.cutaway.title')}>
            <CutawayRow term={t('routes.cutaway.libraryRoot')} value={routes.library_root} />
            <CutawayRow term={t('routes.cutaway.completeRoot')} value={routes.complete_root} />
            <CutawayRow term={t('complete.cutaway.routes')} value={String(routes.routes.length)} />
            <CutawayRow
              term={t('complete.cutaway.skipped')}
              value={t(skippedIndexers ? 'complete.skipped.indexers' : 'complete.cutaway.nothing')}
              muted={!skippedIndexers}
            />
          </Cutaway>
        </div>
      </div>

      <div className="min-w-0 bg-hull p-6">
        <h2 className="text-lg font-semibold text-ink">{t('complete.title')}</h2>
        <p className="mt-2 max-w-prose text-sm text-ink-dim">{t('complete.lede')}</p>

        <ul className="mt-6 grid gap-3">
          {routes.routes.map((route) => (
            <li key={route.slug} className="min-w-0 border-2 border-rule bg-well px-4 py-3">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                {/* 狀態讀的是那條 Route 自己的健康，不是「這一頁只會在全綠時出現」的假設。 */}
                <span className={`label px-2 py-1.5 ${SIGNAL_FILL[ROUTE_SIGNAL[route.health]]}`}>
                  {t(`routes.health.${route.health}`)}
                </span>
                <span className="value text-sm font-semibold text-ink">{route.name}</span>
                <span className="value text-xs text-ink-dim">{route.category}</span>
              </div>
              <dl className="mt-2 grid gap-x-4 gap-y-1 sm:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
                <dt className="label self-center text-ink-dim">{t('routes.cutaway.target')}</dt>
                <dd className="value text-xs wrap-anywhere text-ink">{route.target_path}</dd>
                <dt className="label self-center text-ink-dim">{t('complete.savePath')}</dt>
                <dd className="value text-xs wrap-anywhere text-ink">{route.save_path}</dd>
              </dl>
            </li>
          ))}
        </ul>

        {skippedIndexers && (
          <section className="mt-6 grid gap-3">
            <h3 className="label text-ink-dim">{t('complete.skippedTitle')}</h3>
            <Notice signal="assigned" label={t('source.skip')}>
              {t('complete.where.indexers')}
            </Notice>
          </section>
        )}

        {failed && (
          <div className="mt-6">
            <Notice signal="blocked" label={t('common.failed')}>
              {t('complete.failed')}
            </Notice>
          </div>
        )}

        <div className={`mt-6 grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] ${STICKY_ACTION}`}>
          <PrimaryButton type="button" disabled={completing} onClick={onComplete}>
            {completing ? t('complete.completing') : t('complete.submit')}
          </PrimaryButton>
          <GhostButton type="button" disabled={completing} onClick={onRevisit}>
            {t('complete.back')}
          </GhostButton>
        </div>

        <p className="mt-4 max-w-prose text-xs text-ink-dim">{t('complete.signInHint')}</p>
      </div>
    </div>
  )
}
