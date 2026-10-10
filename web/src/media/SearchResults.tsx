import { useTranslation } from 'react-i18next'

import { Dot } from '../components/Dot'
import { Timestamp } from '../components/Timestamp'
import type { Media } from '../api/media'
import type { SearchResult } from '../api/search'
import { reasonOf, type Group } from './searchFilter'
import { estimate, formatCount, formatSize, tagTokens, type SortKey } from './searchResult'
import { SubmitAction } from './SubmitAction'

/**
 * 一張裝船清單（`.scratch/m1/search-results-shape.md` §3）。
 *
 * **一份 DOM，兩種版面**：桌機是真表格，390px 上第 2–6 欄整欄不畫，那五個值改成發佈名底下
 * 的一行中點分隔（使用者 2026-09-10 拍板「窄版改成堆疊列」）。用 `hidden` 而不是兩份標記，
 * 是因為 `display: none` 的東西不進無障礙樹——螢幕閱讀器在任何寬度下都只會讀到一份。
 *
 * 表格外**不包 `overflow-x`**：窄版根本不是表格，被切掉的發佈名等於沒顯示
 * （The Values Sit On Their Line Rule）。
 *
 * **一類一個 `tbody`**（M4 票 83）：開了好幾類時照篩選按鈕的順序一組接一組，「符合」永遠在最上面，
 * 組內照排序鍵。一類送來的比總數少時，那一組底下一行說清楚只列了哪幾筆。
 */
export function SearchResults({
  groups,
  sort,
  onSort,
  media,
  route,
}: {
  groups: readonly Group[]
  sort: SortKey
  onSort: (key: SortKey) => void
  media: Media
  /** 這一輪選的 Route。送單時它從偏好變成承諾（票 04b、09）。 */
  route: number | null
}) {
  const { t } = useTranslation()

  return (
    <table className="w-full border-collapse border-2 border-rule bg-well text-left">
      <thead className="hidden sm:table-header-group">
        <tr className="border-b-2 border-rule bg-deck">
          <th scope="col" className="label px-4 py-2.5 text-ink-dim">
            {t('search.column.title')}
          </th>
          <SortableHeader label={t('search.column.size')} sort={sort} own="size" onSort={onSort} />
          <SortableHeader
            label={t('search.column.seeders')}
            sort={sort}
            own="seeders"
            onSort={onSort}
          />
          <th scope="col" className="label px-4 py-2.5 text-ink-dim">
            {t('search.column.indexer')}
          </th>
          <th scope="col" className="label px-4 py-2.5 text-ink-dim">
            {t('search.column.published')}
          </th>
          <th scope="col" className="label px-4 py-2.5 text-ink-dim">
            {t('search.column.estimate')}
          </th>
        </tr>
      </thead>
      {groups.map((group) => (
        <tbody
          key={group.verdict}
          className="divide-y divide-rule border-t-2 border-rule first-of-type:border-t-0"
        >
          {group.rows.map((row) => (
            <ResultRow key={row.key} row={row} media={media} route={route} />
          ))}
          {group.total > group.rows.length && (
            <tr>
              <td colSpan={6} className="px-4 py-2.5 text-xs text-ink-dim">
                {t('search.capped', { total: group.total, shown: group.rows.length })}
              </td>
            </tr>
          )}
        </tbody>
      ))}
    </table>
  )
}

/**
 * 可排序的欄頭。`aria-sort` 掛在 `th` 上而不是按鈕上——那是表格的屬性，
 * 而按鈕只是改變它的手段。
 */
function SortableHeader({
  label,
  sort,
  own,
  onSort,
}: {
  label: string
  sort: SortKey
  own: SortKey
  onSort: (key: SortKey) => void
}) {
  return (
    <th
      scope="col"
      className="px-0 py-0 text-right"
      aria-sort={sort === own ? 'descending' : 'none'}
    >
      <button
        type="button"
        onClick={() => onSort(own)}
        // 選中的欄頭用**線變重**標出來，不用顏色——排序不是四個信號色裡的任何一個
        // （The Role Is Not A State Rule）。
        className={`label w-full px-4 py-2.5 text-right whitespace-nowrap ${
          sort === own ? 'border-b-2 border-rule-strong text-ink' : 'text-ink-dim hover:text-ink'
        }`}
      >
        {label}
      </button>
    </th>
  )
}

