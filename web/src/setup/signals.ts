import type { DetectionReason, ServiceDetection, SetupStatus } from '../api/setup'
import type { ServiceKind } from '../api/schemas'
import type { Signal } from '../components/signal'

/**
 * 判定 → 信號。套件內是 `neutral`：Berth 會自己接手，不需要使用者做什麼，
 * 但也還沒完成，所以既不是黃的也不是綠的。既有服務連得上是 `secured`
 * （這一步的事做完了，那個泊位自己的工作在它的步驟）；連不上才是 `assigned`。
 *
 * 「連得上」是後端算的（`resolved`）：那條規則同時決定精靈能不能離開第 2 步，
 * 兩邊各存一份遲早會不一致。
 */
export function signalOf(detection: ServiceDetection | undefined): Signal {
  if (!detection) return 'neutral'
  switch (detection.origin) {
    case 'bundled':
      return 'neutral'
    case 'existing':
      return detection.resolved ? 'secured' : 'assigned'
    case 'pending':
      return 'working'
    case 'timeout':
      return 'blocked'
  }
}

/** 既有與逾時都要能就地填連線資訊（票 05 驗收：從 `COMPOSE_PROFILES` 拿掉之後要出現表單）。 */
export function needsConnectionForm(detection: ServiceDetection | undefined): boolean {
  if (!detection) return false
  return detection.origin === 'existing' || detection.origin === 'timeout'
}

/** 連線表單的位址範例：區網上的一台，port 是那個服務的預設（不是三個都寫 Jellyfin 的）。 */
export const EXAMPLE_ADDRESS: Record<ServiceKind, string> = {
  jellyfin: 'http://192.168.1.10:8096',
  qbittorrent: 'http://192.168.1.10:8080',
  prowlarr: 'http://192.168.1.10:9696',
}

/** 只有位址是每個服務都要填的；其餘欄位逐服務不同。 */
export function connectFields(kind: ServiceKind): ReadonlyArray<'apiKey' | 'credentials'> {
  if (kind === 'prowlarr') return ['apiKey']
  if (kind === 'qbittorrent') return ['credentials']
  return []
}

/** 探測打的那一支（plan §9.3 第 2 步）。主機與 port 是後端給的，見 `probeEndpoint`。 */
const PROBE_PATH: Record<ServiceKind, string> = {
  jellyfin: '/System/Info/Public',
  qbittorrent: '/api/v2/app/version',
  prowlarr: '/ping',
}

/**
 * 剖面與纜繩上寫的「探哪裡」：`主機:port/路徑`。主機與 port 照後端的 `probe_targets`——
 * qBittorrent 的 port 是 `.env` 的 `QBITTORRENT_WEBUI_PORT`，寫死的話換了 port 就說錯（票 06h）。
 */
export function probeEndpoint(status: SetupStatus, kind: ServiceKind): string {
  // OpenAPI 把 dict 寫成任意鍵；後端三個服務一定都給（`services/clients.bundled_targets`）。
  return status.probe_targets[kind]!.replace(/^https?:\/\//, '') + PROBE_PATH[kind]
}

export const REASON_LABEL = {
  setup_pending: 'reason.setup_pending',
  setup_completed: 'reason.setup_completed',
  anonymous_ok: 'reason.anonymous_ok',
  auth_required: 'reason.auth_required',
  ip_banned: 'reason.ip_banned',
  no_indexers: 'reason.no_indexers',
  has_indexers: 'reason.has_indexers',
  api_key_missing: 'reason.api_key_missing',
  not_deployed: 'reason.not_deployed',
  unreachable: 'reason.unreachable',
  starting: 'reason.starting',
  protocol_mismatch: 'reason.protocol_mismatch',
  connected: 'reason.connected',
} as const satisfies Record<DetectionReason, string>
