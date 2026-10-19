import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useId } from 'react'
import { useTranslation } from 'react-i18next'

import { RSS_KEY, saveExclusions, type Exclusions } from '../api/rss'
import { Checkbox } from '../components/controls'
import { RequestFailed } from '../components/RequestFailed'
import { GLOBAL_EXCLUSIONS_ANCHOR, RulesEditor } from './RulesEditor'
import { SectionHeading } from '../components/SectionHeading'

/**
 * 全域的排除條件（M3 票 10，brief §15「全部接受，只排除」）：合集的內建判斷與全域的標題規則。Feed 與
 * RSS Series 那兩層在各自那一列上（`RulesToggle`）；三層取聯集，這一段的 lede 說清楚。
 *
 * 合集那一項不是規則：它看解析器的 `release_kind`，只在全域這一層（brief §15）。所以它自成一組、
 * 與下面的標題規則分開，標明是內建判斷（M4 票 113）。
 *
 * 中性、不塗漆（Usual Stays Unpainted）：排除條件是設定，不是要你現在做的事。
 */
export function ExclusionsSection({ exclusions }: { exclusions: Exclusions }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const headingId = useId()
  const builtinId = useId()
  const builtinHintId = useId()
  const rulesId = useId()
  const toggle = useMutation({
    mutationFn: (notSingle: boolean) => saveExclusions(notSingle, exclusions.rules),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: RSS_KEY }),
  })

  return (
    <section
      id={GLOBAL_EXCLUSIONS_ANCHOR}
      aria-labelledby={headingId}
      className="grid scroll-mt-6 gap-3"
    >
      <SectionHeading id={headingId} label={t('rss.rules.globalTitle')} />
      <div className="grid gap-4 border-2 border-rule bg-well px-4 py-3">
        <p className="max-w-prose text-sm text-ink-dim">{t('rss.rules.lede')}</p>
        <div
          role="group"
          aria-labelledby={builtinId}
          aria-describedby={builtinHintId}
          className="grid gap-2"
        >
          <p className="flex flex-wrap items-baseline gap-x-2">
            <span id={builtinId} className="label text-ink-dim">
              {t('rss.rules.builtin')}
            </span>
            <span id={builtinHintId} className="text-xs text-ink-dim">
              {t('rss.rules.builtinHint')}
            </span>
          </p>
          <Checkbox
            label={t('rss.rules.notSingle')}
            hint={t('rss.rules.notSingleHint')}
            checked={toggle.isPending ? toggle.variables : exclusions.not_single}
            onChange={(checked) => {
              if (!toggle.isPending) toggle.mutate(checked)
            }}
          />
          {toggle.isError && <RequestFailed error={toggle.error} lead={t('request.notDone')} />}
        </div>
        <div
          role="group"
          aria-labelledby={rulesId}
          className="grid gap-2 border-t-2 border-rule pt-4"
        >
          <p id={rulesId} className="label text-ink-dim">
            {t('rss.rules.titleRules')}
          </p>
          <RulesEditor
            rules={exclusions.rules}
            save={(rules) => saveExclusions(exclusions.not_single, rules)}
          />
        </div>
      </div>
    </section>
  )
}
