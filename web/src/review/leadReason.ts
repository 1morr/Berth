import type { TFunction } from 'i18next'

import type { ItemReason } from '../api/plans'
import { reasonParams } from '../plans/reasonText'

/**
 * 收起的 audit 列要說「為什麼是 medium」的那幾種理由（M3 票 05，使用者 2026-09-24 試跑時拍板）。
 *
 * 取的是**把信心壓到 medium 的**那幾條：季集不是明說的（`strategy` 不是 `explicit` / `folder` / `context`
 * 的讀法各自的那一句）、批次一致性只部分通過（`strategy_outlier`），加上兩道只給到 medium 的覆核（標題
 * 對不上、特典編號）。其餘理由（明說的季號、標題對上了）是 medium 的背景，不是原因。
 *
 * **陣列的順序就是優先序**：認錯作品最先，再來是「這一包其餘的不是這樣讀的」——它說得出這一個哪裡不像
 * 同伴，而這一個自己的讀法在展開裡寫著；然後是各種推論與換算，最後是特典編號。
 */
const LEADS = [
  'title_mismatch',
  'strategy_outlier',
  'single_season',
  'season_from_arc',
  'final_season',
  'air_date_run',
  'published_in_run',
  'cour_offset',
  'absolute_group',
  'absolute_cumulative',
  'specials_numbering',
] as const satisfies readonly ItemReason['code'][]

export type LeadCode = (typeof LEADS)[number]

/** 主要原因那一條：`code` 限於 `LEADS`，句子在 `review.audit.lead.*`。 */
export type Lead = ItemReason & { code: LeadCode }

function isLead(reason: ItemReason): reason is Lead {
  return (LEADS as readonly string[]).includes(reason.code)
}

/** 一個檔案收起時說的那一條；沒有降級理由時是 `null`（照舊說「信心 medium，已自動入庫」）。 */
export function leadReason(reasons: readonly ItemReason[]): Lead | null {
  const found = reasons.filter(isLead)
  if (found.length === 0) return null
  return found.reduce((best, reason) =>
    LEADS.indexOf(reason.code) < LEADS.indexOf(best.code) ? reason : best,
  )
}

/**
 * 一組（同一個 Job）收起時說什麼：組內的主要原因都一樣就說一次（`same`），各不相同時說不只一種
 * （`mixed`），都沒有降級理由時什麼都不加（`none`）。
 *
 * 「一樣」比的是**句子會說的那幾格**：`strategy_outlier` 的句子帶著其餘檔案的讀法，讀法不同就是兩句話。
 */
export function groupLead(
  files: readonly (readonly ItemReason[])[],
): { kind: 'same'; reason: Lead } | { kind: 'mixed' } | { kind: 'none' } {
  const leads = files.map(leadReason)
  const first = leads[0] ?? null
  if (!leads.every((lead) => sameLead(lead, first))) return { kind: 'mixed' }
  return first === null ? { kind: 'none' } : { kind: 'same', reason: first }
}

function sameLead(a: Lead | null, b: Lead | null): boolean {
  if (a === null || b === null) return a === b
  return a.code === b.code && a.params.strategy === b.params.strategy
}

/** 主要原因那一句（`review.audit.lead.*`），接在「信心 medium：」後面。 */
export function leadText(t: TFunction, lead: Lead): string {
  // `as never`：同 `reasonText`，鍵是逐 code 的聯集，參數形狀由後端的 `ReasonCode` 定。
  return t(`review.audit.lead.${lead.code}`, reasonParams(t, lead) as never)
}
