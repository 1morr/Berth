import type { TFunction } from 'i18next'

import type { ExcludedCount } from '../api/rss'
import { formatList } from '../i18n/list'

/**
 * 訂閱之後被排除條件擋下的那幾筆說成一句（M4 票 112）；沒有就是空字串。合集一類一段，三層規則合成一段
 * （作品頁上分不出哪一層，要看細節去 RSS 頁）。
 */
export function excludedText(
  t: TFunction,
  excluded: readonly ExcludedCount[],
  language: string,
): string {
  let notSingle = 0
  let rule = 0
  for (const one of excluded) {
    if (one.code === 'not_single') notSingle += one.count
    else rule += one.count
  }
  const parts = [
    notSingle > 0 ? t('rss.subscribe.excludedNotSingle', { count: notSingle }) : '',
    rule > 0 ? t('rss.subscribe.excludedRule', { count: rule }) : '',
  ].filter(Boolean)
  if (parts.length === 0) return ''
  // 中文的「合集、區間或季包」裡已經有頓號，兩段之間用逗號。
  const what = language.startsWith('zh') ? parts.join('，') : formatList(parts, language)
  return t('rss.subscribe.excluded', { count: notSingle + rule, what })
}

/** 兩句接起來：中文句號之後不留空格。 */
export function sentences(parts: readonly string[], language: string): string {
  return parts.filter(Boolean).join(language.startsWith('zh') ? '' : ' ')
}
