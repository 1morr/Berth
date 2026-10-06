import { useTranslation } from 'react-i18next'

import type { JellyfinWeb } from '../api/jellyfin'
import type { QbittorrentSetup } from '../api/schemas'
import type { IndexerSetup } from '../api/setup'
import { jellyfinBase } from '../inventory/jellyfinLink'
import { jellyfinWeb, prowlarrWeb, qbittorrentWeb } from './serviceWeb'

interface Door {
  name: string
  url: string | null
  login: string
}

/**
 * 完成頁的「各服務自己的介面」（M4 票 31，實測 #45）：開在哪、拿什麼登入。精靈全程不必打開它們
 * （PRODUCT 原則 1），但跑完之後要看下載細節、在 Prowlarr 加私站時，人要知道門在哪、鑰匙是哪一把。
 *
 * 網址照各自的推導（`jellyfinBase`、`serviceWeb`）：給不出就說給不出，不給一條開不起來的連結。
 * 跳過時沒有 Prowlarr 那一列。
 */
export function ServiceDoors({
  owner,
  jellyfin,
  qbittorrent,
  indexers,
}: {
  owner: string
  jellyfin: JellyfinWeb | undefined
  qbittorrent: QbittorrentSetup | undefined
  indexers: IndexerSetup | undefined
}) {
  const { t } = useTranslation()
  const doors: Door[] = [
    {
      name: 'Jellyfin',
      // 深連結那一份推導給的是使用者填的位址（`deeplink.py` 第 2 條）；填的是 `host.docker.internal`
      // 時瀏覽器開不了，照 `serviceWeb` 同一條換成這台主機（實跑 E6 抓到）。
      url: jellyfinDoor(jellyfin),
      login: t('complete.doors.jellyfin', { name: owner }),
    },
  ]
  if (qbittorrent) {
    doors.push({
      name: 'qBittorrent',
      url: qbittorrentWeb(qbittorrent),
      login:
        qbittorrent.origin === 'bundled' && qbittorrent.web_ui_username
          ? t('complete.doors.bundledLogin', { name: qbittorrent.web_ui_username })
          : t('complete.doors.yours'),
    })
  }
  if (indexers && indexers.origin !== null) {
    doors.push({
      name: 'Prowlarr',
      url: prowlarrWeb(indexers),
      login:
        indexers.origin === 'bundled' && indexers.web_ui_username
          ? t('complete.doors.bundledLogin', { name: indexers.web_ui_username })
          : t('complete.doors.yours'),
    })
  }

  return (
    <section aria-labelledby="service-doors" className="mt-6 grid gap-3">
      <h3 id="service-doors" className="label text-ink-dim">
        {t('complete.doors.title')}
      </h3>
      <p className="max-w-prose text-xs text-ink-dim">{t('complete.doors.lede')}</p>
      <dl className="grid gap-x-4 gap-y-2 border-2 border-rule bg-well px-4 py-3 sm:grid-cols-[auto_minmax(0,1fr)]">
        {doors.map((door) => (
          <div key={door.name} className="contents">
            <dt className="value self-baseline text-sm font-semibold text-ink">{door.name}</dt>
            <dd className="min-w-0 text-xs text-ink">
              {door.url ? (
                <a
                  href={door.url}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="value wrap-anywhere underline underline-offset-2 hover:text-ink-dim"
                >
                  {door.url}
                </a>
              ) : (
                <span className="text-ink-dim">{t('complete.doors.noLink')}</span>
              )}
              <span className="mt-1 block text-ink-dim">{door.login}</span>
            </dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

function jellyfinDoor(jellyfin: JellyfinWeb | undefined): string | null {
  const base = jellyfin ? jellyfinBase(jellyfin, window.location) : null
  return base ? jellyfinWeb(base) : null
}
