import { describe, expect, it } from 'vitest'

// 與後端 `library_slug` 同一份例子（`tests/unit/test_library_slug.py` 讀同一個檔）：兩邊一分岔，畫面上的
// 資料夾就不是 Berth 建的那一條。`?raw` 讀檔：`tsconfig.app.json` 沒開 JSON 模組。
import shared from './librarySlug.examples.json?raw'

import type { LibraryChoice } from '../api/setup'
import { librarySlug, missingType, newLibraryPath, newLibraryProblem } from './newLibrary'

function library(name: string, type: string, locations: string[] = []): LibraryChoice {
  return {
    name,
    collection_type: type,
    locations,
    berth_path: `/data/library/${name.toLowerCase()}`,
    has_berth_path: false,
    uses_tvdb: false,
    supported: type === 'movies' || type === 'tvshows',
    has_route: false,
    target_path: '',
    listed: false,
    preselected: type === 'movies' || type === 'tvshows',
  }
}

const SHARED = JSON.parse(shared) as { cases: [string, string][]; collisions: string[][] }

describe('新建媒體庫的資料夾', () => {
  it.each(SHARED.cases)('%j → %j', (name, slug) => {
    expect(librarySlug(name)).toBe(slug)
  })

  it.each(SHARED.collisions)('名字不同、資料夾相同：%j', (...names) => {
    expect(new Set(names.map(librarySlug)).size).toBe(1)
  })

  it('落在 library root 底下一層，名稱的前後空白不算', () => {
    expect(newLibraryPath('/data/library/', ' 電影 ')).toBe('/data/library/電影')
  })
})

describe('新的媒體庫預設是哪一種', () => {
  it('那台只有劇集：電影', () => {
    expect(missingType([library('劇集', 'tvshows')])).toBe('movies')
  })

  it('那台只有電影：劇集', () => {
    expect(missingType([library('Films', 'movies'), library('Music', 'music')])).toBe('tvshows')
  })

  it('兩種都有、或一個都沒有：電影', () => {
    expect(missingType([library('Films', 'movies'), library('TV', 'tvshows')])).toBe('movies')
    expect(missingType([])).toBe('movies')
  })
})

describe('新建那一列撞到什麼', () => {
  const theirs = [
    library('Anime', 'tvshows', ['/volume1/anime']),
    library('Films', 'movies', ['/volume1/films', '/data/library/movies']),
  ]

  it('名稱空白', () => {
    expect(newLibraryProblem('  ', '/data/library/berth', theirs, [])).toEqual({
      reason: 'name_missing',
    })
  })

  it('與那台已有的同名，不分大小寫', () => {
    expect(newLibraryProblem('anime', '/data/library/anime', theirs, [])).toEqual({
      reason: 'name_taken',
      holder: 'Anime',
    })
  })

  it('資料夾已經是別的媒體庫的路徑', () => {
    expect(newLibraryProblem('Movies?', '/data/library/movies', theirs, [])).toEqual({
      reason: 'folder_taken',
      holder: 'Films',
    })
  })

  it('資料夾是這一輪別的媒體庫要加的 Berth 路徑', () => {
    const claimed = [{ library: 'TV Shows', path: '/data/library/tv-shows' }]
    expect(newLibraryProblem('TV-Shows', '/data/library/tv-shows', theirs, claimed)).toEqual({
      reason: 'folder_taken',
      holder: 'TV Shows',
    })
  })

  it('都沒撞到', () => {
    expect(newLibraryProblem('紀錄片', '/data/library/紀錄片', theirs, [])).toBeNull()
  })
})
