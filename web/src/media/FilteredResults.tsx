import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { Media } from '../api/media'
import type { SearchResults as SearchOutcome } from '../api/search'
import { ToggleChips } from '../components/ToggleChips'
import { toggled } from '../components/toggled'
import {
  DEFAULT_OPEN,
  VERDICTS,
  groups,
  isJudged,
  sitesOf,
  tallies,
  type Verdict,
} from './searchFilter'
import { SearchResults } from './SearchResults'
import type { SortKey } from './searchResult'

/**
 * 搜尋結果：筆數那一行、篩選按鈕、站別、結果表（M4 票 83，`.scratch/m4/search-filter-shape.md`）。
 *
 * 照 Sonarr 互動搜尋的慣例：Berth 判斷不像這部作品的照樣送來，每一筆標上理由，使用者自己決定抓不抓。
 * 與 Sonarr 不同的是**預設只開「符合」**：The Pirate Bay 對查不到的字會回熱門清單，全開等於回到票 08
 * 之前。按鈕可以多選，數字是那一類的總數，「只看某個站」時跟著變。取代了原本「收起來」的展開區。
 *
 * 篩選的狀態住在這裡、不往上提：每一次搜尋各掛一個（`key` 是那一次送出的時刻），新的一輪回到只開「符合」
 * ——上一輪開著的類，套到下一輪的結果上沒有意義。
 */
export function FilteredResults({
  results,
  media,
  route,
  sort,
  onSort,
}: {
  results: SearchOutcome
  media: Media
  route: number | null
  sort: SortKey
  onSort: (key: SortKey) => void
}) {
  const { t } = useTranslation()
  const siteId = useId()
  const sortId = useId()
  const [open, setOpen] = useState<ReadonlySet<Verdict>>(DEFAULT_OPEN)
  const [site, setSite] = useState<string | null>(null)

  const judged = isJudged(results)
  const sites = sitesOf(results)
  const totals = tallies(results, site)
  const everywhere = tallies(results, null)
  const shown = groups(results, open, site, sort)
  const others = VERDICTS.filter((verdict) => verdict !== 'fits').reduce(
    (sum, verdict) => sum + everywhere[verdict],
    0,
  )

  return (
    <div className="grid gap-3">
      {/* 索引站回的每一筆去了哪裡（M4 票 69）：各類的數字在按鈕上，加上重複的就是回了幾筆。 */}
      {results.returned > 0 && (
        <p className="max-w-prose text-xs text-ink-dim">
          {t('search.returned', { count: results.returned })}
          {results.merged > 0 ? t('search.merged', { count: results.merged }) : ''}
        </p>
      )}

      {(judged || sites.length > 1) && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
          {judged && (
            // 是 0 的類不畫（按鈕永遠按得下去，票 02b）；「符合」例外，永遠在第一格。
            <ToggleChips
              label={t('search.filter.label')}
              chips={VERDICTS.filter(
                (verdict) => verdict === 'fits' || everywhere[verdict] > 0,
              ).map((verdict) => ({
                value: verdict,
                label: t(`search.verdict.${verdict}`),
                count: totals[verdict],
              }))}
              selected={open}
              onToggle={(verdict) => setOpen((before) => toggled(before, verdict))}
            />
          )}
          {sites.length > 1 && (
            <p className="flex items-center gap-3 max-sm:w-full">
              <label htmlFor={siteId} className="label text-ink-dim">
                {t('search.filter.site')}
              </label>
              <select
                id={siteId}
                value={site ?? ''}
                onChange={(event) => setSite(event.target.value || null)}
                className="value min-w-0 border-2 border-rule-strong bg-hull px-3 py-2 text-sm text-ink focus:border-ink max-sm:flex-1"
              >
                <option value="">{t('search.filter.allSites')}</option>
                {sites.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            </p>
          )}
        </div>
      )}

      {shown.length > 0 ? (
        <>
          {/* 窄版沒有欄頭，所以排序在這裡。兩個控制項改的是同一個值。 */}
          <p className="flex items-center gap-3 sm:hidden">
            <label htmlFor={sortId} className="label text-ink-dim">
              {t('search.sort.label')}
            </label>
            <select
              id={sortId}
              value={sort}
              onChange={(event) => onSort(event.target.value as SortKey)}
              className="value min-w-0 flex-1 border-2 border-rule-strong bg-hull px-3 py-2 text-sm text-ink focus:border-ink"
            >
              <option value="seeders">{t('search.column.seeders')}</option>
              <option value="size">{t('search.column.size')}</option>
            </select>
          </p>
          <SearchResults groups={shown} sort={sort} onSort={onSort} media={media} route={route} />
        </>
      ) : (
        <p className="max-w-prose text-sm text-ink-dim">{empty()}</p>
      )}
    </div>
  )

  /** 表格是空的時候說的那一句：說的是為什麼空，不是同一句「沒有東西」。 */
  function empty(): string {
    if (results.returned === 0) return t('search.empty')
    if (open.size === 0) return t('search.filter.noneOpen')
    if (site !== null) return t('search.filter.noneHere')
    // 所有站加起來還是空的：開著的只會是「符合」（其他類是 0 時沒有按鈕可開），東西都在別的類裡。
    return t('search.onlyOthers', { count: others })
  }
}
