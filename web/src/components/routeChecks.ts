import type { HealthStatus, RouteCheck, StepFailure } from '../api/schemas'
import type { Signal } from './signal'

/**
 * 泊位 3（媒體庫路徑）的六條纜繩：標題、它打的端點、失敗時的補法（plan §9.5）。
 *
 * 補法要指出**哪個容器少了哪個掛載**（brief §16.4）——只說「路徑找不到」等於把唯一有用的訊息
 * 丟掉。每一條纜繩失敗時該改的是**一台**（M4 票 19）：Berth 看不到 qBittorrent 報的路徑是 berth；
 * qBittorrent 讀不到 Berth 寫的探測檔是 qbittorrent；Jellyfin 報的媒體庫路徑 Berth 看不到、或
 * Jellyfin 看不到 Berth 寫的檔，都是 jellyfin——Berth 早就掛著 `/data`，叫人改 berth 是白改；
 * 硬鏈接的 `EXDEV` 才又是 berth 自己。
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
  download_visible: 'routes.check.downloadVisible',
  library_path: 'routes.check.libraryPath',
  probe_visible: 'routes.check.probeVisible',
  hardlink: 'routes.check.hardlink',
} as const satisfies Record<RouteCheck, string>

/** 這一條真的打的那支端點或做的那件事。收進技術細節（M4 票 21）。 */
export const CHECK_ENDPOINT = {
  category: 'torrents/createCategory',
  // 兩種都 stat 分類回報的路徑；套件內另外讀全域 save_path，細節列會並排兩條（M4 票 05）。
  download_path: 'torrents/categories → stat()',
  // 探測檔做成 torrent、停住加入、校驗（M4 票 19，brief §20.2）。
  download_visible: 'torrents/add → torrents/recheck',
  library_path: 'Library/VirtualFolders → stat()',
  probe_visible: 'Environment/ValidatePath',
  hardlink: 'link()',
} as const satisfies Record<RouteCheck, string>

/** 失敗時要改的那一台。`remedyFor` 裡的 `null` 是與掛載無關（分類衝突、硬鏈接不是 `EXDEV`）。 */
type Service = 'berth' | 'qbittorrent' | 'jellyfin'

/**
 * 這一條問的是哪一台：失敗那一句人話裡的 `{{service}}`（「連不到 qBittorrent」）。硬鏈接只在 Berth 自己的
 * 容器裡做。產品名不翻譯，所以是字串不是 i18n key。
 */
export const CHECK_SERVICE = {
  category: 'qBittorrent',
  download_path: 'qBittorrent',
  download_visible: 'qBittorrent',
  library_path: 'Jellyfin',
  probe_visible: 'Jellyfin',
  hardlink: 'Berth',
} as const satisfies Record<RouteCheck, string>

/**
 * 與掛載無關的失敗（M4 票 21）：連不到、帳密不對、被封。這時給 compose 片段只會叫人白改——
 * 原本 qBittorrent 帳密錯時，分類那一條給的是「分類衝突」的補法。
 */
const SERVICE_FAILURES: ReadonlySet<StepFailure> = new Set([
  'not_deployed',
  'unreachable',
  'starting',
  'protocol_mismatch',
  'auth_rejected',
  'ip_banned',
])

/** 哪幾個服務是使用者自己的那一台（M4 票 08）。只有精靈讀得到選擇，健康頁與設定頁不給。 */
export interface ExistingServices {
  jellyfin: boolean
  qbittorrent: boolean
  /** Berth 的下載與媒體庫共用的那個容器路徑（`complete_root` 與 `library_root` 的共同父目錄）。 */
  root: string
}

/** 套件內那一份 compose 的共用掛載。`deploy/docker-compose.yml` 三個容器都是它。 */
const BUNDLED_ROOT = '/data'

const FIX = {
  category: 'routes.fix.category',
  berth: 'routes.fix.berthMount',
  qbittorrent: 'routes.fix.qbittorrentMount',
  library: 'routes.fix.libraryMount',
  jellyfin: 'routes.fix.jellyfinMount',
  hardlink: 'routes.fix.hardlink',
  existingQbittorrent: 'routes.fix.existing.qbittorrentMount',
  existingLibrary: 'routes.fix.existing.libraryMount',
  existingJellyfin: 'routes.fix.existing.jellyfinMount',
  unreachable: 'routes.fix.service.unreachable',
  auth: 'routes.fix.service.auth',
  banned: 'connection.fix.banned',
  probeUnreadable: 'routes.fix.probeUnreadable',
  probeUnsettled: 'routes.fix.probeUnsettled',
  libraryChanged: 'routes.fix.libraryChanged',
  berthCannotWrite: 'routes.fix.berthCannotWrite',
  directoryMissing: 'routes.fix.directoryMissing',
  // 位址的協定寫錯與服務頁同一句（M4 票 25）。
  schemeMismatch: 'connection.fix.schemeMismatch',
  schemeMissing: 'connection.fix.schemeMissing',
} as const

/** 既有服務另說的那一句（票 08）。補法已經是那一台自己的版本時不另說。 */
const ADVICE = {
  qbittorrent: 'routes.fix.existing.qbittorrent',
  split: 'routes.fix.existing.split',
} as const

