import { describe, expect, it } from 'vitest'

import type { OneshotItem } from '../api/rss'
import { freshSingles, sendOrder, tally, type Outcome } from './oneshotBatch'

function row(guid: string, overrides: Partial<OneshotItem> = {}): OneshotItem {
  return {
    guid,
    title: `[LoliHouse] Kamiina Botan - ${guid} [WebRip 1080p]`,
    link: '',
    url: `https://mikanani.me/Download/${guid}.torrent`,
    info_hash: guid,
    size: null,
    published_at: null,
    release_kind: 'single',
    tags: {
      source: 'WEB',
      resolution: '1080p',
      subs: [],
      hardsub: false,
      group: 'LoliHouse',
      version: '',
      edition: '',
    },
    season: null,
    episode_start: Number(guid),
    episode_end: Number(guid),
    whole_season: false,
    strategy: null,
    job_hash: '',
    known: null,
    ...overrides,
  }
}

describe('一次性 RSS 連結的那一批', () => {
  it('勾選的那幾筆舊的先送：feed 新的在前，照反序', () => {
    const feed = [row('03'), row('02'), row('01')]
    expect(sendOrder(feed, new Set(['01', '03'])).map((item) => item.guid)).toEqual(['01', '03'])
  })

  it('勾選全部單集：跳過合集、已有下載與帳本已有的', () => {
    const feed = [
      row('04'),
      row('03', { job_hash: '03' }),
      row('02', { known: 'Kamiina Botan - S01E02.mkv' }),
      row('01'),
      row('batch', { release_kind: 'collection' }),
    ]
    expect([...freshSingles(feed)]).toEqual(['04', '01'])
  })

  it('送完之後數得出三種結果', () => {
    const outcomes = new Map<string, Outcome>([
      ['01', { kind: 'sent', hash: 'a' }],
      ['02', { kind: 'sent', hash: 'b' }],
      ['03', { kind: 'already', hash: 'c' }],
      ['04', { kind: 'refused', reason: 'low_disk_space', detail: '' }],
    ])
    expect(tally(outcomes)).toEqual({ sent: 2, already: 1, refused: 1 })
  })
})
