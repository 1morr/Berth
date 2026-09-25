import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import type { ServiceKind } from '../api/schemas'
import { servicesQueryOptions } from '../api/settings'
import { GhostButton, Notice } from '../components/controls'
import { ServiceCard } from '../health/ServiceCard'
import { SettingsSection } from './SettingsFrame'
import type { ServiceCheck } from './useServiceCheck'

/**
 * 設定頁頂端的「健康」：只有這一頁那個服務的那一張卡（票 06i）。形狀與健康頁那一張完全相同——
 * 同一件事不該有兩種說法——只是紅燈時不再給「前往設定」：人已經在這一頁上了。
 */
export function HealthSection({ kind, check }: { kind: ServiceKind; check: ServiceCheck }) {
  const { t } = useTranslation()
  const services = useQuery(servicesQueryOptions)
  const row = services.data?.services.find((service) => service.kind === kind)
  const checking = check.isPending && check.variables === kind

  return (
    // 區塊的 `<h2>` 讓卡片自己的 `<h3>` 不跳級（DESIGN.md：標題層級跟著所在的頁面）。
    <SettingsSection id={`health-${kind}`} title={t('settings.health')}>
      {services.isPending ? (
        <p className="text-sm text-ink-dim">{t('health.checking')}</p>
      ) : !row ? (
        <Notice signal="blocked" label={t('common.failed')}>
          {t('health.unreachable')}
        </Notice>
      ) : (
        <div className="grid gap-3">
          <ServiceCard
            row={row}
            settingsLink={false}
            actions={
              <GhostButton type="button" busy={checking} onClick={() => check.mutate(kind)}>
                {checking ? t('settings.checking') : t('settings.check')}
              </GhostButton>
            }
          />
          {check.isError && (
            <Notice signal="blocked" label={t('common.failed')}>
              {t('settings.checkFailed')}
            </Notice>
          )}
        </div>
      )}
    </SettingsSection>
  )
}
