import { describe, expect, it } from 'vitest'

import { groupRows } from './rowGroups'

type Row = { id: number; kind: string; held: boolean }

function groups(rows: Row[]) {
  return groupRows(
    rows,
    (row) => row.kind,
    (row) => row.held,
  ).map((group) => [group.key, group.held, group.rows.map((row) => row.id)])
}

describe('依決定分組（M1.5 票 09）', () => {
  it('同一個鍵收成一組，組照第一次出現的順序，組裡照原本的順序', () => {
    expect(
      groups([
        { id: 1, kind: 'a', held: false },
        { id: 2, kind: 'b', held: false },
        { id: 3, kind: 'a', held: false },
      ]),
    ).toEqual([
      ['a', false, [1, 3]],
      ['b', false, [2]],
    ])
  })

  it('組裡有一列需要人，整組就排到最前面；需要人的組之間仍照原本的順序', () => {
    expect(
      groups([
        { id: 1, kind: 'a', held: false },
        { id: 2, kind: 'b', held: false },
        { id: 3, kind: 'c', held: true },
        { id: 4, kind: 'b', held: true },
      ]),
    ).toEqual([
      ['b', true, [2, 4]],
      ['c', true, [3]],
      ['a', false, [1]],
    ])
  })
})
