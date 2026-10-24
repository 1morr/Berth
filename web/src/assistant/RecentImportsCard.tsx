import { useId } from 'react'
import { useTranslation } from 'react-i18next'

import type { RecentImports, RecentWork } from '../api/assistant'
import { ArtSlot } from '../components/ArtSlot'
import { Dot } from '../components/Dot'
import { KIND_CODE } from '../components/kind'
import { displayRound } from '../i18n/displayRound'
import { countEpisodes, describeSpans } from '../weekly/spans'
import { CardFrame, WorkLink } from './cardParts'

const DAY_MS = 24 * 60 * 60 * 1000

/**
 * 「最近入庫」的結果卡（M5 票 09，DESIGN.md〈助理側面板〉的結果卡）：最近 N 天入庫的作品，一部一列——
 * 海報、類型代號與年份、作品名（連到作品頁）、入庫的集、Jellyfin 收錄了沒。
 *
 * 一列是橫放的牆卡片：同一份 `ArtSlot` 與標識帶的寫法，面板只有 26rem 寬，所以海報縮在左邊。
 * 收錄狀態不塗漆（The Usual Stays Unpainted Rule），找不到的那一句是 `ink` 字，同媒體庫牆。
 */
export function RecentImportsCard({ result }: { result: RecentImports }) {
  const { t, i18n } = useTranslation()
  const id = useId()
  const days = Math.round((Date.parse(result.until) - Date.parse(result.since)) / DAY_MS)
  const episodes = result.works.reduce((sum, work) => sum + countEpisodes(work.episodes), 0)

  return (
    <CardFrame
      labelId={id}
      heading={t('assistant.cards.recentImports.title', { count: days })}
      count={
        result.works.length > 0 ? (
          <>
            {t('weekly.imported.works', { count: result.works.length })}
            {episodes > 0 && (
              <>
                {' '}
                <Dot /> {t('weekly.imported.episodes', { count: episodes })}
              </>
            )}
          </>
        ) : undefined
      }
    >
      {result.works.length === 0 ? (
        <p className="px-3 py-2.5 text-sm text-ink-dim">
          {t('assistant.cards.recentImports.empty')}
        </p>
      ) : (
        <ul>
          {result.works.map((work) => (
            <WorkRow
              key={work.media ?? `${work.title}-${work.title_en}`}
              work={work}
              language={i18n.language}
            />
          ))}
        </ul>
      )}
    </CardFrame>
  )
}

function WorkRow({ work, language }: { work: RecentWork; language: string }) {
  const { t } = useTranslation()
  const title = displayRound(language, { 'zh-Hant': work.title, en: work.title_en })
  const poster = displayRound(language, { 'zh-Hant': work.poster_url, en: work.poster_url_en })

  return (
    <li className="flex gap-3 border-t-2 border-rule px-3 py-2.5 first:border-t-0">
      <ArtSlot url={poster} shape="poster" sizes="3.5rem" className="w-14 shrink-0" />
      <div className="grid min-w-0 content-start gap-1">
        {work.kind && (
          <p className="value text-xs text-ink-dim">
            {KIND_CODE[work.kind]} <Dot /> {work.year ?? '—'}
          </p>
        )}
        <h4 className="value text-sm wrap-anywhere text-ink">
          {work.media === null ? title : <WorkLink media={work.media}>{title}</WorkLink>}
        </h4>
        <p className="value text-xs wrap-anywhere text-ink-dim">
          {work.kind === 'movie' ? t('weekly.imported.movie') : describeSpans(work.episodes)}
        </p>
        <Presence presence={work.presence} />
      </div>
    </li>
  )
}

function Presence({ presence }: { presence: RecentWork['presence'] }) {
  const { t } = useTranslation()
  switch (presence) {
    case 'found':
      return (
        <p className="text-xs text-ink-dim">{t('assistant.cards.recentImports.presence.found')}</p>
      )
    case 'searching':
      return (
        <p className="text-xs text-ink-dim">
          {t('assistant.cards.recentImports.presence.searching')}
        </p>
      )
    case 'lost':
      return <p className="text-xs text-ink">{t('assistant.cards.recentImports.presence.lost')}</p>
    case 'none':
      return null
  }
}
