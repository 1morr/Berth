import { describe, expect, it } from 'vitest'

import { searchTerm } from './searchTerm'

describe('searchTerm', () => {
  it('中文名 / 英文名的發佈取英文那一段', () => {
    expect(
      searchTerm(
        '[喵萌奶茶屋&LoliHouse] 与你相恋到生命尽头 / Kimi ga Shinu made Koi wo Shitai - 12 [WebRip 1080p HEVC-10bit AAC][简繁日内封字幕]',
      ),
    ).toBe('Kimi ga Shinu made Koi wo Shitai')
  })

  it('三段的取最後一段', () => {
    expect(
      searchTerm(
        '[LoliHouse] 尼古喵喵 (邪竜解放版) / ヤニねこ / Yani Neko / Chainsmoker Cat - 11 [WebRip 1080p HEVC-10bit AAC][简繁内封字幕]',
      ),
    ).toBe('Chainsmoker Cat')
  })

  it('沒有斜線的是整段作品名（組名與集號之後的都去掉）', () => {
    expect(
      searchTerm(
        '[ANi]  Re：从零开始的异世界生活 第四季 - 18 [1080P][Baha][WEB-DL][AAC AVC][CHT][MP4]',
      ),
    ).toBe('Re：从零开始的异世界生活 第四季')
  })

  it('讀不出作品名時回原樣', () => {
    expect(searchTerm('  [Group]  ')).toBe('[Group]')
  })
})
