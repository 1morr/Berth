import type { TFunction } from 'i18next'

import type { SubmitRefusal, SubscribeRefusal, ToolRefusal } from '../api/assistant'

/**
 * 登錄表自己的拒絕（`ToolRefusal`）、送單的防線（`SubmitRefusal`，M5 票 12：照著標題裡的指令送的那一筆
 * 被擋下時，人要看得懂為什麼）與訂閱的防線（`SubscribeRefusal`，票 11）有人話；其餘模組的理由碼照原樣
 * （機器字串，`.value`）。
 */
const REFUSAL_TEXT = {
  unknown_tool: 'assistant.tools.reason.unknown_tool',
  invalid_input: 'assistant.tools.reason.invalid_input',
  not_allowed: 'assistant.tools.reason.not_allowed',
  changed: 'assistant.tools.reason.changed',
  not_from_this_conversation: 'assistant.tools.reason.not_from_this_conversation',
  other_work: 'assistant.tools.reason.other_work',
  not_a_match: 'assistant.tools.reason.not_a_match',
  episodes_unknown: 'assistant.tools.reason.episodes_unknown',
  other_episodes: 'assistant.tools.reason.other_episodes',
  excluded: 'assistant.tools.reason.excluded',
  route_needed: 'assistant.tools.reason.route_needed',
  bangumi_not_from_this_conversation: 'assistant.tools.reason.bangumi_not_from_this_conversation',
  subgroup_not_from_this_conversation: 'assistant.tools.reason.subgroup_not_from_this_conversation',
} as const satisfies Record<ToolRefusal | SubmitRefusal | SubscribeRefusal, string>

type Reason = keyof typeof REFUSAL_TEXT

export function reasonText(t: TFunction, reason: string, detail: string): string {
  if (!Object.hasOwn(REFUSAL_TEXT, reason)) return reason
  return t(REFUSAL_TEXT[reason as Reason], { detail })
}
