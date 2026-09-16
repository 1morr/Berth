import { JELLYFIN_STEPS, type JellyfinStep } from '../api/setup'

/**
 * plan §9.4 的七步。**每一步標的是它真的打的那支端點**，不是一句形容——剖面裡逐行列出來，
 * 使用者按之前就知道 Berth 會對他的 Jellyfin 做什麼（direction contract 的 Proof）。
 *
 * 沒有「裝插件」與「重啟」：Berth 只支援 Jellyfin 12，而 12.x 原生合併多版本（票 14b）。
 */
export const STEP_ENDPOINT: Record<JellyfinStep, string> = {
  public_info: 'GET /System/Info/Public',
  configuration: 'POST /Startup/Configuration',
  admin_user: 'POST /Startup/User',
  libraries: 'POST /Library/VirtualFolders',
  remote_access: 'POST /Startup/RemoteAccess',
  complete: 'POST /Startup/Complete',
  api_key: 'POST /Auth/Keys',
}

export const STEP_LABEL = {
  public_info: 'jellyfin.step.public_info',
  configuration: 'jellyfin.step.configuration',
  admin_user: 'jellyfin.step.admin_user',
  libraries: 'jellyfin.step.libraries',
  remote_access: 'jellyfin.step.remote_access',
  complete: 'jellyfin.step.complete',
  api_key: 'jellyfin.step.api_key',
} as const satisfies Record<JellyfinStep, string>

/** 失敗時的手動步驟說明。與 `STEP_LABEL` 一樣是查表而不是拼字串——拼出來的 key 型別檢查不到。 */
export const STEP_FIX = {
  public_info: 'jellyfin.fix.public_info',
  configuration: 'jellyfin.fix.configuration',
  admin_user: 'jellyfin.fix.admin_user',
  libraries: 'jellyfin.fix.libraries',
  remote_access: 'jellyfin.fix.remote_access',
  complete: 'jellyfin.fix.complete',
  api_key: 'jellyfin.fix.api_key',
} as const satisfies Record<JellyfinStep, string>

/**
 * 失敗時可複製的手動步驟（PRODUCT.md 原則 4）。`base` 是那台 Jellyfin 的位址，
 * 因為每一條手動步驟都要在**他自己那台**上做。
 */
export function manualSteps(step: string, base: string): readonly string[] {
  switch (step) {
    case 'public_info':
      return ['docker compose ps jellyfin', 'docker compose logs --tail 50 jellyfin']
    case 'configuration':
    case 'admin_user':
    case 'remote_access':
    case 'complete':
      return [`${base}/web/#/wizard/start`]
    case 'libraries':
      return [`${base}/web/#/dashboard/libraries`]
    case 'api_key':
      return [`${base}/web/#/dashboard/keys`]
    default:
      return []
  }
}

export function isJellyfinStep(step: string): step is JellyfinStep {
  return (JELLYFIN_STEPS as readonly string[]).includes(step)
}
