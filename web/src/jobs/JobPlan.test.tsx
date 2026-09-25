import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import type { Plan, PlanItem } from '../api/plans'
import { renderWithProviders } from '../test/render'
import { JobPlan } from './JobPlan'

function item(overrides: Partial<PlanItem> = {}): PlanItem {
  return {
    id: 1,
    rel_path: '[Group] SPY×FAMILY S01E01 [1080p][CHT].mkv',
    kind: 'video',
    action: 'import',
    media_id: 'tv:120089',
    season: 1,
    episode_start: 1,
    episode_end: 1,
    target_path:
      'SPY x FAMILY (2022) [tmdbid-120089]/Season 01/SPY x FAMILY (2022) - S01E01 - Episode 1 [WEB][1080p][CHT][Group].mkv',
    confidence: 'high',
    reasons: [{ code: 'season_from_release', params: { season: 1 } }],
    audit: false,
    applied: false,
    actions: [],
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
    media_kind: 'tv',
    summary: { files: 1, high: 1, medium: 0, low: 0, actions: { import: 1 }, review_reason: null },
    items: [item()],
    series: null,
    ...overrides,
  }
}

/** 展開每一組之後的逐檔清單（M1.5 票 09：逐檔要展開那一組才畫）。理由自己也是一份 `ul`，所以取的是外層那一個。 */
async function render(row: Plan) {
  renderWithProviders(<JobPlan plan={row} />)
  for (const summary of screen.getAllByText('展開')) await userEvent.click(summary)
  return within(screen.getAllByRole('list')[0])
}

/** 一組的摘要列（`<summary>`），照畫面上的順序。 */
function groups() {
  return screen.getAllByText(/^\d+ 個檔案$/).map((count) => count.closest('summary')!)
}

/** 葬送的芙莉蓮 `[7³ACG]` BD 合集的形狀：S00 11 個中信心待確認、S01 28 個高信心（票 15 critique 量到的那一包）。 */
function frieren(): Plan {
  const specials = Array.from({ length: 11 }, (_, index) =>
    item({
      id: index + 1,
      rel_path: `Sousou no Frieren 2023 S00E${String(index + 1).padStart(2, '0')}.mkv`,
      season: 0,
      episode_start: index + 1,
      episode_end: index + 1,
      confidence: 'medium',
      audit: true,
    }),
  )
  const episodes = Array.from({ length: 28 }, (_, index) =>
    item({
      id: index + 12,
      rel_path: `Sousou no Frieren 2023 S01E${String(index + 1).padStart(2, '0')}.mkv`,
      episode_start: index + 1,
      episode_end: index + 1,
    }),
  )
  return plan({
    summary: {
      files: 39,
      high: 28,
      medium: 11,
      low: 0,
      actions: { import: 39 },
      review_reason: null,
    },
    items: [...specials, ...episodes],
  })
}

