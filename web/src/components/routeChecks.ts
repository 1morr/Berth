import type { HealthStatus, RouteCheck } from '../api/schemas'
import type { Signal } from './signal'

/**
 * 泊位 3（媒體庫路徑）的五條纜繩：標題、它打的端點、失敗時的說法（plan §9.5）。
 *
 * 失敗的說法要指出**哪個容器少了哪個掛載**（brief §16.4）——只說「路徑找不到」等於把
 * 唯一有用的訊息丟掉。所以每一條纜繩對應一個容器：Berth 看不到 qBittorrent / Jellyfin 報的
 * 路徑就是 berth 少了掛載；Jellyfin 看不到 Berth 剛寫的檔案就是 jellyfin 少了掛載。
 */

/** Route 的健康 → 信號。`unknown` 不是信號：還沒檢查過。 */
export const ROUTE_SIGNAL = {
  unknown: 'neutral',
  ok: 'secured',
  failed: 'blocked',
} as const satisfies Record<HealthStatus, Signal>

/** 同一份判定的文案。查表而不是動態組 key——動態組過不了 `strictKeyChecks`（票 06）。 */
export const ROUTE_HEALTH_LABEL = {
  unknown: 'routes.health.unknown',
  ok: 'routes.health.ok',
  failed: 'routes.health.failed',
} as const satisfies Record<HealthStatus, string>

export const CHECK_LABEL = {
  category: 'routes.check.category',
  download_path: 'routes.check.downloadPath',
  library_path: 'routes.check.libraryPath',
  probe_visible: 'routes.check.probeVisible',
  hardlink: 'routes.check.hardlink',
} as const satisfies Record<RouteCheck, string>

/** 這一條真的打的那支端點或做的那件事。貼在它那一行，不進散文。 */
export const CHECK_ENDPOINT = {
  category: 'torrents/createCategory',
  download_path: 'app/preferences → stat()',
  library_path: 'Library/VirtualFolders → stat()',
  probe_visible: 'Environment/ValidatePath',
  hardlink: 'link()',
} as const satisfies Record<RouteCheck, string>

export const CHECK_FIX = {
  category: 'routes.fix.category',
  download_path: 'routes.fix.berthMount',
  library_path: 'routes.fix.berthMount',
  probe_visible: 'routes.fix.jellyfinMount',
  hardlink: 'routes.fix.hardlink',
} as const satisfies Record<RouteCheck, string>

/**
 * 修正片段：該容器的 compose `volumes:`（brief §16.4）。
 *
 * 值與 `deploy/docker-compose.yml` 一字不差，貼回去就是對的。`${DATA_ROOT}` 保持變數形式——
 * 使用者的 `.env` 已經有它，把它展開成某個猜出來的宿主路徑反而會貼錯。
 */
const MOUNT = (service: string) => [`  ${service}:`, '    volumes:', '      - ${DATA_ROOT}:/data']

export const CHECK_COMMANDS: Record<RouteCheck, readonly string[]> = {
  category: [],
  download_path: [MOUNT('berth').join('\n')],
  library_path: [MOUNT('berth').join('\n')],
  probe_visible: [MOUNT('jellyfin').join('\n')],
  // 硬鏈接要成立就得**一條**掛載蓋住 complete 與 library 兩個目錄，分開掛就是 EXDEV。
  hardlink: [[...MOUNT('berth'), ...MOUNT('qbittorrent'), ...MOUNT('jellyfin')].join('\n')],
}
