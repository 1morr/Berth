import { describe, expect, it } from 'vitest'

import { resources, SUPPORTED_LANGUAGES } from './resources'

/**
 * 「平台先行的核准就好」只給照字面的列（M5.5 票 04b，使用者 2026-11-04 定）。
 *
 * 換算差一集也剛好早一週，那一句放在有換算的列上會把算錯的列引去核准。所以：
 *
 * - 逐列理由：照字面而早超過九天的（`released_far_ahead_of_airing`）說平台先行；有換算的
 *   （`released_before_airing`）不說，改叫人查季號與 offset。
 * - 整份計劃的理由（`air_date_conflict`，審核頁的短句與下載頁的長說明）不知道是哪一種列，
 *   要說平台先行就得帶著「照字面讀的」這個條件，並說有換算的先查季號與 offset。
 */

/** 叫人直接核准的那一句。 */
const JUST_APPROVE =
  /平台先行[^。；]{0,6}核准|streaming platform aired it first[^.;]{0,10}just approve/i
/** 把平台先行限定在照字面讀的列。 */
const LITERAL_ONLY = /照字面[^。；]{0,20}平台先行|read as written[^.;]{0,60}streaming platform/i
/** 叫人先查季號與 offset。 */
const CHECK_NUMBERING = /季號[^。]{0,10}offset|season[^.]{0,20}offset/i

describe('三個樣式本身（雙向）', () => {
  it('抓得到要抓的寫法', () => {
    expect('平台先行的核准就好').toMatch(JUST_APPROVE)
    expect('If a streaming platform aired it first, just approve').toMatch(JUST_APPROVE)
    expect('照字面讀的列若是平台先行，核准就好').toMatch(LITERAL_ONLY)
    expect('先查季號與 offset').toMatch(CHECK_NUMBERING)
  })

  it('不把無關的句子算進來', () => {
    expect('在地上波先行的範圍內：多半是平台比電視台先播').not.toMatch(JUST_APPROVE)
    expect('平台先行的核准就好').not.toMatch(LITERAL_ONLY)
    expect('季集多半算錯了').not.toMatch(CHECK_NUMBERING)
  })
})

describe.each(SUPPORTED_LANGUAGES)('%s', (language) => {
  const { jobs, review } = resources[language].translation

  it('照字面而早超過九天被擋的列說平台先行的核准就好', () => {
    expect(jobs.plan.why.released_far_ahead_of_airing).toMatch(JUST_APPROVE)
  })

  it('有換算的列不說平台先行，改叫人查季號與 offset', () => {
    expect(jobs.plan.why.released_before_airing).not.toMatch(JUST_APPROVE)
    expect(jobs.plan.why.released_before_airing).toMatch(CHECK_NUMBERING)
  })

  it.each([
    ['審核頁的短句', review.plan.reason.air_date_conflict],
    ['下載頁的長說明', jobs.plan.reason.air_date_conflict],
  ])('整份計劃的理由（%s）只對照字面讀的列說平台先行', (_, text) => {
    expect(text).toMatch(LITERAL_ONLY)
    expect(text).toMatch(CHECK_NUMBERING)
  })
})
