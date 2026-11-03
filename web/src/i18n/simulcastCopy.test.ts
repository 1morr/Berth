import { describe, expect, it } from 'vitest'

import { resources, SUPPORTED_LANGUAGES } from './resources'

/**
 * 「平台先行的核准就好」只給照字面的列（M5.5 票 04b，使用者 2026-11-04 定）。
 *
 * 換算差一集也剛好早一週，那一句放在有換算的列上會把算錯的列引去核准。所以：
 *
 * - 逐列理由：照字面而早 10–14 天的（`released_far_ahead_of_airing`）說平台先行；照字面卻早超過
 *   14 天的（`released_too_early_for_simulcast`）不像先行，不說，改叫人查作品與 TMDB 的日期；
 *   有換算的（`released_before_airing`）不說，改叫人查季號與 offset。
 * - 整份計劃的理由（`air_date_conflict`，審核頁的短句與下載頁的長說明）不知道是哪一種列，
 *   要說平台先行就得帶著「照字面讀、早得像先行」這兩個條件，並說有換算的先查季號與 offset。
 */

/** 叫人直接核准的那一句。 */
const JUST_APPROVE =
  /平台先行[^。；]{0,6}核准|streaming platform aired it first[^.;]{0,10}just approve/i
/** 把平台先行限定在照字面讀的列。 */
const LITERAL_ONLY = /照字面[^。；]{0,20}平台先行|read as written[^.;]{0,60}streaming platform/i
/** 叫人先查季號與 offset。 */
const CHECK_NUMBERING = /季號[^。]{0,10}offset|season[^.]{0,20}offset/i
/** 把平台先行限定在早得還像先行的列（一週左右）。 */
const LIKE_HEAD_START = /(?<!不)像平台先行|early by about a week/i
/** 叫人先查作品認對沒、TMDB 的日期。 */
const CHECK_TITLE_AND_DATE = /作品[^。]{0,12}TMDB[^。]{0,6}日期|title[^.]{0,40}TMDB’s date/i

describe('樣式本身（雙向）', () => {
  it('抓得到要抓的寫法', () => {
    expect('平台先行的核准就好').toMatch(JUST_APPROVE)
    expect('If a streaming platform aired it first, just approve').toMatch(JUST_APPROVE)
    expect('照字面讀的列若是平台先行，核准就好').toMatch(LITERAL_ONLY)
    expect('先查季號與 offset').toMatch(CHECK_NUMBERING)
    expect('照字面讀而早得像平台先行的列').toMatch(LIKE_HEAD_START)
    expect('先查作品有沒有認錯、TMDB 的日期對不對').toMatch(CHECK_TITLE_AND_DATE)
    expect('check that the title is right and that TMDB’s date is right').toMatch(
      CHECK_TITLE_AND_DATE,
    )
  })

  it('不把無關的句子算進來', () => {
    expect('在地上波先行的範圍內：多半是平台比電視台先播').not.toMatch(JUST_APPROVE)
    expect('平台先行的核准就好').not.toMatch(LITERAL_ONLY)
    expect('季集多半算錯了').not.toMatch(CHECK_NUMBERING)
    expect('照字面讀的列若是平台先行').not.toMatch(LIKE_HEAD_START)
    expect('早超過兩週，不像平台先行').not.toMatch(LIKE_HEAD_START)
    expect('more than about a week early').not.toMatch(LIKE_HEAD_START)
    expect('發佈標題與 TMDB 上的作品相同').not.toMatch(CHECK_TITLE_AND_DATE)
  })
})

describe.each(SUPPORTED_LANGUAGES)('%s', (language) => {
  const { jobs, review } = resources[language].translation

  it('照字面而早 10–14 天被擋的列說平台先行的核准就好', () => {
    expect(jobs.plan.why.released_far_ahead_of_airing).toMatch(JUST_APPROVE)
  })

  it('照字面卻早超過 14 天的列不說平台先行，改叫人查作品與 TMDB 的日期', () => {
    expect(jobs.plan.why.released_too_early_for_simulcast).not.toMatch(JUST_APPROVE)
    expect(jobs.plan.why.released_too_early_for_simulcast).toMatch(CHECK_TITLE_AND_DATE)
  })

  it('有換算的列不說平台先行，改叫人查季號與 offset', () => {
    expect(jobs.plan.why.released_before_airing).not.toMatch(JUST_APPROVE)
    expect(jobs.plan.why.released_before_airing).toMatch(CHECK_NUMBERING)
  })

  it.each([
    ['審核頁的短句', review.plan.reason.air_date_conflict],
    ['下載頁的長說明', jobs.plan.reason.air_date_conflict],
  ])('整份計劃的理由（%s）只對照字面讀、早得像先行的列說平台先行', (_, text) => {
    expect(text).toMatch(LITERAL_ONLY)
    expect(text).toMatch(LIKE_HEAD_START)
    expect(text).toMatch(CHECK_NUMBERING)
  })

  it('下載頁的長說明也說照字面卻早太多的先查作品與 TMDB 的日期', () => {
    expect(jobs.plan.reason.air_date_conflict).toMatch(CHECK_TITLE_AND_DATE)
  })
})
