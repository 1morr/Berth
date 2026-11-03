import { useQuery } from '@tanstack/react-query'
import { Link, useRouterState } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { waitingQueryOptions } from '../api/waiting'
import { NAV_BOX, NAV_BOX_ACTIVE } from '../components/controls'
import { CountChip } from './CountChip'
import { countedName, inSection, sectionCount, sectionPages, type Section } from './sections'

/**
 * 管一整個區塊的導覽項：連到區塊的第一頁，在區塊的每一頁上都是當前。件數是各分頁件數的和，
 * 只有 admin（`GET /waiting` 對其他人 403）。
 *
 * 不用 `NAV_LINK` 的 `data-status`：TanStack 只在連結自己那條路徑上掛它，在 `/issues` 上「待處理」
 * （連 `/review`）不會亮。`aria-current` 照實說：在它連的那一頁是 `page`，在區塊的別頁是 `true`——它不是
 * 這一頁，但這一頁屬於它。`exact`：`/schedule/tracking` 在 `/schedule` 底下，模糊比對會讓 TanStack
 * 在那一頁也掛上 `page`。
 */
export function SectionLink({ section, admin }: { section: Section; admin: boolean }) {
  const { t } = useTranslation()
  const pathname = useRouterState({ select: (state) => state.location.pathname })
  const counts = useQuery({ ...waitingQueryOptions, enabled: admin }).data
  const to = section.tabs[0].to
  const current = inSection(pathname, sectionPages(section))
  const exact = pathname === to
  const label = t(section.label)
  const count = admin ? sectionCount(section, counts) : undefined

  return (
    <Link
      to={to}
      activeOptions={{ exact: true }}
      aria-current={current && !exact ? 'true' : undefined}
      aria-label={countedName(t, label, count)}
      className={`${current ? NAV_BOX_ACTIVE : NAV_BOX} inline-flex items-center px-4 py-2.5`}
    >
      {label}
      <CountChip count={count} />
    </Link>
  )
}
