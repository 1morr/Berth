import type { TFunction } from 'i18next'

import type { StepFailure } from '../api/schemas'

/**
 * 一條纜繩為什麼沒繫上 → 那一句人話（M4 票 21）。
 *
 * 後端回封閉的代碼加少量參數（`SetupStep.failure` / `params`），畫面照代碼查表——動態組 key 過不了
 * `strictKeyChecks`（票 06），而 `satisfies` 讓後端多一個代碼時這裡在 tsc 就紅。每個代碼兩個語言都有
 * 文案，由 `failures.test.ts` 守著。原文不在這裡：它收進 `TechnicalDetails`。
 */
export const FAILURE_TEXT = {
  not_deployed: 'failure.not_deployed',
  unreachable: 'failure.unreachable',
  starting: 'failure.starting',
  auth_rejected: 'failure.auth_rejected',
  ip_banned: 'failure.ip_banned',
  protocol_mismatch: 'failure.protocol_mismatch',
  scheme_mismatch: 'failure.scheme_mismatch',
  scheme_missing: 'failure.scheme_missing',
  not_found: 'failure.not_found',
  version_unsupported: 'failure.version_unsupported',
  login_rejected: 'failure.login_rejected',
  credential_missing: 'failure.credential_missing',
  category_conflict: 'failure.category_conflict',
  save_path_missing: 'failure.save_path_missing',
  path_not_visible: 'failure.path_not_visible',
  directory_missing: 'failure.directory_missing',
  berth_cannot_write: 'failure.berth_cannot_write',
  probe_unseen: 'failure.probe_unseen',
  probe_unreadable: 'failure.probe_unreadable',
  probe_unsettled: 'failure.probe_unsettled',
  library_gone: 'failure.library_gone',
  library_path_gone: 'failure.library_path_gone',
  jellyfin_cannot_see: 'failure.jellyfin_cannot_see',
  cross_device: 'failure.cross_device',
  link_failed: 'failure.link_failed',
  site_cloudflare: 'failure.site_cloudflare',
  site_no_results: 'failure.site_no_results',
  site_unreachable: 'failure.site_unreachable',
  site_rejected: 'failure.site_rejected',
  site_not_offered: 'failure.site_not_offered',
  no_search: 'failure.no_search',
  unexpected: 'failure.unexpected',
} as const satisfies Record<StepFailure, string>

/** 一條失敗的纜繩要的那幾個欄位。票 21 之前存下的失敗沒有代碼，當 `unexpected`。 */
export interface Failed {
  failure?: StepFailure | null
  params?: Readonly<Record<string, string>>
}

/**
 * 那一句人話。`service` 是造成它的那一台（「連不到 qBittorrent」）：同一個代碼在不同的纜繩上
 * 說的是不同的服務，而那是呼叫端才知道的事。
 */
export function failureText(t: TFunction, row: Failed, service: string): string {
  // 每個參數都先給空字串：代碼與參數對不上時（舊資料、後端少給一個）說得短一點，不印出 `{{path}}`。
  const params = { service, version: '', category: '', path: '', library: '', ...row.params }
  return t(FAILURE_TEXT[row.failure ?? 'unexpected'], params)
}
