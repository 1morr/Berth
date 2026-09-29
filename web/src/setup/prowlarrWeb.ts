import type { IndexerSetup } from '../api/setup'

/** compose 裡 Prowlarr 的服務名（`deploy/docker-compose.yml`，`tests/unit/test_deploy_names.py` 守著）。 */
const COMPOSE_HOST = 'prowlarr'

/**
 * 瀏覽器開 Prowlarr 介面的位址（M4 票 09）：要帳號的站要在它自己的介面加。
 *
 * - **套件內**：Berth 存的位址是 compose 內網的 `http://prowlarr:9696`，瀏覽器解不到那個名字（票 15 critique）。
 *   照 Jellyfin 深連結的做法（`services/deeplink.py`）：**瀏覽器現在的主機名** + 它在宿主上發佈的 port
 *   （`PROWLARR_PORT`，後端給）。
 * - **既有**：使用者自己填的位址。填的是 `host.docker.internal` 時那就是跑 Berth 的這台主機，換成瀏覽器的
 *   主機名；填的是 compose 主機名就給不出。
 *
 * 給不出就沒有連結，不給一條開不起來的。Torznab 端點沒有 Prowlarr 的介面。
 */
export function prowlarrWeb(
  indexers: Pick<IndexerSetup, 'origin' | 'kind' | 'base_url' | 'web_port'>,
  page: Pick<Location, 'protocol' | 'hostname'> = window.location,
): string | null {
  if (indexers.kind !== 'prowlarr') return null
  if (indexers.origin === 'bundled') {
    return indexers.web_port === null
      ? null
      : `${page.protocol}//${page.hostname}:${indexers.web_port}`
  }
  if (indexers.origin !== 'existing') return null
  let url: URL
  try {
    url = new URL(indexers.base_url)
  } catch {
    return null
  }
  if (url.hostname === COMPOSE_HOST) return null
  if (url.hostname === 'host.docker.internal') url.hostname = page.hostname
  return `${url.origin}${url.pathname}`.replace(/\/$/, '')
}
