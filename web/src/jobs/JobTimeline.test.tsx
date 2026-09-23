import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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

  it('只有擋住這一筆的 issue 是紅字——torrent 從客戶端消失不是阻擋（The One Meaning Rule）', () => {
    const line = render([
      event({ id: 1, type: 'issue_detected', payload: { type: 'missing_files' } }),
      event({ id: 2, type: 'issue_detected', payload: { type: 'client_removed' } }),
    ])

    expect(line.getByText(/qBittorrent 說檔案不見了/)).toHaveClass('text-blocked-ink')
    expect(line.getByText(/torrent 從 qBittorrent 上消失了/)).not.toHaveClass('text-blocked-ink')
  })

  it('認不得的 issue 型別不畫，也不印出一條 i18n key', () => {
    const line = render([
      event({ type: 'issue_detected', payload: { type: 'something_new_in_m2' } }),
    ])

    expect(line.getByText('需要處理')).toBeInTheDocument()
    expect(line.queryByText(/jobs\.timeline\.issue/)).not.toBeInTheDocument()
  })

  it('計劃那一筆說得出幾個檔案要入庫、逐信心幾個', () => {
    const line = render([
      event({ type: 'plan_generated', payload: { engine: 'rules', files: 5, high: 5 } }),
    ])

    expect(line.getByText('計劃')).toBeInTheDocument()
    expect(line.getByText(/5 個檔案要入庫/)).toBeInTheDocument()
    // 與展開區的抬頭同一把鍵、同一套詞（票 03 第 10 條：不再印原始列舉值）。
    expect(line.getByText(/信心 高 5/)).toBeInTheDocument()
  })

  it('停下來那一筆說得出當時為什麼停', () => {
    const line = render([
      event({ type: 'review_required', payload: { reason: 'low_confidence', files: 0, low: 1 } }),
    ])

    expect(line.getByText('待審核')).toBeInTheDocument()
    expect(line.getByText(/有檔案的季集推不出來/)).toBeInTheDocument()
  })

  it('認不得的停下來理由不畫，也不印出一條 i18n key', () => {
    const line = render([event({ type: 'review_required', payload: { reason: 'from_m2' } })])

    expect(line.queryByText(/jobs\.timeline\.review/)).not.toBeInTheDocument()
  })

  it('認不得的事件型別原樣顯示——它仍然是一件真的發生過的事', () => {
    // 後端跑在前面、前端還沒有那一句時的樣子（brief §5.2 的事件是開放的）。
    const line = render([event({ type: 'from_the_future' })])

    expect(line.getByText('from_the_future')).toBeInTheDocument()
  })

  it('核准與拒絕各說誰決定了什麼（M2 票 07）', () => {
    const line = render([
      event({ id: 1, type: 'review_decided', payload: { decision: 'approved', files: 2 } }),
      event({ id: 2, type: 'review_decided', payload: { decision: 'rejected' } }),
    ])

    expect(line.getByText('管理員核准了，2 個檔案要入庫')).toBeInTheDocument()
    expect(line.getByText('管理員拒絕了這份計劃，Berth 重新規劃')).toBeInTheDocument()
  })

  it('刪除那一筆說得出真的刪了哪幾樣、空出多少', () => {
    const line = render([
      event({
        type: 'deleted',
        payload: { links: 5, sources: 6, torrent: true, purged: false, freed: 1_500_000_000 },
      }),
    ])

    expect(line.getByText('已刪除')).toBeInTheDocument()
    expect(line.getByText(/移除 5 個鏈接/)).toBeInTheDocument()
    expect(line.getByText(/刪掉 6 個下載檔案/)).toBeInTheDocument()
    expect(line.getByText(/從 qBittorrent 移除/)).toBeInTheDocument()
    expect(line.getByText(/空出 1\.4 GB/)).toBeInTheDocument()
  })

  it('只移除鏈接時說的是「沒有空出空間」而不是「已釋放 0 B」', () => {
    // 硬鏈接的另一半還在時一個位元組都沒回到磁碟（brief §9.2）。
    const line = render([
      event({
        type: 'deleted',
        payload: { links: 5, sources: 0, torrent: false, purged: false, freed: 0 },
      }),
    ])

    expect(line.getByText(/沒有空出空間/)).toBeInTheDocument()
  })

  it('鏈接那一筆說得出檔案進了媒體庫的哪裡', () => {
    const target = '/data/library/anime/SPY x FAMILY (2022) [tmdbid-120089]/Season 01/E01.mkv'
    const line = render([event({ type: 'linked', payload: { file: 'E01.mkv', target } })])

    expect(line.getByText('已鏈接')).toBeInTheDocument()
    expect(line.getByText(target)).toBeInTheDocument()
  })

  it('連續的鏈接合成一行，逐檔的目標收在底下（票 15：一季 39 檔展開後有七千多 px）', async () => {
    const targets = ['E01.mkv', 'E02.mkv', 'E03.mkv'].map((name) => `/data/library/anime/${name}`)
    renderWithProviders(
      <JobTimeline
        events={[
          ...targets.map((target, index) =>
            event({ id: index + 1, type: 'linked', payload: { target } }),
          ),
          event({ id: 9, type: 'jellyfin_scan_requested', payload: { count: 3 } }),
        ]}
      />,
    )

    const list = screen.getAllByRole('list')[0]
    const lines = within(list)
      .getAllByRole('listitem')
      .filter((item) => item.parentElement === list)
    expect(lines).toHaveLength(2)
    expect(within(lines[0]).getByText('已鏈接')).toBeInTheDocument()
    expect(within(lines[0]).getByText('3 個檔案')).toBeInTheDocument()

    await userEvent.click(within(lines[0]).getByText('列出目標路徑'))
    for (const target of targets) expect(within(lines[0]).getByText(target)).toBeVisible()
  })

  it('鏈接失敗那一筆帶著原文——它是「哪個掛載少了」的證據', () => {
    const error = 'Invalid cross-device link: the source is on the mount at /downloads'
    const line = render([
      event({ type: 'link_failed', payload: { target: '/data/library/x.mkv', errno: 18, error } }),
    ])

    expect(line.getByText('鏈接失敗')).toBeInTheDocument()
    expect(line.getByText(error)).toBeInTheDocument()
  })

  it('擋住入庫的鏈接失敗才是紅字——一條字幕沒鏈上不是阻擋', () => {
    const line = render([
      event({
        id: 1,
        type: 'link_failed',
        payload: { target: 'E01.mkv', blocking: true, error: 'Invalid cross-device link' },
      }),
      event({
        id: 2,
        type: 'link_failed',
        payload: { target: 'E01.ass', blocking: false, error: 'Permission denied' },
      }),
    ])

    expect(line.getByText('Invalid cross-device link')).toHaveClass('text-blocked-ink')
    expect(line.getByText('Permission denied')).toHaveClass('text-ink-dim')
  })

  it('通知與反查那兩筆說得出幾個檔案', () => {
    const line = render([
      event({ id: 1, type: 'jellyfin_scan_requested', payload: { count: 5, paths: [] } }),
      event({ id: 2, type: 'jellyfin_item_resolved', payload: { count: 3 } }),
    ])

    expect(line.getByText('通知了 5 個檔案的路徑')).toBeInTheDocument()
    expect(line.getByText('3 個檔案在 Jellyfin 裡找到了')).toBeInTheDocument()
  })

  it('Jellyfin 的請求沒成時說下一步會怎樣，並接上原文', () => {
    const line = render([
      event({
        type: 'jellyfin_request_failed',
        payload: { request: 'scan', error: 'POST /Library/Media/Updated: 404' },
      }),
    ])

    expect(line.getByText(/通知沒送到/)).toBeInTheDocument()
    expect(line.getByText(/404/)).toBeInTheDocument()
  })

  it('入庫的重試與送單的重試說的是不同的站', () => {
    const line = render([event({ type: 'retried', payload: { state: 'importing' } })])

    expect(line.getByText(/退回「入庫中」/)).toBeInTheDocument()
    expect(line.queryByText(/退回「已建立」/)).not.toBeInTheDocument()
  })

  it('待處理上按的那幾顆各說各的站，不是一律「退回已建立」（M2 票 09c）', () => {
    const line = render([
      event({ id: 1, type: 'retried', payload: { state: 'metadata_ready', action: 'recheck' } }),
      event({ id: 2, type: 'retried', payload: { state: 'metadata_ready', action: 'retry' } }),
      event({ id: 3, type: 'retried', payload: { state: 'completed' } }),
    ])

    expect(line.getByText(/重新校驗並接著下載/)).toBeInTheDocument()
    expect(line.getByText(/重新開始這一筆/)).toBeInTheDocument()
    expect(line.getByText(/退回「下載完成」/)).toBeInTheDocument()
    expect(line.queryByText(/退回「已建立」/)).not.toBeInTheDocument()
  })

  it('重新入庫那一筆的標籤是「重新入庫」，不是「重試」（M2 票 10）', () => {
    const line = render([
      event({ type: 'retried', payload: { state: 'completed', action: 'reimport' } }),
    ])

    expect(line.getByText('重新入庫', { selector: 'span' })).toBeInTheDocument()
    expect(line.queryByText('重試')).not.toBeInTheDocument()
  })

  it('目標上有別人的檔案時，停下來那一筆說得出來', () => {
    const line = render([event({ type: 'review_required', payload: { reason: 'target_exists' } })])

    expect(line.getByText(/目標位置上已經有別的檔案/)).toBeInTheDocument()
  })

  it('Jellyfin 一直沒列出檔案時，需要處理那一筆說得出下一步', () => {
    const line = render([
      event({ type: 'issue_detected', payload: { type: 'jellyfin_item_unresolved', count: 3 } }),
    ])

    expect(line.getByText(/Jellyfin 一直沒有列出/)).toBeInTheDocument()
  })

  it('修正那一筆說得出從什麼改成什麼（M2 票 08）', () => {
    const line = render([
      event({
        type: 'rematched',
        actor: '7',
        payload: {
          plan: 5,
          file: 'batch/OVA 2.mkv',
          from: {
            action: 'unmatched',
            season: null,
            episode_start: null,
            episode_end: null,
            target: '',
          },
          to: {
            action: 'import',
            season: 0,
            episode_start: 3,
            episode_end: null,
            target: '/lib/x - S00E03.mkv',
          },
        },
      }),
    ])

    expect(line.getByText('已修正')).toBeInTheDocument()
    expect(line.getByText(/管理員改了這個檔案：.+ → .+ S00E03/)).toBeInTheDocument()
    expect(line.getByText('batch/OVA 2.mkv')).toBeInTheDocument()
    expect(line.getByText('/lib/x - S00E03.mkv')).toBeInTheDocument()
  })

  it('重複版本：略過的那一筆說有幾個、決定的那一筆說決定了什麼', () => {
    const line = render([
      event({ id: 1, type: 'duplicate_skipped', payload: { plan: 2, files: ['a.mkv', 'b.mkv'] } }),
      event({
        id: 2,
        type: 'duplicate_decided',
        payload: {
          decision: 'replace',
          file: 'a.mkv',
          target: '/lib/a.mkv',
          replaced: '/lib/a.mkv',
        },
      }),
    ])

    expect(line.getByText(/2 個檔案與媒體庫裡已有的一份重複/)).toBeInTheDocument()
    expect(line.getByText('管理員用這一份取代了媒體庫裡的舊版本')).toBeInTheDocument()
    expect(line.getByText('/lib/a.mkv')).toBeInTheDocument()
  })
})

describe('時間線摘要（M2 票 12）', () => {
  it('只畫最近幾段；連續的鏈接算一段，較早的筆數算的是事件', () => {
    renderWithProviders(
      <JobTimeline
        latest={2}
        events={[
          event({ id: 1, type: 'created' }),
          event({ id: 2, type: 'completed' }),
          event({ id: 3, type: 'linked', payload: { target: '/a' } }),
          event({ id: 4, type: 'linked', payload: { target: '/b' } }),
          event({ id: 5, type: 'jellyfin_scan_requested', payload: { count: 2 } }),
        ]}
      />,
    )

    expect(screen.getByText('已通知 Jellyfin')).toBeInTheDocument()
    expect(screen.getByText('已鏈接')).toBeInTheDocument()
    expect(screen.queryByText('下載完成')).toBeNull()
    expect(screen.getByText('較早的 2 筆事件在詳情頁。')).toBeInTheDocument()
  })

  it('全部畫得下時不說還有較早的', () => {
    renderWithProviders(<JobTimeline latest={3} events={[event({ id: 1, type: 'created' })]} />)

    expect(screen.queryByText(/較早的/)).toBeNull()
  })
})
