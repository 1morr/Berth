import { describe, expect, it } from 'vitest'

import type { Chunk } from '../api/assistant'
import { withChunk, type Item } from './transcript'

/**
 * 串流的 chunk 併進畫面（M5 票 11）：有的 provider 每一輪都用同一個 call id（本機模型的 `call_0`），同一則回覆裡
 * 兩次呼叫同名同 id 時，結果只接到還在跑的那一次。
 */

const start = (id: string): Chunk => ({
  type: 'tool-input-start',
  tool_call_id: id,
  tool_name: 'subscribe_mikan',
})

const output = (id: string, type: string): Chunk => ({
  type: 'tool-output-available',
  tool_call_id: id,
  tool_name: 'subscribe_mikan',
  outcome: type === 'Refusal' ? 'refused' : 'done',
  result_type: type,
  result: (type === 'Refusal'
    ? { reason: 'route_needed', detail: '' }
    : { submitted: 12 }) as Record<string, unknown>,
})

function tools(items: Item[]) {
  return items.flatMap((item) => (item.kind === 'tool' ? [item] : []))
}

describe('withChunk', () => {
  it('同一個 call id 呼叫兩次：結果接到還在跑的那一次，先前那一次照舊', () => {
    let items: Item[] = []
    for (const chunk of [
      start('call_0'),
      output('call_0', 'Refusal'),
      start('call_0'),
      output('call_0', 'Subscribed'),
    ]) {
      items = withChunk(items, chunk)
    }

    const [first, second] = tools(items)
    expect([first.state, first.output?.type]).toEqual(['refused', 'Refusal'])
    expect([second.state, second.output?.type]).toEqual(['done', 'Subscribed'])
    expect(first.key).not.toBe(second.key)
  })
})
