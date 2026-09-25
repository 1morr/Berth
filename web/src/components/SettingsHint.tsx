import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { meQueryOptions } from '../api/auth'
import { berthOf, type BerthSlot } from './berths'
import { GHOST_LINK } from './controls'

/**
 * 「去設定頁把這件事補上」——只給 admin 的那條連結（票 06i 起指設定頁，不再指精靈）。
 *
 * 設定頁只有 admin 進得去（後端同時回 403），所以對一般使用者那是一條死路，
 * 而他要的是「去叫管理員」（票 10 code-review 的結論）。這條規則在票 04 一度被抄了
 * 第二份（探索頁的憑證訊息與詳情頁的「沒有 Route」），所以收成一個元件——
 * 各處講的是同一條規則，各寫一份遲早會有一邊忘記擋。
 *
 * 連結文字由泊位導出（「前往設定：索引站」）：說出會落在哪一頁，各處不必各寫一句。
 */
export function SettingsHint({
  slot,
  fallback,
}: {
  /** 要去哪一格的設定頁（`components/berths.ts`）。 */
  slot: BerthSlot
  /** 一般使用者看到的那句話。 */
  fallback: string
}) {
  const { t } = useTranslation()
  const me = useQuery(meQueryOptions)

  if (me.data?.role !== 'admin') return <p className="text-sm text-ink-dim">{fallback}</p>

  const berth = berthOf(slot)
  return (
    <Link to={berth.settings} className={GHOST_LINK}>
      {t('settings.go', { place: t(berth.nameKey) })}
    </Link>
  )
}
