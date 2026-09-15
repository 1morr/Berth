import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { NAV_BOX, NAV_BOX_ACTIVE } from './controls'

/** 兩個設定頁，照子分頁列上的順序。 */
const TABS = [
  { to: '/settings/services', label: 'settings.tabs.services' },
  { to: '/settings/routes', label: 'settings.tabs.routes' },
] as const

/**
 * 設定的子分頁列：服務 | 媒體庫路徑（票 14、`.scratch/m1/route-settings-shape.md` 的決定 1）。
 *
 * 頁首的「設定」仍只有一個入口，兩頁各自在標題上方掛這一條。當前頁用重橫線加 `deck` 底標出來，
 * 不靠顏色——與頁首導覽、媒體庫的切換列同一個方塊。
 */
export function SettingsTabs() {
  const { t } = useTranslation()

  return (
    <nav aria-label={t('settings.tabs.label')} className="flex flex-wrap gap-2">
      {TABS.map((tab) => (
        <Link
          key={tab.to}
          to={tab.to}
          className={`${NAV_BOX} px-3 py-2`}
          activeProps={{ className: `${NAV_BOX_ACTIVE} px-3 py-2` }}
        >
          {t(tab.label)}
        </Link>
      ))}
    </nav>
  )
}