export interface Remedy {
  /**
   * 失敗時的說明（i18n key）。值裡的 `{{root}}` 由呼叫端帶入 `root`，`{{service}}` 帶 `CHECK_SERVICE`，
   * `{{path}}` 帶那一條纜繩的 `params`。
   */
  fix: (typeof FIX)[keyof typeof FIX]
  /** 修正片段：要改的那一台的 compose `volumes:`。 */
  commands: readonly string[]
  /** 既有服務另說的一句，沒有就是 `null`。 */
  advice: (typeof ADVICE)[keyof typeof ADVICE] | null
  /** 片段與說明裡的共用容器路徑。 */
  root: string
}

/**
 * 一條纜繩失敗時的補法（M4 票 19）：說明、要改的那一台的片段、既有服務另說的一句。
 *
 * **片段對著要改的那一台**，套件內與既有分開寫：套件內的片段與 `deploy/docker-compose.yml` 一字不差；
 * 既有的是「你那一份 compose 裡那個服務」要加的一條，說明裡叫人把 `${DATA_ROOT}` 換成 berth 那一份的值，
 * 並照 TRaSH 的說法改成單一共用掛載、別分開掛 `/downloads`、`/movies`。
 */
export function remedyFor(
  check: RouteCheck,
  {
    existing,
    crossDevice,
    failure,
  }: { existing?: ExistingServices; crossDevice: boolean; failure?: StepFailure | null },
): Remedy {
  const root = existing?.root || BUNDLED_ROOT
  const remedy = (
    fix: Remedy['fix'],
    service: Service | null,
    advice: Remedy['advice'] = null,
  ): Remedy => ({
    fix,
    // 下載與媒體庫沒有共同父目錄（`/`）時沒有一條掛載修得好，片段照貼反而會把宿主目錄掛到根上。
    commands: service && root !== '/' ? [mountSnippet(service, root)] : [],
    advice,
    root,
  })

  // 先看為什麼：與掛載無關的失敗、或檢查自己說得出不是掛載的那幾種，補法不給片段。
  if (failure === 'ip_banned') return remedy(FIX.banned, null)
  if (failure === 'auth_rejected') return remedy(FIX.auth, null)
  if (failure === 'scheme_mismatch') return remedy(FIX.schemeMismatch, null)
  if (failure === 'scheme_missing') return remedy(FIX.schemeMissing, null)
  if (failure && SERVICE_FAILURES.has(failure)) return remedy(FIX.unreachable, null)
  if (failure === 'probe_unreadable') return remedy(FIX.probeUnreadable, null)
  if (failure === 'probe_unsettled') return remedy(FIX.probeUnsettled, null)
  if (failure === 'library_gone' || failure === 'library_path_gone') {
    return remedy(FIX.libraryChanged, null)
  }
  // Berth 在自己的容器裡寫不進、目錄不見了（M4 票 25）：都不是哪一台少了掛載。原本照檢查項目落下去
  // ——寫不進寫入目標被說成 Jellyfin 沒掛、建不了分類目錄被說成分類衝突。
  if (failure === 'berth_cannot_write') return remedy(FIX.berthCannotWrite, null)
  if (failure === 'directory_missing') return remedy(FIX.directoryMissing, null)

  switch (check) {
    case 'category':
      return remedy(FIX.category, null)
    case 'download_path':
      return remedy(FIX.berth, 'berth', existing?.qbittorrent ? ADVICE.qbittorrent : null)
    case 'download_visible':
      return remedy(
        existing?.qbittorrent ? FIX.existingQbittorrent : FIX.qbittorrent,
        'qbittorrent',
      )
    case 'library_path':
      return remedy(existing?.jellyfin ? FIX.existingLibrary : FIX.library, 'jellyfin')
    case 'probe_visible':
      return remedy(existing?.jellyfin ? FIX.existingJellyfin : FIX.jellyfin, 'jellyfin')
    case 'hardlink':
      // 硬鏈接要成立就得**一條**掛載蓋住 complete 與 library 兩個目錄；分開掛就是 EXDEV，
      // 那是 berth 自己的掛載。其餘的失敗（權限、檔案系統不支援）不是改 volumes 修得好的。
      return crossDevice
        ? remedy(
            FIX.hardlink,
            'berth',
            existing?.jellyfin || existing?.qbittorrent ? ADVICE.split : null,
          )
        : remedy(FIX.hardlink, null)
  }
}

/**
 * 修正片段：該容器的 compose `volumes:`（brief §16.4）。
 *
 * `${DATA_ROOT}` 保持變數形式——使用者的 `.env` 已經有它，把它展開成某個猜出來的宿主路徑反而會貼錯。
 */
export function mountSnippet(service: Service, root: string): string {
  return [`  ${service}:`, '    volumes:', `      - \${DATA_ROOT}:${root}`].join('\n')
}

/** 兩條容器路徑的共同父目錄。`/data/torrent/complete` 與 `/data/library` → `/data`。 */
export function commonRoot(a: string, b: string): string {
  const left = a.split('/').filter(Boolean)
  const right = b.split('/').filter(Boolean)
  const shared: string[] = []
  for (const [index, part] of left.entries()) {
    if (right[index] !== part) break
    shared.push(part)
  }
  return `/${shared.join('/')}`
}
