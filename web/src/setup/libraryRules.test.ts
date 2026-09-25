import { describe, expect, it } from 'vitest'

import type { LibraryDraft } from '../api/setup'
import { folderFor, problemsOf } from './libraryRules'

function row(name: string, folder: string): LibraryDraft {
  return { name, folder, collection_type: 'tvshows' }
}

describe('名稱推導資料夾', () => {
  it('ASCII 的名稱照後端 `library_slug` 的規則推：小寫、不安全字元換成 -', () => {
    expect(folderFor('Movies')).toBe('movies')
    expect(folderFor('TV: Kids ')).toBe('tv- kids')
    expect(folderFor('Anime / Old')).toBe('anime - old')
  })

  it('名稱不是 ASCII 就不推，要使用者自己填', () => {
    expect(folderFor('電視劇（華語）')).toBe('')
    expect(folderFor('Anime 動畫')).toBe('')
  })

  it('推不出東西就是空的，不是 berth', () => {
    expect(folderFor('')).toBe('')
    expect(folderFor(' .. ')).toBe('')
  })
})

describe('清單的規則（與後端 `check_bundled_libraries` 同一組）', () => {
  it('預設三列與任意命名的清單都沒有問題', () => {
    const rows = [row('Movies', 'movies'), row('電視劇（華語）', 'tv-zh'), row('紀錄片', '紀錄片')]

    expect(problemsOf(rows)).toEqual({ empty: false, rows: [{}, {}, {}] })
  })

  it('一列都沒有就擋', () => {
    expect(problemsOf([])).toEqual({ empty: true, rows: [] })
  })

  it('空的名稱與資料夾各自標在那一格', () => {
    expect(problemsOf([row(' ', ' ')]).rows).toEqual([
      { name: 'name_missing', folder: 'folder_missing' },
    ])
  })

  it('重複標在後面那一列，不分大小寫、前後空白不算', () => {
    const rows = [row('TV', 'tv'), row(' tv', 'TV '), row('Anime', 'anime')]

    expect(problemsOf(rows).rows).toEqual([{}, { name: 'name_taken', folder: 'folder_taken' }, {}])
  })

  it.each(['..', '.', '../tv', '/data/tv', 'tv/anime', 'tv\\anime'])(
    '「%s」跳出 library_root 或往下鑽',
    (folder) => {
      expect(problemsOf([row('TV', folder)]).rows[0]).toEqual({ folder: 'folder_outside_root' })
    },
  )

  it.each(['tv:zh', 'tv?', 'tv"', 'tv|zh', 'tv<', 'tv*', 'tv\u0001'])(
    '「%s」有 Windows 不收的字元',
    (folder) => {
      expect(problemsOf([row('TV', folder)]).rows[0]).toEqual({ folder: 'folder_characters' })
    },
  )
})
