import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { leftoversQueryOptions, type LeftoverKind } from '../api/setup'
import { Checkbox } from '../components/controls'
import { RequestFailed } from '../components/RequestFailed'
import { TechnicalDetails } from '../components/TechnicalDetails'

/**
 * 換 qBittorrent / Prowlarr 的確認框裡，Berth 在原本那一台留下的東西（M4 票 47，brief §19 D6）。
 *
 * 確認框打開時才問：後端讀的是存下的那一台，按下確認之後它就成了舊的。清單只有 Berth 擁有的物件
 * （`berth-*` 分類與裡面幾個 torrent、Berth 加的站、Berth 設的介面登入），加上套件內 qBittorrent
 * 預置的免密白名單——它不經 Berth 的 API、清單問不到，所以由呼叫端說那一台是不是套件內的。連不到時
 * 列 Berth 記得建過的，照實說確認不了現況。
 *
 * **分類裡的 torrent 會留在原本那一台做種**，Berth 換台之後不再追蹤（M4 票 65，審計 P1-4）。
 * **能移除的只有空的 `berth-*` 分類**，而且是勾選、不是按鈕：跟著確認換台一起送（`ServiceChoice`），
 * 取消就什麼都不動（審計 P2-9）。連不到時沒有勾選。
 */
export function LeftoverList({
  kind,
  bundled,
  removeEmpty,
  onRemoveEmpty,
}: {
  kind: LeftoverKind
  /** 原本那一台是套件內的：qBittorrent 多一列預置的免密白名單。 */
  bundled: boolean
  /** 換台時一併移除空的 `berth-*` 分類（只有 qBittorrent）。 */
  removeEmpty: boolean
  onRemoveEmpty: (remove: boolean) => void
}) {
  const { t } = useTranslation()
  const leftovers = useQuery(leftoversQueryOptions(kind))

  if (leftovers.isError) {
    return <RequestFailed error={leftovers.error} lead={t('choice.leftovers.readFailed')} />
  }
  if (!leftovers.data) {
    return <p className="text-xs text-ink-dim">{t('choice.leftovers.reading')}</p>
  }

  const data = leftovers.data
  const empty = data.reachable ? data.categories.filter((row) => row.torrents === 0) : []
  const seeding = data.categories.reduce((sum, row) => sum + (row.torrents ?? 0), 0)
  const allowlist = kind === 'qbittorrent' && bundled
  const nothing = data.categories.length === 0 && data.sites.length === 0 && !data.login
  const listed = !nothing || allowlist

  return (
    <section aria-labelledby={`leftovers-${kind}`} className="grid gap-2">
      <p id={`leftovers-${kind}`} className="max-w-prose text-xs text-ink">
        {!listed
          ? t(data.reachable ? 'choice.leftovers.none' : 'choice.leftovers.noneRemembered')
          : t(data.reachable ? 'choice.leftovers.heading' : 'choice.leftovers.remembered')}
      </p>
      {listed && (
        <ul className="grid gap-1 text-xs text-ink">
          {data.categories.map((row) => (
            <li key={row.name} className="flex flex-wrap gap-x-2">
              <span>{t('choice.leftovers.category')}</span>
              <span className="value">{row.name}</span>
              {row.torrents !== null && (
                <span className="text-ink-dim">
                  {row.torrents === 0
                    ? t('choice.leftovers.empty')
                    : t('choice.leftovers.torrents', { count: row.torrents })}
                </span>
              )}
            </li>
          ))}
          {data.sites.length > 0 && (
            <li className="flex flex-wrap gap-x-2">
              <span>{t('choice.leftovers.sites')}</span>
              <span className="value">{data.sites.join(t('choice.leftovers.separator'))}</span>
            </li>
          )}
          {data.login && (
            <li className="flex flex-wrap gap-x-2">
              <span>{t('choice.leftovers.login')}</span>
              <span className="value">{data.login}</span>
            </li>
          )}
          {allowlist && (
            <li className="grid gap-1">
              <span className="flex flex-wrap gap-x-2">
                <span>{t('choice.leftovers.allowlist')}</span>
                <span className="text-ink-dim">{t('choice.leftovers.allowlistValue')}</span>
              </span>
              <span className="max-w-prose text-ink-dim">{t('choice.leftovers.allowlistHow')}</span>
            </li>
          )}
        </ul>
      )}
      {/* 連得到時照數目說；連不到時數不出來，但分類還在就照樣說它們會留著。 */}
      {data.reachable
        ? seeding > 0 && (
            <p className="max-w-prose text-xs text-ink">
              {t('choice.leftovers.seeding', { count: seeding })}
            </p>
          )
        : kind === 'qbittorrent' &&
          data.categories.length > 0 && (
            <p className="max-w-prose text-xs text-ink">{t('choice.leftovers.seedingUnknown')}</p>
          )}
      {!data.reachable && <TechnicalDetails lines={[data.base_url, data.error]} />}
      {kind === 'qbittorrent' && empty.length > 0 && (
        <Checkbox
          label={t('choice.leftovers.removeEmpty', { count: empty.length })}
          hint={t('choice.leftovers.removeEmptyHint')}
          checked={removeEmpty}
          onChange={onRemoveEmpty}
        />
      )}
    </section>
  )
}
