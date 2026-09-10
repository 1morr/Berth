import { describe, expect, it } from 'vitest'

import type { SearchResult } from '../api/search'
import { estimate, formatCount, formatSize, sortRows, tagTokens } from './searchResult'

function row(overrides: Partial<SearchResult> = {}): SearchResult {
  return {
    title: 'x',
    indexer: 'ACG.RIP',
    size: 0,
    seeders: null,
    info_url: '',
    download_url: '',
    key: 'k',
    info_hash: '',
    tags: {
      source: null,
      resolution: '',
      subs: [],
      hardsub: false,
      group: '',
      version: '',
      edition: '',
    },
    season: null,
    episode_start: null,
    episode_end: null,
    whole_season: false,
    strategy: null,
    ...overrides,
  }
}

describe('結果表那幾格的讀法', () => {
  it('大小用 1024 進位，索引站沒說時是一條破折號', () => {
    expect(formatSize(524288000, 'en')).toBe('500 MB')
    expect(formatSize(9_000_000_000, 'en')).toBe('8.4 GB')
    // 「沒說」與「0 位元組」在畫面上是同一件事：這一筆量不出大小。
    expect(formatSize(0, 'en')).toBe('—')
  })

  it('做種的 null 是「那個站沒報」，不是零', () => {
    expect(formatCount(null, 'en')).toBe('—')
    expect(formatCount(0, 'en')).toBe('0')
  })

  it('預估有三種說法，判斷不出來就說判斷不出來', () => {
    expect(estimate(row({ season: 3, episode_start: 13, episode_end: 13 }))).toEqual({
      code: 'S03E13',
      noteKey: '',
    })
    expect(estimate(row({ season: 3, episode_start: 1, episode_end: 13 }))).toEqual({
      code: 'S03E01–E13',
      noteKey: '',
    })
    expect(
      estimate(row({ season: 3, episode_start: 1, episode_end: 13, whole_season: true })),
    ).toEqual({ code: 'S03', noteKey: 'search.estimate.wholeSeason' })
    expect(estimate(row({ strategy: 'movie' }))).toEqual({
      code: '',
      noteKey: 'search.estimate.movie',
    })
    expect(estimate(row())).toEqual({ code: '', noteKey: 'search.estimate.unknown' })
  })

  it('Tags 照 brief §6.8 的檔名順序，空的欄位整格不畫', () => {
    const tags = row({
      tags: {
        source: 'WEB',
        resolution: '1080p',
        subs: ['CHS', 'CHT'],
        hardsub: true,
        group: 'ANi',
        version: 'v2',
        edition: '',
      },
    }).tags

    expect(tagTokens(tags)).toEqual(['WEB', '1080p', 'CHS+CHT', 'Hardsub', 'ANi', 'v2'])
  })

  it('沒報做種的排在有報的後面——「沒說」拿不出理由排前面', () => {
    const rows = [
      row({ key: 'none', seeders: null }),
      row({ key: 'zero', seeders: 0 }),
      row({ key: 'many', seeders: 9 }),
    ]

    expect(sortRows(rows, 'seeders').map((entry) => entry.key)).toEqual(['many', 'zero', 'none'])
  })
})
