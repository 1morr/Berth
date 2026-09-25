import type { TFunction } from 'i18next'

import type { FileKind, ItemReason, PlanAction } from '../api/plans'
import type { ReasonSet } from '../api/refusal'
import type { resources } from '../i18n/resources'

/** 季集是靠什麼讀出來的（`domain.MappingStrategy`）。它不在任何回應的型別上，只出現在理由的參數裡。 */
type Strategy = keyof (typeof resources)['zh-Hant']['translation']['jobs']['plan']['strategy']

/**
 * 理由參數裡那三個**封閉集合**的鍵，各一份執行期認得的成員。少一種、多一種都是編譯錯誤
 * （同 `api/refusal.ts` 的 `ReasonSet`）；後端多送一種還沒有翻譯的值時照原文印，不印 i18n key。
 */
const KINDS: ReasonSet<FileKind> = {
  video: true,
  subtitle: true,
  font: true,
  audio: true,
  image: true,
  archive: true,
  sample: true,
  disc: true,
  extra: true,
  other: true,
}
const ACTIONS: ReasonSet<PlanAction> = {
  import: true,
  extra: true,
  subtitle: true,
  skip: true,
  unmatched: true,
  review: true,
}
const STRATEGIES: ReasonSet<Strategy> = {
  explicit: true,
  folder: true,
  context: true,
  arc_name: true,
  single_season: true,
  absolute_group: true,
  absolute_cumulative: true,
  air_date_offset: true,
  cour_offset: true,
  published_run: true,
  movie: true,
}

function member<R extends string>(set: ReasonSet<R>, value: unknown): value is R {
  return typeof value === 'string' && Object.hasOwn(set, value)
}

/**
 * Plan Item 的一條理由 → 一句話（M2 票 07）。
 *
 * **句子只在前端**：後端給的是封閉集合的 code 加參數（`domain.ReasonCode`），參數是檔名、季集、
 * 日期這種不翻譯的事實。`code` 取自產出的型別，所以 `jobs.plan.why.*` 少一句是 `tsc` 錯誤——
 * zh-Hant 與 en 的鍵樹又是同一棵（`resources.ts` 的 `Translations`），兩份語言一起被守著。
 */
export function reasonText(t: TFunction, reason: ItemReason): string {
  // `as never`：鍵是逐 code 的聯集，i18next 的型別因此要求**每一句**的參數同時都在（交集）。
  // 參數逐 code 不同，形狀由後端的 `ReasonCode` 定；鍵本身仍然被型別檢查。
  return t(`jobs.plan.why.${reason.code}`, reasonParams(t, reason) as never)
}

/**
 * 一條理由的參數，三個封閉集合的鍵換成翻好的字。審核頁收起時那一句主要原因（`review/leadReason.ts`）
 * 用的是另一組句子，參數同一份。
 */
export function reasonParams(t: TFunction, reason: ItemReason): Record<string, string | number> {
  const params: Record<string, string | number> = { ...reason.params }
  if (member(KINDS, params.kind)) params.kind = t(`jobs.plan.kind.${params.kind}`)
  if (member(ACTIONS, params.action)) params.action = t(`jobs.plan.action.${params.action}`)
  if (member(STRATEGIES, params.strategy))
    params.strategy = t(`jobs.plan.strategy.${params.strategy}`)
  return params
}
