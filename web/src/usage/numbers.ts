/**
 * 用量頁與步驟頁的數字寫法（M5 票 21）。**不知道的不當 0**：全部不知道寫「—」或「未知」，
 * 部分不知道在知道的那一份後面接「+未知」（`unknownMark`），說明在表下。
 */

/** 估計費用。一美分以下多留兩位：一輪常常只花 $0.003。 */
export function usd(value: number, language: string): string {
  const digits = value !== 0 && Math.abs(value) < 1 ? 4 : 2
  return `$${value.toLocaleString(language, { minimumFractionDigits: digits, maximumFractionDigits: digits })}`
}

export function tokens(value: number, language: string): string {
  return value.toLocaleString(language)
}

/** 快取命中率；沒有 input 是 `null`。 */
export function percent(rate: number | null, unknown: string): string {
  return rate === null ? unknown : `${Math.round(rate * 100)}%`
}

export interface Tally {
  known: number
  /** 幾次呼叫知道。0 也是知道：知道的加總是 0 不等於全部不知道。 */
  counted: number
  unknown: number
}

/**
 * 「知道的加總 + 幾次不知道」的一格：全部知道照寫；一次都不知道寫 `none`；兩者都有寫「知道的 +未知」。
 */
export function tally(
  value: Tally,
  format: (known: number) => string,
  { none, partial }: { none: string; partial: (known: string) => string },
): string {
  if (value.unknown === 0) return format(value.known)
  if (value.counted === 0) return none
  return partial(format(value.known))
}

/** 一格可能是 `null`（接口沒報）的 token 數。 */
export function maybeTokens(value: number | null, language: string, none: string): string {
  return value === null ? none : tokens(value, language)
}

/** 耗時：一秒以下寫毫秒。 */
export function duration(ms: number, language: string): string {
  if (ms < 1000) return `${ms.toLocaleString(language)} ms`
  return `${(ms / 1000).toLocaleString(language, { maximumFractionDigits: 1 })} s`
}
