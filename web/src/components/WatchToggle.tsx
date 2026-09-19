import { useId, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useRouter } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { ApiError } from '../api/client'
import { accessRefusal, markPlayed, type WatchState } from '../api/jellyfin'
import { ConfirmPanel } from './ConfirmPanel'
import { COMPACT_BUTTON, GhostButton, Notice, PrimaryButton } from './controls'
import { useInPlaceConfirm } from './useInPlaceConfirm'

/** 標記的是什麼：確認的文案說得出清掉的範圍（研究 §5）。 */
export type WatchTarget = 'series' | 'movie' | 'episode'

/**
 * 標為已看 / 未看，寫進這個人在 Jellyfin 的紀錄（媒體庫牆的卡片、Media 詳情的集與電影，M1.5 票 05、08）。
 *
 * **清掉的東西找不回來時先就地確認**（PRODUCT 原則 2）。jellyfin-web 兩個方向都不確認；Berth 不提供「復原」：
 *
 * - 標為未看：觀看次數與最後觀看時間清掉，劇集清的是每一集。
 * - 標為已看、而它看到一半：那個位置歸零（票 08 使用者拍板）。
 * - 標為已看一整部劇：每一集看到一半的位置都歸零，而劇集的觀看紀錄看不出底下有沒有這種集，所以一律確認。
 *
 * 寫入之後把回應交給 `onWritten`，由呼叫端就地改它那一份快取，不重抓整面牆或整季。
 *
 * **成功也要出聲**（票 11 的 audit，WCAG 2.1.3 Status Messages、PRODUCT 的無障礙那一節）：焦點這時
 * 已經回到這一顆鍵上，而它的名字剛剛換過——螢幕閱讀器不會為一個已經聚焦的元素重念新名字，所以
 * 成功那一句由旁邊的 `aria-live` 說。失敗那一半本來就有（`Notice signal="blocked"` 是 `role="alert"`）。
 */
export function WatchToggle({
  itemId,
  target,
  watch,
  describedBy,
  onWritten,
}: {
  itemId: string
  target: WatchTarget
  watch: WatchState
  /** 這一顆鍵屬於哪一格：牆與集卡上每一格都有同名的一顆，描述說是哪一部、哪一集（WCAG 2.4.6）。 */
  describedBy?: string
  onWritten: (written: WatchState) => void
}) {
  const { t } = useTranslation()
  const router = useRouter()
  const { asked, open, close, trigger, panel, onKeyDown } = useInPlaceConfirm()
  const warningId = useId()
  const [announced, setAnnounced] = useState('')
  const mark = useMutation({
    mutationFn: (played: boolean) => markPlayed(itemId, played),
    onSuccess: (written) => {
      setAnnounced(
        written.played ? t('inventory.watch.donePlayed') : t('inventory.watch.doneUnplayed'),
      )
      onWritten(written)
    },
    onError: (error) => {
      // 帳號在 Jellyfin 被停用：後端已經結束 session，重跑守衛把人送回登入頁（與牆那一支同一條路）。
      if (error instanceof ApiError && error.status === 401) void router.invalidate()
    },
  })
  const refusal = accessRefusal(mark.error)
  const next = !watch.played
  // 按下去會清掉什麼；什麼都不會清掉（沒進度的集或電影標為已看）時是 `null`，一按就送。
  const warning = watch.played
    ? t(UNPLAYED_WARNING[target])
    : watch.progress !== null
      ? t('inventory.watch.warningProgress', { progress: watch.progress })
      : target === 'series'
        ? t('inventory.watch.warningSeriesPlayed')
        : null

  return (
    <>
      {asked && warning ? (
        <div className="basis-full">
          <ConfirmPanel panelRef={panel} onKeyDown={onKeyDown} labelledBy={warningId}>
            <p id={warningId} className="text-xs text-ink">
              {warning}
            </p>
            {/* 卡片再寬也只有十幾 rem：兩顆鍵永遠疊成一欄。 */}
            <div className="grid gap-2">
              <PrimaryButton
                type="button"
                onClick={() => {
                  close()
                  mark.mutate(next)
                }}
              >
                {next ? t('inventory.watch.markPlayed') : t('inventory.watch.markUnplayed')}
              </PrimaryButton>
              <GhostButton type="button" onClick={close}>
                {t('common.cancel')}
              </GhostButton>
            </div>
          </ConfirmPanel>
        </div>
      ) : (
        <button
          ref={trigger}
          type="button"
          aria-describedby={describedBy}
          // 送出中不用 `disabled`：確認收起時焦點要回到這一顆，停用的鍵接不住焦點，鍵盤使用者會
          // 掉回 `body`（票 05 playwright 實跑抓到）。按鈕照常可按，這一下什麼都不做。
          aria-disabled={mark.isPending || undefined}
          onClick={() => {
            if (mark.isPending) return
            if (warning) open()
            else mark.mutate(next)
          }}
          className={COMPACT_BUTTON}
        >
          {mark.isPending
            ? t('inventory.watch.pending')
            : next
              ? t('inventory.watch.markPlayed')
              : t('inventory.watch.markUnplayed')}
        </button>
      )}
      <p aria-live="polite" className="sr-only">
        {announced}
      </p>
      {/* 失敗就在那一格說原因與下一步，Jellyfin 問不到時貼服務原文（PRODUCT 原則 4）。再按一次就是重試。 */}
      {mark.isError && refusal?.reason !== 'account_disabled' && (
        <div className="grid basis-full gap-1.5">
          <Notice signal="blocked" label={t('common.failed')}>
            {refusal?.reason === 'item_not_visible' || refusal?.reason === 'jellyfin_unreachable'
              ? t(`inventory.watch.refused.${refusal.reason}`)
              : t('inventory.watch.refused.other')}
          </Notice>
          {refusal?.reason === 'jellyfin_unreachable' && refusal.detail && (
            <p className="value text-xs wrap-anywhere text-ink-dim">{refusal.detail}</p>
          )}
        </div>
      )}
    </>
  )
}

/** 標為未看時清掉的範圍，照標的是什麼。 */
const UNPLAYED_WARNING = {
  series: 'inventory.watch.warningSeries',
  movie: 'inventory.watch.warningMovie',
  episode: 'inventory.watch.warningEpisode',
} as const satisfies Record<WatchTarget, string>
