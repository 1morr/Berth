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

/**
 * 測試打的第一支（`services/setup._test_connection`）。Prowlarr 問 `system/status`：1.3.2 之前沒有 `/ping`，
 * 版本就說不出來了（M4 票 20）。
 */
const TEST_PATH: Record<ServiceKind, string> = {
  jellyfin: '/System/Info/Public',
  qbittorrent: '/api/v2/app/version',
  prowlarr: '/api/v1/system/status',
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

/**
 * 測試那一條行首的「連哪裡」：`主機:port`（M4 票 21）。路徑是 Berth 內部打哪一支端點，收進技術細節
 * （`testEndpoint`）。
 */
export function testTarget(status: SetupStatus, kind: ServiceKind): string {
  const chosen = status.services.find((row) => row.kind === kind)?.base_url
  // OpenAPI 把 dict 寫成任意鍵；後端三個服務一定都給（`services/clients.bundled_targets`）。
  return (chosen || status.bundled_targets[kind]!).replace(/^https?:\/\//, '').replace(/\/+$/, '')
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

/**
 * 把套件內那一台起回來（M4 票 30、35）：還沒選時「套件內」卡片下的那一份，與選了之後主機名解不到的補法是同一組。
 * 只查 DNS 分不出兩種原因——停掉的容器與不在 `COMPOSE_PROFILES` 裡的服務都解不到——所以兩種都給。
 */
export function bringBack(
  status: SetupStatus,
  kind: ServiceKind,
): { stopped: string[]; missing: string[] } {
  return {
    stopped: [`docker compose start ${kind}`],
    missing: [composeProfiles(status, kind, 'bundled'), 'docker compose up -d'],
  }
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
  scheme_mismatch: 'reason.scheme_mismatch',
  scheme_missing: 'reason.scheme_missing',
  version_unsupported: 'reason.version_unsupported',
  other_server: 'reason.other_server',
} as const satisfies Record<ConnectionReason, string>

/**
 * 連線卡上那一句理由（M4 票 31）。代碼是共用的，但說法看是哪一台、在哪個狀態：
 *
 * - 帳密被拒：Berth 對 qBittorrent 用帳密，對其餘兩台用 API key，不說「帳密或 API key」讓人猜。
 * - 還在等套件內那一台起來（`waiting`）：起到一半的服務會回不像它自己的東西或乾脆不答，那一輪的
 *   `protocol_mismatch` / `unreachable` 只是還沒起好；等完了還是那樣才照實說（實測 B 線：倒數
 *   0/120 秒時寫「回的東西不是這個服務」）。
 */
export function reasonLabel(
  kind: ServiceKind,
  reason: ConnectionReason,
  state: ConnectionState | null | undefined,
) {
  if (state === 'waiting' && (reason === 'protocol_mismatch' || reason === 'unreachable')) {
    return 'reason.coming_up'
  }
  if (reason === 'auth_required' && kind === 'qbittorrent') return 'reason.auth_required_login'
  return REASON_LABEL[reason]
}

/**
 * 位址的協定寫錯時的補法（M4 票 25）：服務頁的連線卡與頁 4 的既有表單說同一句，不叫人查 port。
 * 不是這兩種理由時是 `undefined`，呼叫端照自己的規則挑。
 */
export function schemeFix(reason: ConnectionReason | null | undefined) {
  if (reason === 'scheme_mismatch') return 'connection.fix.schemeMismatch' as const
  if (reason === 'scheme_missing') return 'connection.fix.schemeMissing' as const
  return undefined
}

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
