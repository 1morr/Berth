import type { IndexerSetup } from '../api/setup'
import type { QbittorrentSetup, ServiceOrigin } from '../api/schemas'

/**
 * 瀏覽器開一個服務自己的介面的位址（M4 票 09 起於 Prowlarr，票 26 qBittorrent 共用）：要帳號的站要在
 * Prowlarr 自己的介面加，qBittorrent 的偏好寫不進時要去它的設定頁。
 *
 * - **套件內**：Berth 存的位址是 compose 內網的（`http://prowlarr:9696`），瀏覽器解不到那個名字（票 15
 *   critique）。照 Jellyfin 深連結的做法（`services/deeplink.py`）：**瀏覽器現在的主機名** + 它在宿主上
 *   發佈的 port（`PROWLARR_PORT` / `QBITTORRENT_WEBUI_PORT`，後端給）。
 * - **既有**：使用者自己填的位址。填的是 `host.docker.internal` 時那就是跑 Berth 的這台主機，換成瀏覽器的
 *   主機名；填的是 compose 主機名就給不出。
 *
 * 給不出就沒有連結，不給一條開不起來的。
 */
function serviceWeb(
  target: { origin: ServiceOrigin | null; base_url: string; web_port: number | null },
  /** compose 裡那個服務的名字（`deploy/docker-compose.yml` 的服務名）。 */
  composeHost: string,
  page: Pick<Location, 'protocol' | 'hostname'> = window.location,
): string | null {
  if (target.origin === 'bundled') {
    return target.web_port === null ? null : `${page.protocol}//${page.hostname}:${target.web_port}`
  }
  if (target.origin !== 'existing') return null
  let url: URL
  try {
    url = new URL(target.base_url)
  } catch {
    return null
  }
  if (url.hostname === composeHost) return null
  if (url.hostname === 'host.docker.internal') url.hostname = page.hostname
  return `${url.origin}${url.pathname}`.replace(/\/$/, '')
}

/** Prowlarr 的介面。Torznab 端點沒有 Prowlarr 的介面。 */
export function prowlarrWeb(
  indexers: Pick<IndexerSetup, 'origin' | 'kind' | 'base_url' | 'web_port'>,
  page?: Pick<Location, 'protocol' | 'hostname'>,
): string | null {
  return indexers.kind === 'prowlarr' ? serviceWeb(indexers, 'prowlarr', page) : null
}

/** qBittorrent 的 WebUI。 */
export function qbittorrentWeb(
  setup: Pick<QbittorrentSetup, 'origin' | 'base_url' | 'web_port'>,
  page?: Pick<Location, 'protocol' | 'hostname'>,
): string | null {
  return serviceWeb(setup, 'qbittorrent', page)
}
