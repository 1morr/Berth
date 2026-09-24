import type { ServiceKind } from '../api/schemas'
import type { ServiceDetection } from '../api/setup'

/**
 * 第 1 步的剖面只分三種 Service Origin（票 06c）。探測中、逾時、清單裡沒有那個服務都還不知道是不是
 * 套件內的——第 2 步才偵測，第 1 步不能把話說死。
 */
export type DetectedOrigin = 'undetected' | 'bundled' | 'existing'

export function detectedOrigin(
  services: readonly ServiceDetection[],
  kind: ServiceKind,
): DetectedOrigin {
  const origin = services.find((row) => row.kind === kind)?.origin
  if (origin === 'bundled' || origin === 'existing') return origin
  return 'undetected'
}

/** 剖面一列：句子在 `admin.cutaway.*`，`account` 填進它的 `{{account}}`。 */
export interface CutawayLine {
  key:
    | 'admin.cutaway.value.account'
    | 'admin.cutaway.value.berthExisting'
    | 'admin.cutaway.value.pair'
    | 'admin.cutaway.value.jellyfinPending'
    | 'admin.cutaway.value.jellyfinOwned'
    | 'admin.cutaway.value.jellyfinExisting'
    | 'admin.cutaway.value.interfacePending'
    | 'admin.cutaway.value.interfaceExisting'
    | 'admin.cutaway.skipped'
  account: string
  muted: boolean
}

const JELLYFIN: Record<DetectedOrigin, CutawayLine['key']> = {
  undetected: 'admin.cutaway.value.jellyfinPending',
  bundled: 'admin.cutaway.value.pair',
  existing: 'admin.cutaway.value.jellyfinExisting',
}

const INTERFACE: Record<DetectedOrigin, CutawayLine['key']> = {
  undetected: 'admin.cutaway.value.interfacePending',
  bundled: 'admin.cutaway.value.pair',
  existing: 'admin.cutaway.value.interfaceExisting',
}

/**
 * 「將會寫入」四列照 `status.services` 的判定說話（票 06c）。
 *
 * - `typed` 是表單上現在的帳號；`owner` 是已經交給 Jellyfin 的那一個（`jellyfin_owns_account`）。
 *   帳號屬於 Jellyfin 之後，Berth 與 Jellyfin 兩列釘在 `owner`，只有兩個介面跟著表單走。
 * - 值寫「帳號 · 密碼同上」，畫面上從不出現密碼本身。
 */
export function adminCutaway({
  services,
  owned,
  applied,
  typed,
  owner,
}: {
  services: readonly ServiceDetection[]
  owned: boolean
  applied: boolean
  typed: string
  owner: string
}): Record<'berth' | 'jellyfin' | 'qbittorrent' | 'prowlarr', CutawayLine> {
  const jellyfin = detectedOrigin(services, 'jellyfin')
  const account = owned ? owner : typed

  function line(key: CutawayLine['key'], who = account, muted = false): CutawayLine {
    return { key, account: who, muted }
  }

  function interfaceLine(kind: 'qbittorrent' | 'prowlarr'): CutawayLine {
    if (!applied) return line('admin.cutaway.skipped', typed, true)
    return line(INTERFACE[detectedOrigin(services, kind)], typed)
  }

  return {
    berth: line(
      jellyfin === 'existing' ? 'admin.cutaway.value.berthExisting' : 'admin.cutaway.value.account',
    ),
    jellyfin: line(
      jellyfin === 'bundled' && owned ? 'admin.cutaway.value.jellyfinOwned' : JELLYFIN[jellyfin],
    ),
    qbittorrent: interfaceLine('qbittorrent'),
    prowlarr: interfaceLine('prowlarr'),
  }
}
