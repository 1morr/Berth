import { queryOptions } from '@tanstack/react-query'

import { apiGet, apiPost, apiPut } from './client'
import { parseRefusal, type ReasonSet, type Refusal } from './refusal'
import type { Schemas } from './schemas'

/**
 * 通知設定的兩半（M4 票 125）：
 * - `settings/notifications`（只有 admin）：Discord bot 的 token 與 Berth 的網址。token 原文只往後端去、
 *   永遠不回來：回來的只有「設定了沒」與 Discord 回的 application 名。
 * - `me/notifications`（每一位登入的人）：自己的 Discord ID、要收的種類、測試訊息。
 */

export type NotifyBot = Schemas['NotifyBotOut']

export type MyNotify = Schemas['MyNotifyOut']

export type NotificationKind = Schemas['NotificationKind']

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
  berth_url_invalid: true,
}

/** 認不得的理由是 `null`，畫面照請求為什麼沒成說（`RequestFailed`）。 */
export function notifyRefusalOf(error: unknown): Refusal<NotifyRefusal> | null {
  return parseRefusal(error, REASONS)
}

export const botQueryOptions = queryOptions({
  queryKey: ['settings', 'notifications'],
  queryFn: () => apiGet<NotifyBot>('/settings/notifications'),
})

export const myNotifyQueryOptions = queryOptions({
  queryKey: ['me', 'notifications'],
  queryFn: () => apiGet<MyNotify>('/me/notifications'),
})

/** 存下 bot token：Berth 先用它問 Discord 一次，問得到才存。空字串是清掉（只有「移除 token」該送）。 */
export function saveBotToken(token: string): Promise<NotifyBot> {
  return apiPut<NotifyBot>('/settings/notifications/bot', { token } satisfies Schemas['BotTokenIn'])
}

/**
 * 存下自己的 Discord ID 與要收的種類，連同當下的介面語言（通知用那個語言寫）。空 ID 是不收通知。
 */
export function saveMine(mine: Schemas['MyNotifyIn']): Promise<MyNotify> {
  return apiPut<MyNotify>('/me/notifications', mine)
}

/** 存下 Berth 從外面看的網址：通知裡的連結照它組。不是 http(s) 的完整網址回 422 `berth_url_invalid`。 */
export function saveBerthUrl(berthUrl: string): Promise<NotifyBot> {
  return apiPut<NotifyBot>('/settings/notifications/berth-url', {
    berth_url: berthUrl,
  } satisfies Schemas['BerthUrlIn'])
}

/** 送一則測試私訊給自己。Discord 拒絕也是 200，結果在 `delivered` 與 `failure`。 */
export function sendTestMessage(): Promise<NotifyTest> {
  return apiPost<NotifyTest>('/me/notifications/test')
}
