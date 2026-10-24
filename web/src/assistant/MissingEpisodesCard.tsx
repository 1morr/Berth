import { useId } from 'react'
import { useTranslation } from 'react-i18next'

import type { MissingEpisodes } from '../api/assistant'
import { displayRound } from '../i18n/displayRound'
import { describeSpans } from '../weekly/spans'
import { CardFrame, WorkLink } from './cardParts'

/**
 * 「作品缺哪幾集」的結果卡（M5 票 12）：已經播出、還沒有任何下載在處理的集，與作品頁季表的「缺」同一份
 * 判定。集照週報的寫法併成段（`describeSpans`）。
 */
export function MissingEpisodesCard({ result }: { result: MissingEpisodes }) {
  const { t, i18n } = useTranslation()
  const id = useId()
  const title = displayRound(i18n.language, { 'zh-Hant': result.title, en: result.title_en })

  return (
    <CardFrame
      labelId={id}
      heading={t('assistant.cards.missing.title')}
      count={t('assistant.cards.missing.count', { count: result.count })}
    >
      <div className="grid gap-1 px-3 py-2.5">
        <h4 className="value text-sm wrap-anywhere text-ink">
          <WorkLink media={result.media}>{title}</WorkLink>
        </h4>
        <p className="value text-xs wrap-anywhere text-ink-dim">
          {result.count === 0 ? t('assistant.cards.missing.none') : describeSpans(result.episodes)}
        </p>
      </div>
    </CardFrame>
  )
}
