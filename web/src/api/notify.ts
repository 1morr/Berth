import { queryOptions } from '@tanstack/react-query'

import { apiGet, apiPost, apiPut } from './client'
import { parseRefusal, type ReasonSet, type Refusal } from './refusal'
import type { Schemas } from './schemas'

/**
 * `settings/notifications`（M4 票 123，只有 admin）：Discord bot 的 token、我的 Discord 與測試訊息。
 * token 原文只往後端去、永遠不回來：回來的只有「設定了沒」與 Discord 回的 application 名。
 */

export type Notify = Schemas['NotifyOut']

/** 一則測試訊息為什麼沒送到（`DeliveryFailure`）。畫面照它挑人話與補法，原文收進技術細節。 */
export type DeliveryFailure = Schemas['DeliveryFailure']

export type NotifyTest = Schemas['NotifyTestOut']

export type NotifyRefusal = Schemas['NotifyRefusal']

/** 執行期認得的那幾種。少一種或多一種都是編譯錯誤（同 `api/routes.ts`）。 */
const REASONS: ReasonSet<NotifyRefusal> = {
  token_rejected: true,
  discord_unreachable: true,
  discord_id_invalid: true,
  bot_missing: true,
  discord_id_missing: true,
}

/** 認不得的理由是 `null`，畫面照請求為什麼沒成說（`RequestFailed`）。 */
export function notifyRefusalOf(error: unknown): Refusal<NotifyRefusal> | null {
  return parseRefusal(error, REASONS)
}

export const notifyQueryOptions = queryOptions({
  queryKey: ['settings', 'notifications'],
  queryFn: () => apiGet<Notify>('/settings/notifications'),
})

/** 存下 bot token：Berth 先用它問 Discord 一次，問得到才存。空字串是清掉（只有「移除 token」該送）。 */
export function saveBotToken(token: string): Promise<Notify> {
  return apiPut<Notify>('/settings/notifications/bot', { token } satisfies Schemas['BotTokenIn'])
}

/** 存下自己的 Discord ID，連同當下的介面語言（通知用那個語言寫）。空字串是不收通知。 */
export function saveDiscordId(
  discordUserId: string,
  language: Schemas['DiscordIdIn']['language'],
): Promise<Notify> {
  return apiPut<Notify>('/settings/notifications/me', {
    discord_user_id: discordUserId,
    language,
  } satisfies Schemas['DiscordIdIn'])
}

/** 送一則測試私訊給自己。Discord 拒絕也是 200，結果在 `delivered` 與 `failure`。 */
export function sendTestMessage(): Promise<NotifyTest> {
  return apiPost<NotifyTest>('/settings/notifications/test')
}
