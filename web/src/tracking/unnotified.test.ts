import { describe, expect, it } from 'vitest'

import type { MyNotify } from '../api/notify'
import { unnotified } from './unnotified'

const READY: MyNotify = {
  bot_configured: true,
  bot_name: 'Berth',
  discord_user_id: '123456789012345678',
  language: 'zh-Hant',
  kinds: ['ready', 'waiting'],
  unreachable_at: null,
  unreachable_detail: '',
}

describe('unnotified', () => {
  it('收得到：bot、ID、等你處理都齊，Discord 也到得了', () => {
    expect(unnotified(READY)).toBe(false)
  })

  it.each([
    ['沒有 bot', { bot_configured: false }],
    ['沒填 Discord ID', { discord_user_id: '' }],
    ['沒訂閱等你處理', { kinds: ['ready'] as MyNotify['kinds'] }],
    ['Discord 到不了', { unreachable_at: '2026-11-03T05:00:00Z' }],
  ])('%s就收不到', (_, change) => {
    expect(unnotified({ ...READY, ...change })).toBe(true)
  })
})
