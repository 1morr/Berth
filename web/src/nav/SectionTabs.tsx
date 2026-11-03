import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { meQueryOptions } from '../api/auth'
import { waitingQueryOptions } from '../api/waiting'
import { NAV_LINK } from '../components/controls'
import { CountChip } from './CountChip'
import { countedName, tabCount, visibleTabs, type Section } from './sections'

const TAB = `${NAV_LINK} inline-flex items-center px-3 py-2`

/**
 * 區塊的分頁列（M5.5 票 07）：掛在每一頁 `<h1>` 上方，形狀同 `SettingsTabs`。頁首的一個導覽項
 * 管一個區塊，這一條說出區塊裡有哪幾頁、各有幾件在等你。哪幾頁、誰看得到、帶哪一格件數都在
 * `nav/sections.ts` 的區塊物件裡。
 *
 * 件數與頁首同一份查詢（`['waiting']`），兩處的數字不會對不上。`exact`：時間表 `/schedule` 與追更
 * `/schedule/tracking` 是兩格，模糊比對會讓時間表在追更頁上也亮。
 */
export function SectionTabs({ section }: { section: Section }) {
  const { t } = useTranslation()
  const admin = useQuery(meQueryOptions).data?.role === 'admin'
  const counts = useQuery({ ...waitingQueryOptions, enabled: admin }).data

  return (
    <nav aria-label={t(section.label)} className="flex flex-wrap gap-2">
      {visibleTabs(section, admin).map((tab) => {
        const label = t(tab.label)
        const count = tabCount(tab, counts)
        return (
          <Link
            key={tab.to}
            to={tab.to}
            activeOptions={{ exact: true }}
            aria-label={countedName(t, label, count)}
            className={TAB}
          >
            {label}
            <CountChip count={count} />
          </Link>
        )
      })}
    </nav>
  )
}
