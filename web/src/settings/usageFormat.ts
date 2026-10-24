import { useTranslation } from 'react-i18next'

import type { UsageTally } from '../api/ai'

/** 命中率分母是 0 時的那一格：不是 0%，是算不出來。 */
const NO_RATE = '—'

/** 用量頁的數字：依 UI 語言分位；命中率到小數一位（換模型後比得出差別）。 */
export function useUsageFormat() {
  const { i18n } = useTranslation()
  const count = new Intl.NumberFormat(i18n.language)
  const percent = new Intl.NumberFormat(i18n.language, {
    style: 'percent',
    maximumFractionDigits: 1,
  })
  return {
    count: (value: number) => count.format(value),
    rate: (value: number | null) => (value === null ? NO_RATE : percent.format(value)),
  }
}

/** 直條的三段，由下而上。「其他輸入」= 全部輸入扣掉快取讀取：快取寫入、沒快取到的、沒回報的都在裡面。 */
export function segmentsOf(tally: UsageTally) {
  return {
    cacheRead: tally.cache_read_tokens,
    otherInput: Math.max(0, tally.input_tokens - tally.cache_read_tokens),
    output: tally.output_tokens,
  }
}

export type Segment = keyof ReturnType<typeof segmentsOf>

export const SEGMENTS: readonly Segment[] = ['cacheRead', 'otherInput', 'output']

/** 三段的漆：同一色相的三階中性（`.scratch/m5/usage-page-shape.md`〈顏色〉，dataviz 驗證器實跑過）。 */
export const SEGMENT_FILL: Record<Segment, string> = {
  cacheRead: 'bg-ink',
  otherInput: 'bg-ink-dim',
  output: 'bg-bar-faint',
}
