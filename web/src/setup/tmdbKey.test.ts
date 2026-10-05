import { describe, expect, it } from 'vitest'

import { looksLikeTmdbKey } from './tmdbKey'

describe('looksLikeTmdbKey（M4 票 31）', () => {
  it.each([
    ['a v3 API key', '0123456789abcdef0123456789ABCDEF'],
    ['a v4 read access token', 'eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJ4In0.c2lnbmF0dXJlLXBhcnQ_-'],
    ['either one with stray spaces around it', '  0123456789abcdef0123456789abcdef \n'],
  ])('takes %s', (_, value) => {
    expect(looksLikeTmdbKey(value)).toBe(true)
  })

  it.each([
    ['a password', 'hunter2'],
    ['a key with a character missing', '0123456789abcdef0123456789abcde'],
    ['a key with a non-hex character', '0123456789abcdef0123456789abcdeg'],
    [
      'two keys pasted together',
      '0123456789abcdef0123456789abcdef 0123456789abcdef0123456789abcdef',
    ],
    ['a token cut short', 'eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJ4In0'],
    ['the settings page URL', 'https://www.themoviedb.org/settings/api'],
  ])('refuses %s', (_, value) => {
    expect(looksLikeTmdbKey(value)).toBe(false)
  })
})
