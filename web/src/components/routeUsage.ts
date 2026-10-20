import type { TFunction } from 'i18next'

import type { RouteUsage } from '../api/routes'

/**
 * 「N 筆下載」「M 個入庫檔案」，有 RSS 綁著時再加「K 個 RSS Feed」「L 個 RSS Series」（M4 票 115）。
 * 清單那一列逐段排，刪不得的說明與 409 的拒絕把它們接成一句。下載與檔案是 0 也說，RSS 是 0 不說：
 * 大多數 Route 沒有 RSS，多兩段 0 只是雜訊。
 */
export function usageParts(t: TFunction, usage: RouteUsage): string[] {
  return [
    t('routeSettings.usage.jobs', { count: usage.jobs }),
    t('routeSettings.usage.files', { count: usage.ledger_entries }),
    ...(usage.rss_feeds > 0 ? [t('routeSettings.usage.rssFeeds', { count: usage.rss_feeds })] : []),
    ...(usage.rss_series > 0
      ? [t('routeSettings.usage.rssSeries', { count: usage.rss_series })]
      : []),
  ]
}
