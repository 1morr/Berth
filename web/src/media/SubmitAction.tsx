import { useEffect, useId, useRef } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import type { Media } from '../api/media'
import { refusalOf, submitJob } from '../api/jobs'
import type { SearchResult } from '../api/search'
import { GhostButton, PrimaryButton } from '../components/controls'
import { SIGNAL_FILL } from '../components/signal'
import { ConfirmPanel } from '../components/ConfirmPanel'
import { useInPlaceConfirm } from '../components/useInPlaceConfirm'

/**
 * 結果表一列上的送單（票 09、`.scratch/m1/search-results-shape.md` §4 留的位置）。
 *
 * **確認就地展開，而且那段確認裡印著資料夾名**（票 04b、plan §5、brief §4.5）。
 * 那是這個系統唯一一個定了就改不掉的字串：送單成功那一刻它寫死進 `media.folder_name`，
 * 之後 TMDB 改標題也不會動它。所以它必須在**按下去之前**出現在畫面上，而且要說清楚
 * 這一按就定了（PRODUCT 原則 2：動手前先給看）。
 *
 * 已經凍結過的作品第二次送單不重凍，那時這段話換成「它已經是」。
 *
 * 送單本身**不是二選一的成功／失敗**：qBittorrent 收不下時 Job 仍然建好了
 * （`submit_failed` 加原文，plan §3.1），所以成功的畫面是一條「去看下載列表」的連結，
 * 而不是一句「已送出」。
 *
 * **確認裡重述送到哪一條 Route**：選 Route 的下拉在表格上面，按下這一列的送單時它早就捲出
 * 畫面了，而 Route 與資料夾名一起決定了檔案落在哪裡（票 15 的 critique）。
 */
export function SubmitAction({
  media,
  row,
  route,
}: {
  media: Media
  row: SearchResult
  /** 這一輪選的 Route。`null` = 還沒選——那是送不出去的，而說不行的是那個下拉。 */
  route: number | null
}) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { asked, open, close, trigger, panel, onKeyDown } = useInPlaceConfirm()
  const toJobs = useRef<HTMLAnchorElement>(null)
  const confirmId = useId()
  const destination = media.routes.find((choice) => choice.id === route)

  const submit = useMutation({
    mutationFn: () => {
      // 沒選 Route 就**不打 API**：送一個假的 route id 出去會換回一句「那條 Route 不在了」，
      // 而使用者根本還沒選過。說不行的是上面那句話（票 02b：按鈕永遠按得下去）。
      if (route === null) throw new NoRouteError()
      return submitJob({
        // `info_hash` 用它自己那一格，不是 `key`——`key` 是「這一列的身分」（info hash
        // **或** guid），不報 hash 的站那一格是一條網址。
        source: { url: row.download_url, title: row.title, info_hash: row.info_hash },
        media: media.id,
        route,
      })
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['jobs'] }),
        // 送單成功之後這部作品變成 tracked，資料夾名也定了——詳情頁那兩格要跟著換。
        queryClient.invalidateQueries({ queryKey: ['media', media.id] }),
      ])
    },
  })

  // 送出之後確認區塊整個換掉，焦點不能跟著它消失：落在接下來最可能要按的那一條連結上。
  useEffect(() => {
    if (submit.isSuccess) toJobs.current?.focus()
  }, [submit.isSuccess])

  if (submit.isSuccess) {
    return (
      <p role="status" className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <span className={`label px-2 py-1.5 ${SIGNAL_FILL.secured}`}>
          {submit.data.created ? t('submit.done') : t('submit.already')}
        </span>
        <Link
          ref={toJobs}
          to="/jobs"
          className="text-xs underline decoration-rule-strong underline-offset-4 hover:decoration-ink"
        >
          {t('submit.toJobs')}
        </Link>
      </p>
    )
  }

  if (!asked) {
    return (
      <GhostButton ref={trigger} type="button" onClick={open}>
        {t('submit.start')}
      </GhostButton>
    )
  }

  return (
    <ConfirmPanel panelRef={panel} onKeyDown={onKeyDown} labelledBy={confirmId}>
      <div className="grid gap-1">
        {destination && (
          <p className="max-w-prose text-xs break-words text-ink">
            {t('submit.destination', { route: destination.name })}
          </p>
        )}
        <p id={confirmId} className="max-w-prose text-xs text-ink">
          {route === null ? t('submit.needRoute') : t('submit.confirm')}
        </p>
        {/* 資料夾名是機器字串——它會原樣出現在檔案系統上，所以走 `.value`。 */}
        <p className="value text-xs wrap-anywhere text-ink">{media.folder_name || '—'}</p>
        <p className="max-w-prose text-xs text-ink-dim">
          {media.folder_frozen ? t('submit.alreadyFrozen') : t('submit.willFreeze')}
        </p>
      </div>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-[minmax(0,14rem)_auto] sm:items-center">
        {/* 按鈕永遠按得下去（票 02b）：沒選 Route 時說不行的是上面那句話與下拉本身。 */}
        <PrimaryButton type="button" onClick={() => submit.mutate()}>
          {submit.isPending ? t('submit.submitting') : t('submit.submit')}
        </PrimaryButton>
        <GhostButton type="button" onClick={close}>
          {t('common.cancel')}
        </GhostButton>
      </div>

      {/* 「先選一條 Route」在選了之後就不成立了——留著它會與上面那句正常的確認互相矛盾。 */}
      {submit.isError && !(submit.error instanceof NoRouteError && route !== null) && (
        <Refusal error={submit.error} />
      )}
    </ConfirmPanel>
  )
}

/** 還沒選 Route。它不是後端的拒絕，所以不走 `JobRefusal` 那一套。 */
class NoRouteError extends Error {}

/**
 * 被擋下來的理由。
 *
 * 八種各有各的下一步（PRODUCT 原則 4）——「這條 Route 是紅的」要人去健康頁，
 * 「索引站給不出這份 torrent」只能換一列再試。認不得的理由落回一句誠實的通用訊息，
 * 而不是一條 i18n key。
 */
function Refusal({ error }: { error: unknown }) {
  const { t } = useTranslation()
  const refusal = refusalOf(error)

  return (
    <div role="alert" className="grid gap-1">
      <p className="max-w-prose text-xs text-blocked-ink">
        {error instanceof NoRouteError
          ? t('submit.needRouteError')
          : refusal
            ? t(`jobs.refusal.${refusal.reason}`)
            : t('submit.off')}
      </p>
      {/* 服務回的原文，不翻譯（與精靈的纜繩同一個規矩）。 */}
      {refusal?.detail && (
        <p className="value text-xs wrap-anywhere text-ink-dim">{refusal.detail}</p>
      )}
    </div>
  )
}
