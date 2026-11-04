import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useId } from 'react'
import { useTranslation } from 'react-i18next'

import { keepingUpQueryOptions, type KeepingUpSection, type TrackedWork } from '../api/keepingUp'
import { myNotifyQueryOptions } from '../api/notify'
import { CollapsibleRow } from '../components/CollapsibleRow'
import { INLINE_LINK, Notice, PAGE_TITLE } from '../components/controls'
import { QueueLoading } from '../components/QueueLoading'
import { RequestFailed } from '../components/RequestFailed'
import { SectionHeading } from '../components/SectionHeading'
import { AIRING } from '../nav/sections'
import { SectionTabs } from '../nav/SectionTabs'
import { TrackedRows } from '../tracking/TrackedRows'
import { unnotified } from '../tracking/unnotified'

/**
 * 追更 `/schedule/tracking`（M5.5 票 12，`.scratch/m5.5/tracking-shape.md`）：訂閱的作品一部一列，看得出
 * 哪幾部晚了、晚幾天、卡在哪。只有管理員（後端 `ADMIN_PREFIXES` 同時 403）。
 *
 * 三段照後端排好的順序（`KeepingUpSection`）：要你動手、準時、斷更很久；斷更很久預設收起（它們已經不提醒了）。
 * 沒接 Discord 的管理員只能從這一頁知道有遲到，頁首說一句（ADR-0015：不另做其他通知管道）。
 */
export function KeepingUpPage() {
  const { t } = useTranslation()
  const tracking = useQuery(keepingUpQueryOptions)
  const works = tracking.data?.works ?? []
  const of = (section: KeepingUpSection) => works.filter((work) => work.section === section)

  return (
    <div className="mx-auto grid w-full max-w-[80rem] gap-6 px-6 py-8">
      <SectionTabs section={AIRING} />
      <h1 tabIndex={-1} className={`${PAGE_TITLE} border-b-2 border-rule-strong pb-2`}>
        {t('tracking.title')}
      </h1>
      <Unnotified />

      {tracking.isPending ? (
        <>
          <p className="text-sm text-ink-dim">{t('tracking.loading')}</p>
          <QueueLoading />
        </>
      ) : tracking.isError ? (
        <RequestFailed error={tracking.error} lead={t('tracking.readFailed')} />
      ) : works.length === 0 ? (
        <p className="border-2 border-rule bg-well px-4 py-3 text-sm text-ink">
          {t('tracking.none')}{' '}
          <Link to="/schedule" className={INLINE_LINK}>
            {t('tracking.toSchedule')}
          </Link>
        </p>
      ) : (
        <>
          {of('action').length === 0 && (
            <p className="text-sm text-ink-dim">{t('tracking.allOnTime')}</p>
          )}
          <Part section="action" works={of('action')} />
          <Part section="on_time" works={of('on_time')} />
          <Dormant works={of('dormant')} />
        </>
      )}
    </div>
  )
}

/** 要你動手、準時：標題列加一張表。沒有作品的那一段整段不畫。 */
function Part({ section, works }: { section: KeepingUpSection; works: TrackedWork[] }) {
  const { t } = useTranslation()
  const id = useId()
  if (works.length === 0) return null
  const label = t(`tracking.section.${section}`)
  return (
    <section aria-labelledby={id} className="grid gap-3">
      <SectionHeading
        id={id}
        label={label}
        count={{ value: works.length, spoken: t('tracking.count', { count: works.length }) }}
      />
      <TrackedRows works={works} caption={label} />
    </section>
  )
}

/** 斷更很久：收在原生 `<details>` 裡（`CollapsibleRow`），預設收起，摘要列寫部數。 */
function Dormant({ works }: { works: TrackedWork[] }) {
  const { t } = useTranslation()
  if (works.length === 0) return null
  const label = t('tracking.section.dormant')
  return (
    <section aria-label={label}>
      <CollapsibleRow
        name={label}
        summary={
          <span className="flex items-baseline gap-3">
            <span className="label text-ink">{label}</span>
            <span className="value text-xs text-ink-dim">
              {t('tracking.count', { count: works.length })}
            </span>
          </span>
        }
      >
        {() => (
          <div className="grid gap-3 p-4">
            <TrackedRows works={works} caption={label} />
          </div>
        )}
      </CollapsibleRow>
    </section>
  )
}

/** 收不到通知時頁首那一句（中性：它不擋任何事）。讀不到「我的通知」時不畫，不猜。 */
function Unnotified() {
  const { t } = useTranslation()
  const mine = useQuery(myNotifyQueryOptions).data
  if (!mine || !unnotified(mine)) return null
  return (
    <Notice signal="neutral" label={t('tracking.notifiedLabel')}>
      {t('tracking.notified')}{' '}
      <Link to="/settings/notifications" className={INLINE_LINK}>
        {t('tracking.toNotifications')}
      </Link>
    </Notice>
  )
}
