import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { meQueryOptions } from '../api/auth'
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
  to: '/review' | '/issues' | '/rss' | '/schedule'
  label: string
  count?: number | undefined
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

/**
 * 新番：時間表 `/schedule`（每個人，M5.5 票 09）、訂閱 `/rss`（只有 admin，帶待綁定的件數）；追更是票 12。
 * 一般使用者只有一個分頁也照畫：區塊的形狀與管理員看到的一樣，少的那一格是他進不去的頁。
 */
export function AiringTabs() {
  const { t } = useTranslation()
  const admin = useQuery(meQueryOptions).data?.role === 'admin'
  const counts = useQuery({ ...waitingQueryOptions, enabled: admin }).data

  return (
    <Tabs label={t('nav.airing')}>
      <Tab to="/schedule" label={t('nav.schedule')} />
      {admin && <Tab to="/rss" label={t('nav.subscriptions')} count={counts?.rss} />}
    </Tabs>
  )
}
