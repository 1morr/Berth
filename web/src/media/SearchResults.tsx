import { useTranslation } from 'react-i18next'

import { Dot } from '../components/Dot'
import type { Media } from '../api/media'
import type { SearchResult } from '../api/search'
import { estimate, formatCount, formatSize, tagTokens, type SortKey } from './searchResult'
import { SubmitAction } from './SubmitAction'

/**
 * 一張裝船清單（`.scratch/m1/search-results-shape.md` §3）。
 *
 * **一份 DOM，兩種版面**：桌機是真表格，390px 上第 2–5 欄整欄不畫，那四個值改成發佈名底下
 * 的一行中點分隔（使用者 2026-09-10 拍板「窄版改成堆疊列」）。用 `hidden` 而不是兩份標記，
 * 是因為 `display: none` 的東西不進無障礙樹——螢幕閱讀器在任何寬度下都只會讀到一份。
 *
 * 表格外**不包 `overflow-x`**：窄版根本不是表格，被切掉的發佈名等於沒顯示
 * （The Values Sit On Their Line Rule）。
 */
export function SearchResults({
  rows,
  sort,
  onSort,
  media,
  route,
}: {
  rows: readonly SearchResult[]
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
            {t('search.column.estimate')}
          </th>
        </tr>
      </thead>
      <tbody className="divide-y divide-rule">
        {rows.map((row) => (
          <ResultRow key={row.key} row={row} media={media} route={route} />
        ))}
      </tbody>
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
        <TagStrip row={row} />
        {/* 窄版把另外四欄收成一行。桌機上它整行不畫，那四欄自己在右邊。 */}
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
      <td className="hidden px-4 py-3 align-top whitespace-nowrap sm:table-cell">
        <Estimate row={row} />
      </td>
    </tr>
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
