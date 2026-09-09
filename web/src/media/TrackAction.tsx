import { useId, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { track, type Media } from '../api/media'
import { berthNumberOf } from '../components/berths'
import { PrimaryButton, STICKY_ACTION } from '../components/controls'
import { SetupHint } from '../components/SetupHint'
import { SIGNAL_FILL } from '../components/signal'

/**
 * 「選 Route → 追蹤」那一行（shape brief §6，使用者拍板一次做完）。
 *
 * 這一行是整頁的焦點時刻：按下去會把 `folder_name` **凍結**進資料庫，而那串字之後會
 * 真的出現在檔案系統上、改不掉（plan §5、brief §4.5）。所以資料夾名在**按之前**就顯示
 * 出來——動手前先給看（PRODUCT.md 原則 2）。
 *
 * 追蹤之後同一個下拉仍然可以改 Route：Route 不在凍結之列，媒體庫會搬，資料夾名不會。
 */
export function TrackAction({ media }: { media: Media }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const selectId = useId()
  // 下拉的值跟著資料走：`useState` 只取初值，refresh 或別處寫入之後它會停在舊的那一條
  // （票 04 code review）。`chosen` 是「使用者在這一輪動過的選擇」，沒動過就用資料的。
  const [chosen, setChosen] = useState<number | null | undefined>(undefined)
  const routeId = chosen === undefined ? media.default_route_id : chosen

  const save = useMutation({
    mutationFn: () => track(media.id, routeId),
    onSuccess: (updated) => {
      queryClient.setQueryData(['media', media.id], updated)
      // 牆上那一格的「已追蹤」是同一個事實，讓它重問一次。
      void queryClient.invalidateQueries({ queryKey: ['discover'] })
    },
  })

  return (
    <div className={`grid gap-3 ${STICKY_ACTION}`}>
      {media.routes.length > 0 ? (
        <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
          <p className="grid gap-2">
            <label htmlFor={selectId} className="label text-ink-dim">
              {t('media.route.label')}
            </label>
            <select
              id={selectId}
              value={routeId ?? ''}
              onChange={(event) =>
                setChosen(event.target.value === '' ? null : Number(event.target.value))
              }
              className="value w-full border-2 border-rule bg-hull px-3 py-2.5 text-sm text-ink focus:border-rule-strong"
            >
              <option value="">{t('media.route.none')}</option>
              {media.routes.map((route) => (
                <option key={route.id} value={route.id}>
                  {route.name}
                </option>
              ))}
            </select>
          </p>
          <span className="sm:w-56">
            <PrimaryButton type="button" onClick={() => save.mutate()}>
              {label()}
            </PrimaryButton>
          </span>
        </div>
      ) : (
        <NoRoutes kind={media.kind} />
      )}

      {/* 追蹤是整頁唯一會變的一行文字，看不見畫面的人得知道按下去發生了什麼。 */}
      <p aria-live="polite" className="flex flex-wrap items-center gap-x-3 gap-y-2">
        {media.tracked && (
          // 中性色塊：追蹤是一段關係，不是健康狀態（The Role Is Not A State Rule）。
          <span className={`label px-2 py-1.5 ${SIGNAL_FILL.neutral}`}>{t('media.tracked')}</span>
        )}
        <span className="min-w-0 text-sm text-ink-dim">
          {save.isError ? t('media.trackFailed') : t(media.tracked ? 'media.isTracked' : 'media.untracked')}
        </span>
      </p>
    </div>
  )

  function label() {
    if (save.isPending) return t('media.tracking')
    if (media.tracked) return t('media.retrack')
    return t('media.track')
  }
}

/**
 * 一條相符的 Route 都沒有：說得出下一步，而不是給一個空的下拉。
 *
 * 精靈跑完之後只有 admin 進得去（後端同時回 403），所以那條連結也只給 admin——
 * 對一般使用者它是死路，而他要的是「去叫管理員」（票 10 code-review 的同一條）。
 */
function NoRoutes({ kind }: { kind: Media['kind'] }) {
  const { t } = useTranslation()

  return (
    <div className="grid gap-3 border-2 border-rule bg-well px-3 py-3">
      <p className="max-w-prose text-sm text-ink">{t(`media.route.missing.${kind}`)}</p>
      {/* 泊位 4 是媒體庫路徑——Route 就是在那一步建的。 */}
      <SetupHint
        berth={berthNumberOf('library')}
        label={t('media.route.toSetup')}
        fallback={t('media.route.askAdmin')}
      />
    </div>
  )
}
