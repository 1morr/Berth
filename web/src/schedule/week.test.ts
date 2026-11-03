import { describe, expect, it } from 'vitest'

import { airingTime } from './week'

/** 週六 23:00（日本時間）＝ 14:00Z；週六 01:30（日本時間，「25:30」）＝週五 16:30Z。 */
const SATURDAY_NIGHT = '2026-11-07T14:00:00Z'
const LATE_FRIDAY = '2026-11-06T16:30:00Z'

describe('放送時刻（M5.5 票 14）', () => {
  it('落在卡片那一天就只寫時刻（24 小時制）', () => {
    expect(airingTime(SATURDAY_NIGHT, '2026-11-07', 'zh-Hant', 'Asia/Tokyo')).toBe('23:00')
    expect(airingTime(SATURDAY_NIGHT, '2026-11-07', 'en', 'Asia/Tokyo')).toBe('23:00')
  })

  it('本地日期不是卡片那一天時前面寫星期（深夜檔、時差）', () => {
    // TMDB 把「25:30」記在週五；本地已經是週六
    expect(airingTime(LATE_FRIDAY, '2026-11-06', 'zh-Hant', 'Asia/Tokyo')).toBe('週六 01:30')
    expect(airingTime(LATE_FRIDAY, '2026-11-06', 'en', 'Asia/Tokyo')).toBe('Sat 01:30')
    // 台北慢一小時：還在週六
    expect(airingTime(LATE_FRIDAY, '2026-11-06', 'zh-Hant', 'Asia/Taipei')).toBe('週六 00:30')
    // 紐約：同一刻還是週五上午
    expect(airingTime(LATE_FRIDAY, '2026-11-06', 'en', 'America/New_York')).toBe('11:30')
  })
})
