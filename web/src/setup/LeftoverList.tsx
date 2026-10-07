import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { leftoversQueryOptions, removeEmptyCategories, type LeftoverKind } from '../api/setup'
import { GhostButton } from '../components/controls'
import { RequestFailed } from '../components/RequestFailed'
import { TechnicalDetails } from '../components/TechnicalDetails'

/**
 * 換 qBittorrent / Prowlarr 的確認框裡，Berth 在原本那一台留下的東西（M4 票 47，brief §19 D6）。
 *
 * 確認框打開時才問：後端讀的是存下的那一台，按下確認之後它就成了舊的。清單只有 Berth 擁有的物件
 * （`berth-*` 分類與裡面幾個 torrent、Berth 加的站、Berth 設的介面登入）。連不到時列 Berth 記得建過的，
 * 照實說確認不了現況。**能移除的只有空的 `berth-*` 分類**，站與登入只列出；連不到時沒有移除鍵。
 */
export function LeftoverList({ kind }: { kind: LeftoverKind }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const options = leftoversQueryOptions(kind)
  const leftovers = useQuery(options)
  const remove = useMutation({
    mutationFn: removeEmptyCategories,
    onSuccess: (after) => queryClient.setQueryData(options.queryKey, after),
  })

  if (leftovers.isError) {
    return <RequestFailed error={leftovers.error} lead={t('choice.leftovers.readFailed')} />
  }
  if (!leftovers.data) {
    return <p className="text-xs text-ink-dim">{t('choice.leftovers.reading')}</p>
  }

  const data = leftovers.data
  const empty = data.reachable ? data.categories.filter((row) => row.torrents === 0) : []
  const nothing = data.categories.length === 0 && data.sites.length === 0 && !data.login

  return (
    <section aria-labelledby={`leftovers-${kind}`} className="grid gap-2">
      <p id={`leftovers-${kind}`} className="max-w-prose text-xs text-ink">
        {nothing
          ? t(data.reachable ? 'choice.leftovers.none' : 'choice.leftovers.noneRemembered')
          : t(data.reachable ? 'choice.leftovers.heading' : 'choice.leftovers.remembered')}
      </p>
      {!nothing && (
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
        </ul>
      )}
      {!data.reachable && <TechnicalDetails lines={[data.base_url, data.error]} />}
      {kind === 'qbittorrent' && empty.length > 0 && (
        <div>
          <GhostButton type="button" busy={remove.isPending} onClick={() => remove.mutate()}>
            {t('choice.leftovers.removeEmpty', { count: empty.length })}
          </GhostButton>
        </div>
      )}
      {/* 結果由一直都在的宣告區說（WCAG 4.1.3）：移除之後那些分類從清單上消失，沒有別的地方說它發生了。 */}
      {kind === 'qbittorrent' && (
        <p role="status" className="text-xs text-ink-dim">
          {remove.isSuccess && data.reachable && empty.length === 0
            ? t('choice.leftovers.removed')
            : ''}
        </p>
      )}
      {remove.isError && (
        <RequestFailed error={remove.error} lead={t('choice.leftovers.removeFailed')} />
      )}
    </section>
  )
}
