import { render, screen, within } from '@testing-library/react'
import i18next from 'i18next'
import { describe, expect, it } from 'vitest'

import '../i18n'
import { CHECKS_PASSED, routeView, step } from '../test/fixtures'
import type { SetupStep } from '../api/schemas'
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

describe('Berth 自己寫不進的補法（M4 票 72）', () => {
  /** 第一項就撞上 Berth 寫不進，其餘沒跑。 */
  const CANNOT_WRITE: SetupStep[] = CHECKS_PASSED.map((row) =>
    row.step === 'category'
      ? {
          ...step('category', 'failed', '', "[Errno 13] Permission denied: '/data/torrent'"),
          failure: 'berth_cannot_write',
          params: { path: '/data/torrent' },
        }
      : step(row.step, 'pending'),
  )

  // rootless 上把資料夾 chown 給那組 PUID / PGID 要 sudo，做了宿主上的帳號又寫不進去（票 42 實跑）。
  it.each([
    ['zh-Hant', /rootless Docker 不要 chown，改填 PUID=0、PGID=0/],
    ['en', /on rootless Docker, skip the chown and set PUID=0 and PGID=0/],
  ])('%s：補法多說 rootless Docker 填 PUID=0、PGID=0', async (language, said) => {
    await i18next.changeLanguage(language)
    try {
      render(<RouteCheckList route={routeView({ checks: CANNOT_WRITE, health: 'failed' })} />)

      expect(screen.getByText(said)).toHaveTextContent('/data/torrent')
    } finally {
      await i18next.changeLanguage('zh-Hant')
    }
  })
})
