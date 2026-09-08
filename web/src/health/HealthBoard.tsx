import { useTranslation } from 'react-i18next'

import type { HealthDetail, ServiceHealth } from '../api/health'
import { SERVICE_KINDS, type ServiceKind } from '../api/schemas'
import { BerthBoard, type BoardSlot } from '../components/BerthBoard'
import { BERTHS } from '../components/berths'
import { ROUTE_HEALTH_LABEL, ROUTE_SIGNAL } from '../components/routeChecks'
import { detailLabel } from '../components/services'
import { STATE_LABEL, STATE_SIGNAL, serviceState } from './signals'

/**
 * 健康頁的泊位板：與精靈**同一塊板**（`components/BerthBoard.tsx`）。
 *
 * 前三格是服務，第四格是所有 Route 的總結——那正是精靈的第四個泊位（媒體庫路徑）。
 * 精靈問「接上了沒」，這裡問「還繫著嗎」，所以四格的位置與意義不變。
 */
export function HealthBoard({ report }: { report: HealthDetail }) {
  const { t } = useTranslation()
  const byKind = new Map<ServiceKind, ServiceHealth>(report.services.map((row) => [row.kind, row]))

  const slots: BoardSlot[] = SERVICE_KINDS.map((kind, index) => {
    const row = byKind.get(kind)
    const state = row ? serviceState(row) : 'unknown'
    const berth = BERTHS[index]

    return {
      code: berth.code,
      name: t(berth.nameKey),
      status: t(STATE_LABEL[state]),
      detail: row?.detail ? (
        <>
          <span className="label">{t(detailLabel(kind))}</span> {row.detail}
        </>
      ) : null,
      signal: STATE_SIGNAL[state],
      filled: state !== 'unknown' && state !== 'unconfigured',
    }
  })

  const library = BERTHS[3]
  slots.push({
    code: library.code,
    name: t(library.nameKey),
    status: t(ROUTE_HEALTH_LABEL[report.routes_status]),
    detail:
      report.routes.length > 0 ? t('health.routes.count', { count: report.routes.length }) : null,
    signal: ROUTE_SIGNAL[report.routes_status],
    filled: report.routes_status !== 'unknown',
  })

  return <BerthBoard label={t('board.title')} slots={slots} />
}
