import { useTranslation } from 'react-i18next'

import type { HealthDetail, ServiceHealth } from '../api/health'
import { type ServiceKind } from '../api/schemas'
import { BerthBoard, type BoardSlot } from '../components/BerthBoard'
import { BERTHS } from '../components/berths'
import { ROUTE_HEALTH_LABEL, ROUTE_SIGNAL } from '../components/routeChecks'
import { detailLabel } from '../components/services'
import { STATE_LABEL, STATE_SIGNAL, serviceState } from './signals'

/**
 * 健康頁的泊位板：與精靈**同一塊板**（`components/BerthBoard.tsx`）。
 *
 * 三格是服務，媒體庫路徑那一格是所有 Route 的總結——那正是精靈的同一個泊位。TMDB 那一格
 * 不是第五項檢查：它讀的是精靈第 7 步那一次憑證測試的結果（`tmdb_verified`，票 06e）。
 * 精靈問「接上了沒」，這裡問「還繫著嗎」，所以每一格的位置與意義不變。
 */
export function HealthBoard({ report }: { report: HealthDetail }) {
  const { t } = useTranslation()
  const byKind = new Map<ServiceKind, ServiceHealth>(report.services.map((row) => [row.kind, row]))

  // 格子的順序照 `BERTHS` 走，不照服務的順序：媒體庫路徑夾在兩個服務之間（票 06d）。
  const slots: BoardSlot[] = BERTHS.map((berth) => {
    if (berth.slot === 'tmdb') {
      return {
        code: berth.code,
        name: t(berth.nameKey),
        status: t(report.tmdb_verified ? 'detail.verified' : 'detail.unverified'),
        detail: null,
        signal: report.tmdb_verified ? 'secured' : 'blocked',
      }
    }
    if (berth.slot === 'library') {
      return {
        code: berth.code,
        name: t(berth.nameKey),
        status: t(ROUTE_HEALTH_LABEL[report.routes_status]),
        detail:
          report.routes.length > 0
            ? t('health.routes.count', { count: report.routes.length })
            : null,
        signal: ROUTE_SIGNAL[report.routes_status],
        filled: report.routes_status !== 'unknown',
      }
    }
    const kind = berth.slot
    const row = byKind.get(kind)
    const state = row ? serviceState(row) : 'unknown'

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

  return <BerthBoard label={t('board.title')} slots={slots} />
}
