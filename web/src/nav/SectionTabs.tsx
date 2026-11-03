import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { waitingQueryOptions } from '../api/waiting'
import { NAV_LINK } from '../components/controls'
import { CountChip } from './CountChip'
import { countedName } from './sections'

/**
 * 區塊的分頁列（M5.5 票 07）：掛在每一頁 `<h1>` 上方，形狀同 `SettingsTabs`。頁首的一個導覽項
 * 管一個區塊，這一條說出區塊裡有哪幾頁、各有幾件在等你。
 *
 * 件數與頁首同一份查詢（`['waiting']`），兩處的數字不會對不上。
 */
function Tabs({ label, children }: { label: string; children: ReactNode }) {
  return (
    <nav aria-label={label} className="flex flex-wrap gap-2">
      {children}
    </nav>
  )
}

const TAB = `${NAV_LINK} inline-flex items-center px-3 py-2`

function Tab({
  to,
  label,
  count,
}: {
  to: '/review' | '/issues' | '/rss'
  label: string
  count: number | undefined
}) {
  const { t } = useTranslation()
  return (
    <Link to={to} aria-label={countedName(t, label, count)} className={TAB}>
      {label}
      <CountChip count={count} />
    </Link>
  )
}

/** 待處理：審核 `/review`、Issue `/issues`，仍是兩頁（ADR-0006）。 */
export function WaitingTabs() {
  const { t } = useTranslation()
  const counts = useQuery(waitingQueryOptions).data

  return (
    <Tabs label={t('nav.waiting')}>
      <Tab to="/review" label={t('nav.review')} count={counts?.review} />
      <Tab to="/issues" label={t('nav.issues')} count={counts?.issue} />
    </Tabs>
  )
}

/** 新番：這一票只有訂閱（原 RSS 頁）；時間表與追更是 M5.5 票 09、12。 */
export function AiringTabs() {
  const { t } = useTranslation()
  const counts = useQuery(waitingQueryOptions).data

  return (
    <Tabs label={t('nav.airing')}>
      <Tab to="/rss" label={t('nav.subscriptions')} count={counts?.rss} />
    </Tabs>
  )
}