describe('匯入計劃', () => {
  /**
   * 票 03 第 10 條。抬頭那一行原本印的是原始列舉值（`信心 high 28 / medium 11 / low 0`），
   * 底下每一組卻說「高信心」「中信心」——同一塊展開區兩套詞（M1.5 critique 的一致性那一條）。
   */
  it('抬頭與各組講同一套信心的詞，抬頭不印原始列舉值', () => {
    renderWithProviders(<JobPlan plan={frieren()} />)

    const heading = screen.getByText(/信心/, { selector: 'p > span' })
    expect(heading).toHaveTextContent('高')
    expect(heading).toHaveTextContent('中')
    expect(heading).not.toHaveTextContent(/high|medium|low/)

    // 組的摘要用的是同一組字，不是另一套。
    const [audited, plain] = groups()
    expect(within(audited).getByText('中信心')).toBeVisible()
    expect(within(plain).getByText('高信心')).toBeVisible()
  })

  it('依「處置 × 季 × 信心 × 待確認」分組：芙莉蓮 39 個檔案收成兩行（M1.5 票 09）', () => {
    renderWithProviders(<JobPlan plan={frieren()} />)

    const [audited, plain] = groups()
    expect(groups()).toHaveLength(2)
    expect(within(audited).getByText('入庫')).toBeVisible()
    expect(within(audited).getByText('中信心')).toBeVisible()
    expect(within(audited).getByText('已入庫待確認')).toBeVisible()
    expect(within(audited).getByText('S00 E01–E11')).toBeVisible()
    expect(within(audited).getByText('11 個檔案')).toBeVisible()
    expect(within(plain).getByText('高信心')).toBeVisible()
    expect(within(plain).getByText('S01 E01–E28')).toBeVisible()
    expect(within(plain).getByText('28 個檔案')).toBeVisible()
    expect(within(plain).queryByText('已入庫待確認')).not.toBeInTheDocument()
    // 逐檔要展開那一組才畫。
    expect(screen.queryByText('Sousou no Frieren 2023 S01E05.mkv')).not.toBeInTheDocument()
  })

  it('展開一組才逐檔列出，底端收得起來', async () => {
    renderWithProviders(<JobPlan plan={frieren()} />)

    await userEvent.click(within(groups()[1]).getByText('28 個檔案'))
    expect(screen.getByText('Sousou no Frieren 2023 S01E05.mkv')).toBeVisible()
    expect(screen.queryByText('Sousou no Frieren 2023 S00E05.mkv')).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: '收起 入庫 S01 E01–E28' }))
    expect(screen.queryByText('Sousou no Frieren 2023 S01E05.mkv')).not.toBeInTheDocument()
  })

  it('需要人的那一組排在最前面，即使它在 torrent 裡排在後面（The Needs-You Floats Up Rule）', () => {
    renderWithProviders(
      <JobPlan
        plan={plan({
          items: [
            item(),
            item({ id: 2, rel_path: 'NCOP.mkv', action: 'review', confidence: 'low' }),
          ],
        })}
      />,
    )

    const [first, second] = groups()
    expect(within(first).getByText('待審核')).toBeVisible()
    expect(within(second).getByText('入庫')).toBeVisible()
  })

  it('一個檔案一列：季集、來源檔名，目標路徑與理由收在它自己的展開區（M1.5 票 09b）', async () => {
    const list = await render(plan())

    expect(list.getByText('S01E01')).toBeVisible()
    expect(list.getByText('[Group] SPY×FAMILY S01E01 [1080p][CHT].mkv')).toBeVisible()
    // 處置與信心是**組鍵的一部分**，一組裡必然相同——組的摘要說過了，逐檔列不再重複。
    expect(list.queryByText('入庫')).not.toBeInTheDocument()
    expect(list.queryByText('高信心')).not.toBeInTheDocument()
    // 長的那兩段收起來，展開才有。
    expect(list.getByText(/Season 01/)).not.toBeVisible()
    expect(list.getByText('發佈名寫了第 1 季')).not.toBeVisible()

    await userEvent.click(list.getByText('[Group] SPY×FAMILY S01E01 [1080p][CHT].mkv'))

    expect(list.getByText(/Season 01/)).toBeVisible()
    // 理由是 code + 參數，句子由前端翻（M2 票 07）。
    expect(list.getByText('發佈名寫了第 1 季')).toBeVisible()
  })

  it('略過的檔案也有一列——「沒有動它」與「沒看到它」是兩件事', async () => {
    const skipped = plan({
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
    })
    const list = await render(skipped)

    // 處置在組的摘要上，檔名在它自己那一列——沒有季集時檔名就是認出這一筆的唯一憑據。
    expect(within(groups()[0]).getByText('略過')).toBeVisible()
    expect(list.getByText('readme.txt')).toBeVisible()
  })

  it('單檔多集寫成 Jellyfin 認得的那一種（brief §6.6）', async () => {
    const list = await render(plan({ items: [item({ episode_end: 2 })] }))

    expect(list.getByText('S01E01-E02')).toBeInTheDocument()
  })

  it('medium 自動入庫的那一組說得出它還等一次確認', async () => {
    await render(plan({ items: [item({ confidence: 'medium', audit: true })] }))

    // 信心與待確認也在組鍵裡（M1.5 票 09b：逐檔列不再重複組說過的）。
    const summary = groups()[0]
    expect(within(summary).getByText('中信心')).toBeVisible()
    expect(within(summary).getByText('已入庫待確認')).toBeVisible()
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

    // 計劃自己與那一組都說「待審核」：一個說整份停下來了，一個說是哪幾個檔案讓它停的。
    expect(screen.getAllByText('待審核')).toHaveLength(2)
    expect(screen.getByText(/不讓中信心的檔案自己入庫/)).toBeInTheDocument()
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

// 同一個 RSS Series 前後兩份計劃可能用了不同的值（M3 票 13）：這一份說它當時用了什麼。
describe('RSS Series 的季號與偏移', () => {
  it('說出這一份照的是哪一季、偏移多少', () => {
    renderWithProviders(
      <JobPlan plan={plan({ series: { id: 3, season: 1, episode_offset: 12 } })} />,
    )

    expect(screen.getByText('照 RSS Series：第 1 季、集號偏移 +12')).toBeInTheDocument()
  })

  it('Series 兩格都沒設時說由解析器判斷', () => {
    renderWithProviders(
      <JobPlan plan={plan({ series: { id: 3, season: null, episode_offset: null } })} />,
    )

    expect(screen.getByText('RSS Series 沒有設季號與集號偏移，由解析器判斷')).toBeInTheDocument()
  })

  it('只設了季號時說集號不偏移，負的偏移帶著減號', () => {
    const { unmount } = renderWithProviders(
      <JobPlan plan={plan({ series: { id: 3, season: 2, episode_offset: null } })} />,
    )
    expect(screen.getByText('照 RSS Series：第 2 季，集號不偏移')).toBeInTheDocument()
    unmount()

    renderWithProviders(
      <JobPlan plan={plan({ series: { id: 3, season: 2, episode_offset: -12 } })} />,
    )
    expect(screen.getByText('照 RSS Series：第 2 季、集號偏移 -12')).toBeInTheDocument()
  })

  it('不是 RSS 送的那一份沒有這一行', () => {
    renderWithProviders(<JobPlan plan={plan()} />)

    expect(screen.queryByText(/RSS Series/)).not.toBeInTheDocument()
  })
})
