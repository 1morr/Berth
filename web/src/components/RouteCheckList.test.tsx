import { render, screen, within } from '@testing-library/react'
import i18next from 'i18next'
import { describe, expect, it } from 'vitest'

import '../i18n'
import { CHECKS_PASSED, routeView, step } from '../test/fixtures'
import { RouteCheckList } from './RouteCheckList'

const PROBED_AT = '2026-09-08T09:00:00Z'

/** 「qBittorrent 讀得到 Berth 寫的檔案」那一列。 */
function probeRow() {
  const row = screen
    .getAllByRole('listitem')
    .find((item) => within(item).queryByText('qBittorrent 讀得到 Berth 寫的檔案'))
  if (!row) throw new Error('no download_visible row')
  return row
}

describe('RouteCheckList 的探針沿用（M4 票 50）', () => {
  it('健康迴圈沿用的那一條說「沿用上一次的結論」與那一次的時間', () => {
    render(<RouteCheckList route={routeView({ probe_carried: true, probed_at: PROBED_AT })} />)

    const row = probeRow()
    expect(within(row).getByText('已完成')).toBeInTheDocument()
    expect(within(row).getByText(/沿用上一次的結論/)).toBeInTheDocument()
    expect(row.querySelector('time')?.getAttribute('datetime')).toBe(PROBED_AT)
    expect(within(row).getByText(/到 Route 設定按「重新檢查」/)).toBeInTheDocument()
  })

  it('這一輪真的問了就不說沿用', () => {
    render(<RouteCheckList route={routeView({ probe_carried: false, probed_at: PROBED_AT })} />)

    expect(screen.queryByText(/沿用上一次的結論/)).not.toBeInTheDocument()
  })

  it('從來沒探過的是「尚未執行」，不說沿用', () => {
    const checks = CHECKS_PASSED.map((row) =>
      row.step === 'download_visible' ? step('download_visible', 'pending') : row,
    )
    render(<RouteCheckList route={routeView({ checks, probe_carried: false, probed_at: null })} />)

    expect(within(probeRow()).getByText('尚未執行')).toBeInTheDocument()
    expect(screen.queryByText(/沿用上一次的結論/)).not.toBeInTheDocument()
  })

  it('票 50 之前的結論沒有時間：照樣說沿用，時間是「沒有紀錄」', () => {
    render(<RouteCheckList route={routeView({ probe_carried: true, probed_at: null })} />)

    const row = probeRow()
    expect(within(row).getByText(/沿用上一次的結論/)).toBeInTheDocument()
    expect(within(row).getByText('沒有紀錄')).toBeInTheDocument()
  })

  it('英文介面', async () => {
    await i18next.changeLanguage('en')
    try {
      render(<RouteCheckList route={routeView({ probe_carried: true, probed_at: PROBED_AT })} />)

      expect(screen.getByText(/Carried over from the last probe/)).toBeInTheDocument()
      expect(screen.getByText(/press “Check again” in route settings/)).toBeInTheDocument()
    } finally {
      await i18next.changeLanguage('zh-Hant')
    }
  })
})
