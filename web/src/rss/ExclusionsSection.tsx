import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useId } from 'react'
import { useTranslation } from 'react-i18next'

import { RSS_KEY, saveExclusions, type Exclusions } from '../api/rss'
import { Checkbox, Notice } from '../components/controls'
import { RulesEditor } from './RulesEditor'
import { SectionHeading } from './SectionHeading'

/**
 * 全域的排除條件（M3 票 10，brief §15「全部接受，只排除」）：合集預設與全域規則。Feed 與 RSS Series
 * 那兩層在各自那一列上（`RulesToggle`）；三層取聯集，這一段的 lede 說清楚。
 *
 * 中性、不塗漆（Usual Stays Unpainted）：排除條件是設定，不是要你現在做的事。
 */
export function ExclusionsSection({ exclusions }: { exclusions: Exclusions }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const headingId = useId()
  const toggle = useMutation({
    mutationFn: (notSingle: boolean) => saveExclusions(notSingle, exclusions.rules),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: RSS_KEY }),
  })

  return (
    <section aria-labelledby={headingId} className="grid gap-3">
      <SectionHeading id={headingId} label={t('rss.rules.title')} />
      <div className="grid gap-4 border-2 border-rule bg-well px-4 py-3">
        <p className="max-w-prose text-sm text-ink-dim">{t('rss.rules.lede')}</p>
        <Checkbox
          label={t('rss.rules.notSingle')}
          hint={t('rss.rules.notSingleHint')}
          checked={toggle.isPending ? toggle.variables : exclusions.not_single}
          onChange={(checked) => {
            if (!toggle.isPending) toggle.mutate(checked)
          }}
        />
        {toggle.isError && (
          <Notice signal="blocked" label={t('common.failed')}>
            {t('rss.failed')}
          </Notice>
        )}
        <RulesEditor
          rules={exclusions.rules}
          save={(rules) => saveExclusions(exclusions.not_single, rules)}
        />
      </div>
    </section>
  )
}
