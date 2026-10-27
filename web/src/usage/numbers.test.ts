import { describe, expect, it } from 'vitest'

import { duration, maybeTokens, percent, tally, tokens, usd } from './numbers'

describe('usd', () => {
  it('keeps four places under a dollar, two above', () => {
    expect(usd(0.0034, 'en')).toBe('$0.0034')
    expect(usd(1.5, 'en')).toBe('$1.50')
    expect(usd(0, 'en')).toBe('$0.00')
  })
})

describe('tally', () => {
  const words = { none: 'unknown', partial: (known: string) => `${known} +unknown` }
  const format = (known: number) => tokens(known, 'en')

  it('writes the sum when every call is known', () => {
    expect(tally({ known: 1200, unknown: 0 }, format, words)).toBe('1,200')
  })

  it('does not turn all-unknown into zero', () => {
    expect(tally({ known: 0, unknown: 3 }, format, words)).toBe('unknown')
  })

  it('marks a sum that leaves some calls out', () => {
    expect(tally({ known: 1200, unknown: 1 }, format, words)).toBe('1,200 +unknown')
  })
})

describe('the rest', () => {
  it('writes a missing rate and a missing count as unknown, not zero', () => {
    expect(percent(null, '—')).toBe('—')
    expect(percent(0.784, '—')).toBe('78%')
    expect(maybeTokens(null, 'en', '—')).toBe('—')
    expect(maybeTokens(0, 'en', '—')).toBe('0')
  })

  it('writes durations in ms or seconds', () => {
    expect(duration(420, 'en')).toBe('420 ms')
    expect(duration(6200, 'en')).toBe('6.2 s')
  })
})