function ResultRow({
  row,
  media,
  route,
}: {
  row: SearchResult
  media: Media
  route: number | null
}) {
  const { t, i18n } = useTranslation()
  const size = formatSize(row.size, i18n.language)
  const seeders = formatCount(row.seeders, i18n.language)

  return (
    <tr>
      <td className="px-4 py-3 align-top">
        {/* 發佈名整行換行，不截斷：它是這一列的證據，解析器讀的就是同一串字。 */}
        <p className="value text-sm wrap-anywhere text-ink">{row.title}</p>
        <VerdictNote row={row} media={media} />
        <TagStrip row={row} />
        {/* 窄版把另外五欄收成一行。桌機上它整行不畫，那五欄自己在右邊。 */}
        <p className="value mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-dim sm:hidden">
          <span>{size}</span>
          <Dot />
          <span>{t('search.seedersInline', { count: row.seeders ?? 0, value: seeders })}</span>
          {row.indexer && (
            <>
              <Dot />
              <IndexerLink row={row} />
            </>
          )}
          {row.published_at && (
            <>
              <Dot />
              <Published at={row.published_at} />
            </>
          )}
          <Dot />
          <Estimate row={row} />
        </p>
        {/* 送單住在發佈名那一格：它的確認要就地展開，而那一段裡印著資料夾名——
            靠右那幾格窄到放不下一句話（The Failure Expands In Place Rule）。 */}
        <div className="mt-3">
          <SubmitAction media={media} row={row} route={route} />
        </div>
      </td>
      <td className="value hidden px-4 py-3 text-right align-top text-xs whitespace-nowrap text-ink sm:table-cell">
        {size}
      </td>
      <td className="value hidden px-4 py-3 text-right align-top text-xs text-ink sm:table-cell">
        {seeders}
      </td>
      <td className="value hidden px-4 py-3 align-top text-xs whitespace-nowrap text-ink-dim sm:table-cell">
        <IndexerLink row={row} />
      </td>
      <td className="hidden px-4 py-3 align-top text-xs whitespace-nowrap text-ink-dim sm:table-cell">
        <Published at={row.published_at} />
      </td>
      <td className="hidden px-4 py-3 align-top whitespace-nowrap sm:table-cell">
        <Estimate row={row} />
      </td>
    </tr>
  )
}

/**
 * 不是「符合」的列：歸到哪一類（中性小色塊——它是分類不是狀態，The Role Is Not A State Rule）與一句理由。
 * 「符合」與自己打關鍵字的列不標（The Usual Stays Unpainted Rule，使用者確認 shape）。
 */
function VerdictNote({ row, media }: { row: SearchResult; media: Media }) {
  const { t } = useTranslation()
  const reason = reasonOf(row, media)
  if (!reason) return null

  return (
    <p className="mt-2 flex flex-wrap items-baseline gap-x-2 gap-y-1">
      <span className="label bg-deck px-1.5 py-0.5 text-ink">{t(reason.labelKey)}</span>
      <span className="text-xs text-ink-dim">
        {t(reason.key, { evidence: reason.evidence, year: reason.year })}
      </span>
    </p>
  )
}

/**
 * 解析出的 Tags。中性色塊——它們是分類不是狀態（The Role Is Not A State Rule）。
 * 內容與之後真的會進檔名的那一串字是同一份資料（brief §6.8）。
 */
function TagStrip({ row }: { row: SearchResult }) {
  const tokens = tagTokens(row.tags)
  if (tokens.length === 0) return null

  return (
    <p className="mt-2 flex flex-wrap gap-1">
      {tokens.map((token) => (
        // token 是 brief §6.8 的詞彙表，不是文案：`WEB`、`1080p`、`CHS+CHT` 在兩個語言
        // 都是同一串字，走 `.value` 而不是 `.label`（`.label` 會把 `1080p` 大寫掉）。
        <span key={token} className="value bg-deck px-1.5 py-0.5 text-xs text-ink">
          {token}
        </span>
      ))}
    </p>
  )
}

/**
 * 預估季集。`S03` + 「全季」、`S03E13`、或一句「判斷不出來」。
 *
 * 代號走 `.value`（機器字串，與季集清單同一個語域），只有那個詞是翻譯的。
 */
function Estimate({ row }: { row: SearchResult }) {
  const { t } = useTranslation()
  const { code, noteKey } = estimate(row)

  return (
    <span className="inline-flex items-center gap-1.5">
      {code && <span className="value text-xs text-ink">{code}</span>}
      {noteKey &&
        (noteKey === 'search.estimate.unknown' ? (
          // 判斷不出來是一句話，不是一個分類——不給它色塊，免得看起來像個結論。
          <span className="text-xs text-ink-dim">{t(noteKey)}</span>
        ) : (
          <span className="label bg-deck px-1.5 py-1 text-ink">{t(noteKey)}</span>
        ))}
    </span>
  )
}

/**
 * 索引站報的發佈時間（Sonarr / Radarr 手動搜尋的 Age 欄）：相對說法，完整日期在 `title`。
 * 那個站沒報是 `—`，與大小同一種說法——不是「從未」，只是這一格沒有值。
 */
function Published({ at }: { at: string | null }) {
  if (!at) return <span className="value">—</span>
  return <Timestamp at={at} />
}

/** 來源站。有集頁就連過去——使用者常常要自己去看一眼檔案清單。 */
function IndexerLink({ row }: { row: SearchResult }) {
  if (!row.info_url) return <span>{row.indexer}</span>

  return (
    <a
      href={row.info_url}
      target="_blank"
      rel="noreferrer"
      className="underline decoration-rule-strong underline-offset-4 hover:decoration-ink"
    >
      {row.indexer}
    </a>
  )
}
