import { useState } from 'react'

import type { ServiceOrigin } from '../api/schemas'

/** 畫面上選著、還沒存下去的那一格，與改它的那一支。 */
export interface ChoiceDraft {
  draft: ServiceOrigin | null
  onDraft: (origin: ServiceOrigin | null) => void
}

/**
 * 畫面上選著、還沒存下去的那一格（M4 票 09）。由頁面持有：標題與 lede 在確認之前就跟著它
 * （票 15 critique），`ServiceChoice` 只讀寫它。頁面卸下就忘掉——回到這一頁從後端的選擇開始。
 */
export function useChoiceDraft(): ChoiceDraft {
  const [draft, setDraft] = useState<ServiceOrigin | null>(null)
  return { draft, onDraft: setDraft }
}
