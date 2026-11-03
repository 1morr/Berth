import { Link, useRouterState } from '@tanstack/react-router'

import { useTranslation } from 'react-i18next'

import { NAV_BOX, NAV_BOX_ACTIVE } from '../components/controls'
import { CountChip } from './CountChip'
import { countedName, inSection } from './sections'

/**
 * 管一整個區塊的導覽項：連到區塊的第一頁，在區塊的每一頁上都是當前。
 *
 * 不用 `NAV_LINK` 的 `data-status`：TanStack 只在連結自己那條路徑上掛它，在 `/issues` 上「待處理」
 * （連 `/review`）不會亮。`aria-current` 照實說：在它連的那一頁是 `page`（`Link` 自己掛），在區塊的
 * 別頁是 `true`——它不是這一頁，但這一頁屬於它。
 */
export function SectionLink({
  to,
  pages,
  label,
  count,
}: {
  to: '/review' | '/schedule'
  pages: readonly string[]
  label: string
  count: number | undefined
}) {
  const { t } = useTranslation()
  const pathname = useRouterState({ select: (state) => state.location.pathname })
  const current = inSection(pathname, pages)
  const exact = pathname === to

  return (
    <Link
      to={to}
      aria-current={current && !exact ? 'true' : undefined}
      aria-label={countedName(t, label, count)}
      className={`${current ? NAV_BOX_ACTIVE : NAV_BOX} inline-flex items-center px-4 py-2.5`}
    >
      {label}
      <CountChip count={count} />
    </Link>
  )
}
