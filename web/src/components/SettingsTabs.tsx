import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { BERTHS } from './berths'
import { NAV_LINK } from './controls'

/**
 * 設定的子分頁列：一格泊位一頁，照泊位板的順序（票 06i；票 14 起的
 * `.scratch/m1/route-settings-shape.md` 決定 1 是它的前身）。分頁名就是板上那一格的名字——
 * 精靈、健康頁、設定講的是同一組泊位，名字也該是同一個。
 *
 * 最後兩格「通知」「AI」不是泊位（M4 票 123、M5）：不上泊位號，與那五格隔一條線。
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
      {/* 通知不是泊位（沒有號、不在泊位板上）：與那五格之間隔一條線，讓人看得出那五格是一組。 */}
      <span aria-hidden="true" className="mx-1 w-0.5 self-stretch bg-rule" />
      <Link to="/settings/notifications" className={`${NAV_LINK} px-3 py-2`}>
        {t('settings.tabs.notify')}
      </Link>
      <Link to="/settings/ai" className={`${NAV_LINK} px-3 py-2`}>
        {t('settings.tabs.ai')}
      </Link>
    </nav>
  )
}
