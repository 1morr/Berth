import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import type { ImportedWork } from '../api/weekly'
import { SectionHeading } from '../components/SectionHeading'
import { displayRound } from '../i18n/displayRound'
import { countEpisodes, describeSpans } from './spans'

/** 入庫：一部作品一列，照作品名排序；作品名連到作品頁（作品已刪的不連）。 */
export function ImportedSection({ works }: { works: ImportedWork[] }) {
  const { t, i18n } = useTranslation()
  const rows = works
    .map((work) => ({
      work,
      title: displayRound(i18n.language, { 'zh-Hant': work.title, en: work.title_en }),
    }))
    .sort((left, right) => left.title.localeCompare(right.title, i18n.language))
  const episodes = works.reduce((sum, work) => sum + countEpisodes(work.episodes), 0)

  return (
    <section aria-labelledby="weekly-imported" className="grid gap-3">
      <SectionHeading
        id="weekly-imported"
        label={t('weekly.imported.title')}
        extra={
          works.length > 0 && (
            <p className="value text-xs text-ink-dim">
              {t('weekly.imported.works', { count: works.length })}
              {episodes > 0 && ` · ${t('weekly.imported.episodes', { count: episodes })}`}
            </p>
          )
        }
      />
      {rows.length === 0 ? (
        <p className="max-w-prose text-sm text-ink-dim">{t('weekly.imported.empty')}</p>
      ) : (
        <ul className="grid gap-2">
          {rows.map(({ work, title }) => (
            <li
              key={work.media ?? `${work.title}-${work.title_en}`}
              className="flex min-w-0 flex-wrap items-baseline gap-x-3 gap-y-1 border-b border-rule pb-2"
            >
              {work.media === null ? (
                <span className="value wrap-anywhere min-w-0 text-sm text-ink">{title}</span>
              ) : (
                <Link
                  to="/media/$mediaId"
                  params={{ mediaId: work.media }}
                  className="value wrap-anywhere min-w-0 text-sm text-ink underline decoration-rule-strong underline-offset-4 hover:decoration-ink"
                >
                  {title}
                </Link>
              )}
              {work.kind === 'movie' ? (
                <span className="label bg-deck px-2 py-1.5 text-ink">
                  {t('weekly.imported.movie')}
                </span>
              ) : (
                <span className="value wrap-anywhere min-w-0 basis-full text-xs text-ink-dim sm:basis-auto">
                  {describeSpans(work.episodes)}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
