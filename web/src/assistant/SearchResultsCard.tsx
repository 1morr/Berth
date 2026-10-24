import { useId, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import type { SearchResultRow, SearchResults } from '../api/assistant'
import { mediaQueryOptions, type Media } from '../api/media'
import { Dot } from '../components/Dot'
import { seasonCode } from '../components/episodes'
import { displayRound } from '../i18n/displayRound'
import { IndexerNotice } from '../media/IndexerNotice'
import { RoutePicker } from '../media/RoutePicker'
import { reasonOf } from '../media/searchFilter'
import { estimate, formatCount, formatSize, tagTokens } from '../media/searchResult'
import { SubmitAction } from '../media/SubmitAction'
import { describeSpans } from '../weekly/spans'
import { CardFrame, WorkLink } from './cardParts'
import { reasonText } from './refusals'

/**
 * 「依作品與集搜尋」的結果卡（M5 票 12）：搜尋頁結果表的那幾格，一筆一列。
 *
 * - **「為什麼不像這部作品」沿用搜尋頁的那一句**（`reasonOf`，brief §20.20）：不是「符合」的列一個中性色塊加一句理由。
 * - **AI 送不出的列說為什麼**（後端 `submit_guard` 算好的 `refusal`）：符合但集數對不上、被全域標題規則擋下的那幾筆。
 *   這是給人看的防線：標題寫得再像指令，模型也只能在送得出的那幾列裡挑。
 * - **人也可以自己按送單**：同一顆 `SubmitAction`（確認裡印著資料夾名），Route 的下拉在列表上面，初值是後端的預選。
 *   作品還沒讀回來時不畫送單鍵——那一段確認要資料夾名。
 */
export function SearchResultsCard({ result }: { result: SearchResults }) {
  const { t, i18n } = useTranslation()
  const id = useId()
  const media = useQuery(mediaQueryOptions(result.media))
  const [route, setRoute] = useState<number | null | undefined>(undefined)
  const chosen =
    route === undefined ? (result.route ?? media.data?.preselected_route_id ?? null) : route
  const title = displayRound(i18n.language, { 'zh-Hant': result.title, en: result.title_en })
  const fits = result.counts.fits ?? 0
  const shownFits = result.rows.filter((row) => row.verdict === 'fits').length

  return (
    <CardFrame
      labelId={id}
      heading={t('assistant.cards.search.title')}
      count={t('assistant.cards.search.fits', { count: fits })}
    >
      <div className="grid gap-1 px-3 py-2.5">
        <h4 className="value text-sm wrap-anywhere text-ink">
          <WorkLink media={result.media}>{title}</WorkLink>
        </h4>
        <p className="value text-xs wrap-anywhere text-ink-dim">
          {result.wanted.length > 0
            ? t('assistant.cards.search.wanted', { episodes: describeSpans(result.wanted) })
            : t('assistant.cards.search.whole')}
          {result.next_seasons.length > 0 && (
            <>
              {' '}
              <Dot />{' '}
              {t('assistant.cards.search.later', {
                seasons: result.next_seasons.map(seasonCode).join(', '),
              })}
            </>
          )}
        </p>
      </div>
      {result.problem !== null ? (
        <div className="border-t-2 border-rule px-3 py-2.5">
          <IndexerNotice problem={result.problem} detail={result.detail} />
        </div>
      ) : result.rows.length === 0 ? (
        <p className="border-t-2 border-rule px-3 py-2.5 text-sm text-ink-dim">
          {t('assistant.cards.search.empty')}
        </p>
      ) : (
        <>
          {media.data && (
            <div className="border-t-2 border-rule px-3 py-2.5">
              <RoutePicker media={media.data} value={chosen} onChange={setRoute} />
            </div>
          )}
          <ul>
            {result.rows.map((row) => (
              <Row key={row.source_id} row={row} media={media.data} route={chosen} work={result} />
            ))}
          </ul>
          {fits > shownFits && (
            <p className="border-t-2 border-rule px-3 py-2.5 text-xs text-ink-dim">
              {t('assistant.cards.search.capped', { total: fits, shown: shownFits })}{' '}
              <WorkLink media={result.media}>{t('assistant.cards.search.toPage')}</WorkLink>
            </p>
          )}
        </>
      )}
    </CardFrame>
  )
}

const NO_TAGS = {
  source: null,
  resolution: '',
  subs: [],
  hardsub: false,
  group: '',
  version: '',
  edition: '',
}

function Row({
  row,
  media,
  route,
  work,
}: {
  row: SearchResultRow
  media: Media | undefined
  route: number | null
  /** 搜的那一部：理由那一句要它的類型與年份。 */
  work: Pick<SearchResults, 'kind' | 'year'>
}) {
  const { t, i18n } = useTranslation()
  const reason = reasonOf(row, work, '')
  const guess = estimate(row)
  // OpenAPI 裡的 `Tags` 是輸入的形狀（每格可省），後端送出來的每一格都在；補上空值就是同一份。
  const tokens = tagTokens({ ...NO_TAGS, ...row.tags })

  return (
    <li className="grid gap-2 border-t-2 border-rule px-3 py-2.5">
      {/* 發佈名整行換行、不截斷：它是證據，也是陌生人寫的字——照原樣印，不當成指令。 */}
      <p className="value text-sm wrap-anywhere text-ink">{row.title}</p>
      {reason && (
        <p className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
          <span className="label bg-deck px-1.5 py-0.5 text-ink">{t(reason.labelKey)}</span>
          <span className="text-xs text-ink-dim">
            {t(reason.key, { evidence: reason.evidence, year: reason.year })}
          </span>
        </p>
      )}
      {!reason && row.refusal !== null && (
        <p className="text-xs text-ink-dim">
          {t('assistant.cards.search.aiWont', {
            reason: reasonText(t, row.refusal, row.refusal_detail),
          })}
        </p>
      )}
      {tokens.length > 0 && (
        <p className="flex flex-wrap gap-1">
          {tokens.map((token) => (
            <span key={token} className="value bg-deck px-1.5 py-0.5 text-xs text-ink">
              {token}
            </span>
          ))}
        </p>
      )}
      <p className="value flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-dim">
        <span>{formatSize(row.size, i18n.language)}</span>
        <Dot />
        <span>
          {t('search.seedersInline', {
            count: row.seeders ?? 0,
            value: formatCount(row.seeders, i18n.language),
          })}
        </span>
        {row.indexer && (
          <>
            <Dot />
            <span>{row.indexer}</span>
          </>
        )}
        <Dot />
        <span>
          {guess.code}
          {guess.code && guess.noteKey && ' '}
          {guess.noteKey && t(guess.noteKey)}
        </span>
      </p>
      {media && <SubmitAction media={media} row={row} route={route} />}
    </li>
  )
}
