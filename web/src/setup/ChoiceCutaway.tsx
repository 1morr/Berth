import { useTranslation } from 'react-i18next'

import { Cutaway, CutawayRow } from '../components/Cutaway'

/**
 * 還沒選來源時的剖面：兩種來源各會做什麼。頁 2、頁 4 共用（M4 票 81：頁 4 原本在這時說「你自己的
 * Prowlarr」），標題與頁 1 還沒選時同一個「將會做什麼」。
 */
export function ChoiceCutaway({ bundled, existing }: { bundled: string; existing: string }) {
  const { t } = useTranslation()

  return (
    <Cutaway title={t('owner.cutaway.title')}>
      <CutawayRow term={t('origin.bundled')} value={bundled} />
      <CutawayRow term={t('origin.existing')} value={existing} />
    </Cutaway>
  )
}
