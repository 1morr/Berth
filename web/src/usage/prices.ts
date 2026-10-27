import type { TFunction } from 'i18next'

import type { AiEndpoint } from '../api/ai'

type PriceSource = NonNullable<AiEndpoint['price']>['source']

/** 價目從哪來（M5 票 21b）：genai-prices 的版本與它認出的服務商，或 Berth 補位表的查證日期。 */
export function priceSourceText(t: TFunction, source: PriceSource): string {
  return source.table === 'genai_prices'
    ? t('usage.prices.source.genaiPrices', { version: source.version, vendor: source.vendor })
    : t('usage.prices.source.berth', { date: source.verified ?? '' })
}

/** 端點寫成主機加路徑（`api.deepseek.com/anthropic`），不帶 `https://`。 */
export function endpointText(baseUrl: string): string {
  return baseUrl.replace(/^https?:\/\//, '')
}
