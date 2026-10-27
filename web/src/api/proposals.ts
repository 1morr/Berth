import { queryOptions } from '@tanstack/react-query'

import { apiGet, apiPost } from './client'
import { parseRefusal, type ReasonSet, type Refusal } from './refusal'
import type { Schemas } from './schemas'

/**
 * 確認卡（Proposal，M5 票 08、13；plan §6〈proposals〉）。
 *
 * 側面板裡的卡片照這一份畫，不照模型說的：參數、效果、期限、狀態與逐列結果都是伺服器存的
 * （brief §20.24）。給瀏覽器的參數已經去掉下載連結（M4 票 79）。
 */

export type Proposal = Schemas['ProposalOut']
export type ProposalRow = Schemas['ProposalRowOut']
export type ProposalStatus = Schemas['ProposalStatus']
export type ProposalRefusal = Schemas['ProposalRefusal']

const REASONS: ReasonSet<ProposalRefusal> = {
  proposal_missing: true,
  proposal_decided: true,
  proposal_expired: true,
  selection_invalid: true,
}

export function proposalRefusalOf(error: unknown): Refusal<ProposalRefusal> | null {
  return parseRefusal(error, REASONS)
}

/** 還按得下去的兩種：等人按，與對話往下走了但卡片仍然有效。 */
export const WAITING: ReadonlySet<ProposalStatus> = new Set(['pending', 'detached'])

export function proposalsKey(conversationId: string) {
  return ['proposals', conversationId] as const
}

/** 這段對話的卡片，舊的在前。 */
export function proposalsQueryOptions(conversationId: string) {
  return queryOptions({
    queryKey: proposalsKey(conversationId),
    queryFn: ({ signal }) =>
      apiGet<Proposal[]>(`/proposals?conversation_id=${encodeURIComponent(conversationId)}`, {
        signal,
      }),
  })
}

/**
 * 核准（可帶勾選）或拒絕。**核准就當場執行**，回的是執行完的那一張、逐列結果在裡面。
 * body 不帶參數：執行用伺服器存的那一份。
 */
export function decideProposal(
  id: number,
  decision: { approve: boolean; selection?: number[] | null },
): Promise<Proposal> {
  return apiPost<Proposal>(`/proposals/${id}/decide`, decision)
}
