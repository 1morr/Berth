import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'

import { meQueryOptions } from '../api/auth'
import { GHOST_LINK } from './controls'

/**
 * 「去精靈把這件事補上」——只給 admin 的那條連結。
 *
 * 精靈跑完之後只有 admin 進得去（後端同時回 403），所以對一般使用者那是一條死路，
 * 而他要的是「去叫管理員」（票 10 code-review 的結論）。這條規則在票 04 一度被抄了
 * 第二份（探索頁的憑證訊息與詳情頁的「沒有 Route」），所以收成一個元件——
 * 兩處講的是同一條規則，各寫一份遲早會有一邊忘記擋。
 */
export function SetupHint({
  berth,
  label,
  fallback,
}: {
  /** 要跳到哪一個泊位（1–4）。 */
  berth: number
  /** admin 看到的連結文字。 */
  label: string
  /** 一般使用者看到的那句話。 */
  fallback: string
}) {
  const me = useQuery(meQueryOptions)

  if (me.data?.role !== 'admin') return <p className="text-sm text-ink-dim">{fallback}</p>

  return (
    <Link to="/setup" search={{ berth }} className={GHOST_LINK}>
      {label}
    </Link>
  )
}
