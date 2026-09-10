import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { JobEvent } from '../api/jobs'
import { renderWithProviders } from '../test/render'
import { JobTimeline } from './JobTimeline'

/**
 * 時間線逐型別的那幾格（brief §5.2、`.scratch/m1/live-jobs-shape.md` §6）。
 *
 * 這裡不做通用的 key/value 傾印，所以每一種型別都要自己被釘住一次——少寫一種的後果是
 * 那一行只剩色塊與時間，而使用者看不出「Berth 那時候知道了什麼」。
 */

function event(overrides: Partial<JobEvent> = {}): JobEvent {
  return {
    id: 1,
    type: 'created',
    actor: 'system',
    payload: {},
    created_at: '2026-09-10T12:00:00Z',
    ...overrides,
  }
}

function render(rows: JobEvent[]) {
  renderWithProviders(<JobTimeline events={rows} />)
  return within(screen.getByRole('list'))
}

describe('Job 時間線', () => {
  it('檔案清單那一筆說得出幾個檔案與總大小', () => {
    const line = render([
      event({ type: 'metadata_received', payload: { file_count: 13, total_size: 1_400_000_000 } }),
    ])

    expect(line.getByText('檔案清單')).toBeInTheDocument()
    expect(line.getByText(/13 個檔案/)).toBeInTheDocument()
    expect(line.getByText(/1\.3 GB/)).toBeInTheDocument()
  })

  it('進度那一筆是百分比，與列上那一格同一種寫法', () => {
    const line = render([event({ type: 'progress', payload: { progress: 0.5 } })])

    expect(line.getByText('50%')).toBeInTheDocument()
  })

  it('恢復的那一筆另外說一句——它與「又跨了 25%」長得一樣，意思卻相反', () => {
    const line = render([event({ type: 'progress', payload: { progress: 0.31, resumed: true } })])

    expect(line.getByText(/又動起來了/)).toBeInTheDocument()
  })

  it('停住那一筆帶著停了多久與 qBittorrent 自己的狀態字串', () => {
    const line = render([
      event({ type: 'stalled', payload: { idle_minutes: 12, client_state: 'stalledDL' } }),
    ])

    // `client_state` 不翻譯：使用者要拿它去 qBittorrent 的介面上對照（The Machine String Rule）。
    expect(line.getByText(/12 分鐘沒有動靜 · stalledDL/)).toBeInTheDocument()
  })

  it('完成那一筆說出總大小', () => {
    const line = render([event({ type: 'completed', payload: { total_size: 1_400_000_000 } })])

    expect(line.getByText('下載完成')).toBeInTheDocument()
    expect(line.getByText(/1\.3 GB/)).toBeInTheDocument()
  })

  it('需要處理那一筆逐種說一句話，並附上下一步', () => {
    const line = render([
      event({
        type: 'issue_detected',
        payload: { type: 'missing_files', client_state: 'missingFiles' },
      }),
    ])

    expect(line.getByText(/qBittorrent 說檔案不見了/)).toBeInTheDocument()
  })

  it('認不得的 issue 型別不畫，也不印出一條 i18n key', () => {
    const line = render([
      event({ type: 'issue_detected', payload: { type: 'something_new_in_m2' } }),
    ])

    expect(line.getByText('需要處理')).toBeInTheDocument()
    expect(line.queryByText(/jobs\.timeline\.issue/)).not.toBeInTheDocument()
  })

  it('認不得的事件型別原樣顯示——它仍然是一件真的發生過的事', () => {
    const line = render([event({ type: 'plan_generated' })])

    expect(line.getByText('plan_generated')).toBeInTheDocument()
  })
})
