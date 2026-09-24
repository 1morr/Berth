import { describe, expect, it } from 'vitest'

import type { ItemReason } from '../api/plans'
import { groupLead, leadReason } from './leadReason'

const explicit: ItemReason = { code: 'season_from_release', params: { season: 2 } }
const titled: ItemReason = { code: 'title_exact', params: { title: 'SPY x FAMILY' } }
const single: ItemReason = { code: 'single_season', params: {} }
const outlier: ItemReason = { code: 'strategy_outlier', params: { strategy: 'explicit' } }
const mismatch: ItemReason = {
  code: 'title_mismatch',
  params: { release_title: 'Spy Kids', title: 'SPY x FAMILY' },
}

describe('leadReason', () => {
  it('names the inferred season', () => {
    expect(leadReason([titled, single])).toEqual(single)
  })

  it('names the batch consistency that only partly held', () => {
    expect(leadReason([explicit, titled, outlier])).toEqual(outlier)
  })

  it('has nothing to say when no reason pulled the confidence down', () => {
    expect(leadReason([explicit, titled])).toBeNull()
    expect(leadReason([])).toBeNull()
  })

  it('puts a release that may be another title first', () => {
    // 認錯作品時季集算得再漂亮也是錯的：這一句比推論季號更該先看。
    expect(leadReason([single, mismatch])).toEqual(mismatch)
  })

  it('puts the batch outlier before the way this file was read', () => {
    // 同一包其餘的檔案不是這樣讀的，才是這一個可疑的地方；它自己的讀法在展開裡。
    expect(leadReason([single, outlier])).toEqual(outlier)
  })
})

describe('groupLead', () => {
  it('says the reason once when every file shares it', () => {
    expect(groupLead([[titled, single], [single]])).toEqual({ kind: 'same', reason: single })
  })

  it('tells two outliers apart by what the rest of the batch was read with', () => {
    const other: ItemReason = { code: 'strategy_outlier', params: { strategy: 'folder' } }
    expect(groupLead([[outlier], [other]])).toEqual({ kind: 'mixed' })
  })

  it('says there is more than one reason when the files differ', () => {
    expect(groupLead([[single], [explicit]])).toEqual({ kind: 'mixed' })
  })

  it('has nothing to add when no file carries a reason', () => {
    expect(groupLead([[explicit], [titled]])).toEqual({ kind: 'none' })
  })
})
