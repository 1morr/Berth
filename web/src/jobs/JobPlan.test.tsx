import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { Plan, PlanItem } from '../api/plans'
import { renderWithProviders } from '../test/render'
import { JobPlan } from './JobPlan'

function item(overrides: Partial<PlanItem> = {}): PlanItem {
  return {
    id: 1,
    rel_path: '[Group] SPY×FAMILY S01E01 [1080p][CHT].mkv',
    action: 'import',
    media_id: 'tv:120089',
    season: 1,
    episode_start: 1,
    episode_end: 1,
    target_path:
      'SPY x FAMILY (2022) [tmdbid-120089]/Season 01/SPY x FAMILY (2022) - S01E01 - Episode 1 [WEB][1080p][CHT][Group].mkv',
    confidence: 'high',
    reasons: ['the filename says S01E01'],
    audit: false,
    error: '',
    ...overrides,
  }
}

function plan(overrides: Partial<Plan> = {}): Plan {
  return {
    id: 7,
    job_hash: 'a'.repeat(40),
    status: 'auto',
    engine: 'rules',
    engine_version: '0.1.0',
    created_at: '2026-09-11T12:00:00Z',
    summary: { files: 1, high: 1, medium: 0, low: 0, actions: { import: 1 }, review_reason: null },
    items: [item()],
    ...overrides,
  }
}

/** 逐檔那一份清單。理由自己也是一份 `ul`，所以取的是外層那一個。 */
function render(row: Plan) {
  renderWithProviders(<JobPlan plan={row} />)
  return within(screen.getAllByRole('list')[0])
}

describe('匯入計劃', () => {
  it('一個檔案一列：決定、信心、季集、目標路徑與理由（票 11 驗收）', () => {
    const list = render(plan())

    expect(list.getByText('入庫')).toBeInTheDocument()
    expect(list.getByText('高信心')).toBeInTheDocument()
    expect(list.getByText('S01E01')).toBeInTheDocument()
    expect(list.getByText(/Season 01/)).toBeInTheDocument()
    expect(list.getByText('the filename says S01E01')).toBeInTheDocument()
  })

  it('略過的檔案也有一列——「沒有動它」與「沒看到它」是兩件事', () => {
    const list = render(
      plan({
        items: [
          item({
            id: 2,
            rel_path: 'readme.txt',
            action: 'skip',
            target_path: '',
            season: null,
            episode_start: null,
          }),
        ],
        summary: {
          files: 0,
          high: 1,
          medium: 0,
          low: 0,
          actions: { skip: 1 },
          review_reason: null,
        },
      }),
    )

    expect(list.getByText('略過')).toBeInTheDocument()
    expect(list.getByText('readme.txt')).toBeInTheDocument()
  })

  it('單檔多集寫成 Jellyfin 認得的那一種（brief §6.6）', () => {
    const list = render(plan({ items: [item({ episode_end: 2 })] }))

    expect(list.getByText('S01E01-E02')).toBeInTheDocument()
  })

  it('medium 自動入庫的那一列說得出它還等一次確認', () => {
    const list = render(plan({ items: [item({ confidence: 'medium', audit: true })] }))

    expect(list.getByText('中信心')).toBeInTheDocument()
    expect(list.getByText('已入庫待確認')).toBeInTheDocument()
  })

  it('停下來時說得出理由與下一步（PRODUCT 原則 4）', () => {
    renderWithProviders(
      <JobPlan
        plan={plan({
          status: 'pending_review',
          summary: {
            files: 0,
            high: 0,
            medium: 0,
            low: 1,
            actions: { review: 1 },
            review_reason: 'medium_not_allowed',
          },
          items: [item({ action: 'review', confidence: 'medium' })],
        })}
      />,
    )

    // 計劃自己與那一列都說「待審核」：一個說整份停下來了，一個說是哪個檔案讓它停的。
    expect(screen.getAllByText('待審核')).toHaveLength(2)
    expect(screen.getByText(/關掉了「medium 信心自動入庫」/)).toBeInTheDocument()
  })

  it('下載中的那一份說得出它只是預估', () => {
    renderWithProviders(<JobPlan plan={plan({ status: 'preplan' })} />)

    expect(screen.getByText('預估')).toBeInTheDocument()
    expect(screen.getByText(/沒有讀過檔案本身/)).toBeInTheDocument()
  })

  it('自動入庫的那一份沒有理由那一句——常態不需要旁白', () => {
    renderWithProviders(<JobPlan plan={plan()} />)

    expect(screen.getByText('自動入庫')).toBeInTheDocument()
    expect(screen.getByText(/1 個檔案要入庫/)).toBeInTheDocument()
    expect(screen.queryByText(/M1 還沒有審核佇列/)).not.toBeInTheDocument()
  })
})
