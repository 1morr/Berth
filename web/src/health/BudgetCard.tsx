import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { budgetQueryOptions, type SiteBudget } from '../api/health'
import { Dot } from '../components/Dot'
import { Timestamp } from '../components/Timestamp'

/**
 * 健康頁的「請求預算」區塊（M3 票 20、plan §3.2）。
 *
 * RSS 輪詢、每日補漏與索引站搜尋打的是同一批公開站，所以一個站一份預算。這一塊回答兩件事：
 * 這一小時誰用了多少，以及**用完時哪一種工作被延後了**——那些工作不是壞了，是 Berth 自己先停手，
 * 別的地方看不出來它們在等（票 20 驗收第三條）。
 *
 * 延後不塗紅：紅色只代表阻擋（The One Meaning Rule），等得到的事是線變重，與下載迴圈落後一輪同一個說法。
 * 讀不到（舊後端、請求失敗）時整塊不畫：它不是四項檢查之一，少了它不妨礙讀這一頁的其他部分。
 */
export function BudgetCard() {
  const { t } = useTranslation()
  const budget = useQuery(budgetQueryOptions)
  if (!budget.data) return null
  const { limit, sites } = budget.data
  const waiting = sites.some((site) => site.deferred.length > 0)

  return (
    <section
      className={`border-2 bg-well ${waiting ? 'border-rule-strong' : 'border-rule'}`}
      aria-labelledby="health-budget"
    >
      <h3 id="health-budget" className="label border-b-2 border-rule bg-deck px-4 py-2.5 text-ink">
        {t('health.budget.title')}
      </h3>
      <p className="max-w-prose px-4 pt-3 text-xs text-ink-dim">
        {t('health.budget.help', { limit })}
      </p>
      {sites.length === 0 ? (
        <p className="px-4 pt-2 pb-4 text-sm text-ink-dim">{t('health.budget.idle')}</p>
      ) : (
        <ul className="grid gap-3 px-4 pt-3 pb-4">
          {sites.map((site) => (
            <SiteRow key={site.site} site={site} limit={limit} />
          ))}
        </ul>
      )}
    </section>
  )
}

function SiteRow({ site, limit }: { site: SiteBudget; limit: number }) {
  const { t } = useTranslation()

  return (
    <li className="grid min-w-0 gap-1 border-l-2 border-rule pl-3">
      <p className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        {/* 主機名是機器字串：原樣、`.value`。 */}
        <span className="value text-sm wrap-anywhere text-ink">{site.site}</span>
        <Dot />
        <span className="value text-xs text-ink">{`${site.used} / ${limit}`}</span>
      </p>
      {site.by_use.length > 0 && (
        <p className="text-xs text-ink-dim">
          {site.by_use
            .map(({ use, count }) =>
              t('health.budget.useCount', { use: t(`health.budget.use.${use}`), value: count }),
            )
            .join(' · ')}
        </p>
      )}
      {site.deferred.map((deferral) => (
        <p key={deferral.use} className="text-xs text-ink">
          <span>
            {t('health.budget.deferred', {
              use: t(`health.budget.use.${deferral.use}`),
              value: deferral.refused,
            })}
          </span>{' '}
          {deferral.until ? (
            <>
              <span className="text-ink-dim">{t('health.budget.until')}</span>{' '}
              <Timestamp at={deferral.until} />
            </>
          ) : (
            <span className="text-ink-dim">{t('health.budget.never')}</span>
          )}
        </p>
      ))}
    </li>
  )
}
