import type { ReasoningUIPart } from 'ai'
import { useTranslation } from 'react-i18next'

import { ExpandHint } from '../components/ExpandHint'

/**
 * 模型的推理文字（M5.5 票 16，brief §20.26：`deepseek-flash` 不送 `thinking` 也會回）。
 *
 * 收成一行、預設收起，串流途中也不自動展開：推理是模型的草稿，回答才是給你看的。React 不管 `open`，
 * 所以讀者自己展開之後，後面串進來的字照樣接在展開的那一格裡。照原文印（不走 markdown）；
 * 沒有字的（服務遮掉的推理）不畫。
 */
export function Reasoning({ part }: { part: ReasoningUIPart }) {
  const { t } = useTranslation()
  if (part.text === '') return null
  return (
    <details data-reasoning className="group min-w-0 border-2 border-rule bg-well">
      <summary className="flex cursor-pointer flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2 [&::-webkit-details-marker]:hidden">
        <span className="label text-ink-dim">{t('agent.reasoning.label')}</span>
        <span className="min-w-0 flex-1 text-sm text-ink">{t('agent.reasoning.title')}</span>
        {part.state === 'streaming' ? (
          <span className="label bg-working px-1.5 py-0.5 text-on-signal">
            {t('agent.reasoning.thinking')}
          </span>
        ) : null}
        <ExpandHint />
      </summary>
      <p className="border-t-2 border-rule bg-hull px-3 py-2 text-sm whitespace-pre-wrap break-words text-ink-dim">
        {part.text}
      </p>
    </details>
  )
}
