import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import type { RouteView } from '../api/schemas'
import { GhostButton, Notice } from '../components/controls'
import { RouteIdentity } from '../components/RouteIdentity'
import { CheckTally } from '../components/RouteRow'
import { SettingsSection } from './SettingsFrame'
import type { useRecheckRoutes } from './recheckRoutes'

/** 「全部重新檢查」那一顆（M4 票 59）：Route 設定頁與健康頁共用，跑著的時候換成「全部重新檢查中…」。 */
export function RecheckAllButton({ recheck }: { recheck: ReturnType<typeof useRecheckRoutes> }) {
  const { t } = useTranslation()
  return (
    <GhostButton type="button" busy={recheck.isPending} onClick={() => recheck.mutate()}>
      {recheck.isPending ? t('routeSettings.recheckingAll') : t('routeSettings.recheckAll')}
    </GhostButton>
  )
}

/**
 * 換了一台 qBittorrent 之後自動跑的那一輪「全部重新檢查」（M4 票 59，審計 S4）：分類建在原本那一台，
 * 新的這一台要再建一次、探針要再問一次。跑著的時候說「正在重新檢查 N 條 Route」，逐條照頁 3 的樣子說
 * 跑到第幾條纜繩（`CheckTally`，呼叫端輪詢 `GET /routes`）；跑完說幾條過了，沒過的指去「媒體庫路徑」。
 *
 * 一條 Route 都沒有、或這一頁還沒換過台，什麼都不畫。
 */
export function RouteRecheck({
  recheck,
  routes,
}: {
  recheck: ReturnType<typeof useRecheckRoutes>
  /** 跑著時輪詢回來的那一份；跑完之後用命令自己回的那一份。 */
  routes: readonly RouteView[] | undefined
}) {
  const { t } = useTranslation()
  if (recheck.isIdle) return null
  const shown = recheck.data ?? routes ?? []
  if (shown.length === 0 && !recheck.isError) return null
  const passed = shown.filter((route) => route.health === 'ok').length
  // 沒過的含問不到結論的那幾條：「都接上新的這一台了」只在每一條都綠時說。
  const failed = shown.length - passed

  return (
    <SettingsSection
      id="qbittorrent-route-recheck"
      title={t('settings.qbittorrentPage.recheck.title')}
    >
      <div className="grid gap-3">
        <div aria-live="polite" className="grid gap-1 text-xs">
          {recheck.isPending && (
            <>
              <p className="text-ink">
                {t('settings.qbittorrentPage.recheck.running', { count: shown.length })}
              </p>
              <p className="max-w-prose text-ink-dim">
                {t('settings.qbittorrentPage.recheck.meanwhile')}
              </p>
            </>
          )}
          {recheck.isSuccess &&
            (failed > 0 ? (
              <p className="text-ink">
                {t('settings.qbittorrentPage.recheck.failed', { count: failed })}{' '}
                <Link to="/settings/routes" className="underline">
                  {t('routeSettings.link')}
                </Link>
              </p>
            ) : (
              <p className="text-ink">
                {t('settings.qbittorrentPage.recheck.passed', {
                  passed,
                  total: shown.length,
                })}
              </p>
            ))}
        </div>
        {recheck.isError && (
          <Notice signal="blocked" label={t('common.failed')}>
            {t('settings.qbittorrentPage.recheck.error', {
              recheckAll: t('routeSettings.recheckAll'),
            })}
          </Notice>
        )}
        {shown.length > 0 && (
          <ul aria-busy={recheck.isPending} className="grid gap-2">
            {shown.map((route) => (
              <li
                key={route.id}
                className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-2 border-2 border-rule bg-well px-4 py-3"
              >
                <RouteIdentity route={route} />
                <span className="grow" />
                <CheckTally route={route} />
              </li>
            ))}
          </ul>
        )}
      </div>
    </SettingsSection>
  )
}
