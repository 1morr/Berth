import type { ConnectionReason, ConnectionState, SetupService, SetupStatus } from '../api/setup'
import type { ServiceKind } from '../api/schemas'
import type { Signal } from '../components/signal'

/**
 * 測試結果 → 信號（M4 票 15）。還沒選是 `neutral`；連上了是 `secured`（這一條繫上了，那一頁自己的
 * 事在它下面）；套件內那一台還在啟動是 `working`；其餘紅燈。
 */
export function signalOf(service: SetupService | undefined): Signal {
  if (!service || service.state === null || service.state === undefined) return 'neutral'
  const SIGNAL = {
    ok: 'secured',
    waiting: 'working',
    failed: 'blocked',
    timeout: 'blocked',
  } as const satisfies Record<ConnectionState, Signal>
  return SIGNAL[service.state]
}

/** 這個服務選了、而且連得上：那一頁自己的事（擁有者表單、偏好、索引站）才出現。 */
export function connected(service: SetupService | undefined): boolean {
  return service?.state === 'ok'
}

/** 連線表單的位址範例：區網上的一台，port 是那個服務的預設（不是三個都寫 Jellyfin 的）。 */
export const EXAMPLE_ADDRESS: Record<ServiceKind, string> = {
  jellyfin: 'http://192.168.1.10:8096',
  qbittorrent: 'http://192.168.1.10:8080',
  prowlarr: 'http://192.168.1.10:9696',
}

/**
 * 選「既有」時要填的東西，位址以外逐服務不同（brief §16.4）：Jellyfin 的管理員帳密在擁有者表單、
 * qBittorrent 的 WebUI 帳密、Prowlarr 的 API key。
 */
export function connectFields(kind: ServiceKind): ReadonlyArray<'apiKey' | 'credentials'> {
  if (kind === 'prowlarr') return ['apiKey']
  if (kind === 'qbittorrent') return ['credentials']
  return []
}

/** 測試打的那一支（`services/setup._probe`）。 */
const TEST_PATH: Record<ServiceKind, string> = {
  jellyfin: '/System/Info/Public',
  qbittorrent: '/api/v2/app/version',
  prowlarr: '/ping',
}

/**
 * 測試那一條寫的「連哪裡」：`主機:port/路徑`。選了就是選下的那一條；還沒選時是套件內會連的
 * compose 位址（後端的 `bundled_targets`——qBittorrent 的 port 是 `.env` 的設定值，票 06h）。
 */
export function testEndpoint(status: SetupStatus, kind: ServiceKind): string {
  const chosen = status.services.find((row) => row.kind === kind)?.base_url
  // OpenAPI 把 dict 寫成任意鍵；後端三個服務一定都給（`services/clients.bundled_targets`）。
  const target = chosen || status.bundled_targets[kind]!
  return target.replace(/^https?:\/\//, '') + TEST_PATH[kind]
}

/** `.env` 預設的那一行（`deploy/.env.example`）。 */
const ALL_PROFILES: readonly ServiceKind[] = ['jellyfin', 'qbittorrent', 'prowlarr']

/**
 * `.env` 的 `COMPOSE_PROFILES` 該是哪一行（plan §9.3）：選了「既有」的服務不在裡面，其餘（套件內、
 * 還沒選的）都在。`kind` 照 `origin` 算——選既有時給拿掉它的那一行，套件內那一台不在 compose 裡時給
 * 加回它的那一行。照整份選擇算而不是只動這一個：另一個服務已經選了既有、拿掉了，照著貼不該把它的
 * 套件內容器又拉起來（票 15 的 code-review）。
 */
export function composeProfiles(
  status: SetupStatus,
  kind: ServiceKind,
  origin: 'bundled' | 'existing',
): string {
  const existing = new Set(
    status.services.filter((row) => row.origin === 'existing').map((row) => row.kind),
  )
  if (origin === 'existing') existing.add(kind)
  else existing.delete(kind)
  return `COMPOSE_PROFILES=${ALL_PROFILES.filter((each) => !existing.has(each)).join(',')}`
}

export const REASON_LABEL = {
  connected: 'reason.connected',
  setup_pending: 'reason.setup_pending',
  setup_completed: 'reason.setup_completed',
  auth_required: 'reason.auth_required',
  ip_banned: 'reason.ip_banned',
  api_key_missing: 'reason.api_key_missing',
  not_deployed: 'reason.not_deployed',
  unreachable: 'reason.unreachable',
  starting: 'reason.starting',
  protocol_mismatch: 'reason.protocol_mismatch',
  version_unsupported: 'reason.version_unsupported',
  other_server: 'reason.other_server',
} as const satisfies Record<ConnectionReason, string>

/**
 * 版本下限（brief §16.4、§20.14），補法那一句「至少要 X，這一台是 Y」用它。「既有」旁的
 * `choice.existing.floor.*` 說的是同一組數字。
 */
export const VERSION_FLOOR: Record<ServiceKind, string> = {
  jellyfin: 'Jellyfin 12.0',
  qbittorrent: 'qBittorrent 4.4',
  prowlarr: 'Prowlarr 1.3.2',
}

export const STATE_LABEL = {
  ok: 'connection.state.ok',
  waiting: 'connection.state.waiting',
  failed: 'connection.state.failed',
  timeout: 'connection.state.timeout',
} as const satisfies Record<ConnectionState, string>

/** 網址的主機與 port（`jackett:9117`）：Torznab 端點整個算一站時拿它當名字。解析不了就原樣。 */
export function hostOf(url: string): string {
  try {
    return new URL(url).host
  } catch {
    return url
  }
}
