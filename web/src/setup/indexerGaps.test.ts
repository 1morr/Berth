import { describe, expect, it } from 'vitest'

import { ALL_BUNDLED, indexerSetup, setupStatus } from '../test/fixtures'
import { indexerGaps } from './indexerGaps'

/** 頁 4：套件內 Prowlarr 連上了、一站都沒有、介面登入還沒設。 */
const AT_INDEXER = setupStatus({ current_step: 4, owner: 'skipper', services: ALL_BUNDLED })
const NOTHING_YET = indexerSetup()

describe('indexerGaps', () => {
  it('還沒加站、還沒設登入：兩件都差', () => {
    expect(indexerGaps(AT_INDEXER, NOTHING_YET, false)).toEqual(['sites', 'login'])
  })

  // 審計 P2-2：同一屏說著「設定中」，前進鍵的位置卻寫「還差 設定 Prowlarr 介面登入」。
  it('介面登入正在送時不列登入', () => {
    expect(indexerGaps(AT_INDEXER, NOTHING_YET, true)).toEqual(['sites'])
  })
})
