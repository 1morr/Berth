import { describe, expect, it } from 'vitest'

import i18n from '../i18n'
import { groundText } from './grounds'

const AT = '2026-09-25T13:00:00+00:00'

describe('groundText', () => {
  it('重認的時間照 UI 的語言印成當地時間，不印 ISO 原文', () => {
    const text = groundText(
      i18n.t,
      {
        code: 'lookup_retry',
        params: { site: 'api.themoviedb.org', attempt: 1, at: AT, detail: 'GET /3/tv/1: 502' },
      },
      'en',
    )

    expect(text).toContain(new Date(AT).toLocaleString('en'))
    expect(text).not.toContain(AT)
    expect(text).toContain('api.themoviedb.org')
  })

  it('沒有 `at` 的理由參數原樣帶進句子', () => {
    const text = groundText(
      i18n.t,
      { code: 'premiere_near', params: { premiere: '2026-07-07', season: 1, aired: '2026-07-08' } },
      'en',
    )

    expect(text).toContain('2026-07-07')
    expect(text).toContain('2026-07-08')
  })
})
