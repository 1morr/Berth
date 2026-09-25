import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { BERTHS } from './berths'
import { NAV_LINK } from './controls'

/**
 * 設定的子分頁列：一格泊位一頁，照泊位板的順序（票 06i；票 14 起的
 * `.scratch/m1/route-settings-shape.md` 決定 1 是它的前身）。分頁名就是板上那一格的名字——
 * 精靈、健康頁、設定講的是同一組泊位，名字也該是同一個。
 *
 * 頁首的「設定」仍只有一個入口，每一頁各自在標題上方掛這一條。當前頁用重橫線加 `deck` 底標出來，
 * 不靠顏色——與頁首導覽、媒體庫的切換列同一個方塊。
 */
export function SettingsTabs() {
  const { t } = useTranslation()

  return (
    <nav aria-label={t('settings.tabs.label')} className="flex flex-wrap gap-2">
      {BERTHS.map((berth) => (
        <Link key={berth.settings} to={berth.settings} className={`${NAV_LINK} px-3 py-2`}>
          {t(berth.nameKey)}
        </Link>
      ))}
    </nav>
  )
}
