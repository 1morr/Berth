import { useId, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'

import {
  deleteJob,
  deletionQueryOptions,
  NOTHING_TICKED,
  refusalOf,
  type DeleteScope,
  type DeletionEstimate,
} from '../api/jobs'
import { Checkbox, CONFIRM_ACTIONS, GhostButton, PrimaryButton } from '../components/controls'
import { ConfirmPanel } from '../components/ConfirmPanel'
import { useInPlaceConfirm } from '../components/useInPlaceConfirm'
import { formatSize } from '../media/searchResult'

/**
 * 刪除範圍：四個旗標、空間估算、二次確認（brief §9.2、M2 票 04）。
 *
 * **一個元件掛兩處**：`/jobs/:hash` 的動作區（M2 票 12 起；在那之前是 `/jobs` 的展開區）與 Media 詳情的
 * 版本清單（plan §7）——四個旗標的意思與它們的後果只能有一份說法。
 *
 * **就地展開，不是 dialog**（The Failure Expands In Place Rule）：對話框會蓋住使用者正在
 * 看的那一列，而「哪一筆正在被刪」正是這個動作最怕搞錯的事。展開的位置就在那一列裡面。
 *
 * **估算在展開的那一刻才問**（`deletionQueryOptions` 的 `enabled`）：它逐一 `stat` 每一個
 * 來源與目標，慢而準（brief §9.2）。等的時候畫面說得出自己正在做什麼，而**按鈕不鎖**
 * ——估算是給人參考的，不是刪除的前提；算不出來時仍然刪得下去。
 *
 * **四個旗標預設全不勾**（brief §9.2，2026-09-22 定）。Sonarr 的對話框預設勾「同時刪除
 * 檔案」，但這裡的刪除以 Job 為單位而不是作品，預設刪檔會誤刪還在做種的東西。
 */
export function JobDelete({ hash }: { hash: string }) {
  const { t, i18n } = useTranslation()
  const queryClient = useQueryClient()
  const { asked, open, close, trigger, panel, onKeyDown } = useInPlaceConfirm()
  const [scope, setScope] = useState<DeleteScope>(NOTHING_TICKED)
  const titleId = useId()

  const estimate = useQuery(deletionQueryOptions(hash, asked))
  const remove = useMutation({
    mutationFn: () => deleteJob(hash, scope),
    onSuccess: async () => {
      close()
      setScope(NOTHING_TICKED)
      // **兩個掛點各要重畫一次**：那一筆 Job（勾了「清除紀錄」詳情頁就變成「找不到這筆下載」，沒勾就換成
      // 「已刪除」），以及 Media 詳情——剛刪掉的那個版本與那幾個檔案都是 `['media', id]`
      // 讀出來的，只失效 `['jobs']` 的話版本清單上那一條會留在畫面上（票 04 code-review 抓到）。
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['jobs'] }),
        queryClient.invalidateQueries({ queryKey: ['media'] }),
      ])
    },
  })
  const refusal = refusalOf(remove.error)

  if (!asked) {
    return (
      <div className="grid justify-items-start gap-2">
        <GhostButton ref={trigger} type="button" onClick={open}>
          {t('jobs.delete.label')}
        </GhostButton>
        {/* 刪完了而這一筆還留著（沒勾「清除紀錄」）：它就在畫面上，所以只要一句結果。 */}
        {remove.isSuccess && (
          <p aria-live="polite" className="max-w-prose text-xs text-ink-dim">
            {done(t, i18n.language, remove.data)}
          </p>
        )}
      </div>
    )
  }

  return (
    <ConfirmPanel panelRef={panel} onKeyDown={onKeyDown} labelledBy={titleId}>
      <div className="grid gap-1">
        <p id={titleId} className="label text-ink">
          {t('jobs.delete.title')}
        </p>
        <p className="max-w-prose text-xs text-ink-dim">{t('jobs.delete.lede')}</p>
      </div>

      <div className="grid gap-3">
        <Checkbox
          label={t('jobs.delete.unlink')}
          hint={t('jobs.delete.unlinkHint')}
          checked={scope.unlink}
          onChange={(checked) => setScope({ ...scope, unlink: checked })}
        />
        <Checkbox
          label={t('jobs.delete.removeTorrent')}
          hint={t('jobs.delete.removeTorrentHint')}
          checked={scope.removeTorrent}
          onChange={(checked) =>
            // 取消「移除 torrent」時把「刪除檔案」一起收掉：留著一個送出去一定被 422 擋下來
            // 的勾，等於讓使用者按一顆註定失敗的按鈕（後端那一條在 `services/deletion.py`）。
            setScope({
              ...scope,
              removeTorrent: checked,
              deleteFiles: checked && scope.deleteFiles,
            })
          }
        />
        <Checkbox
          label={t('jobs.delete.deleteFiles')}
          // 鎖住的控制項要說得出為什麼（PRODUCT 原則 4），所以提示跟著換成解鎖的方法。
          hint={
            scope.removeTorrent
              ? t('jobs.delete.deleteFilesHint')
              : t('jobs.delete.deleteFilesLocked')
          }
          checked={scope.deleteFiles}
          disabled={!scope.removeTorrent}
          onChange={(checked) => setScope({ ...scope, deleteFiles: checked })}
        />
        <Checkbox
          label={t('jobs.delete.purge')}
          hint={t('jobs.delete.purgeHint')}
          checked={scope.purge}
          onChange={(checked) => setScope({ ...scope, purge: checked })}
        />
      </div>

      <Estimate estimate={estimate.data} pending={estimate.isPending} scope={scope} />

      <div className={CONFIRM_ACTIONS}>
        <PrimaryButton type="button" disabled={remove.isPending} onClick={() => remove.mutate()}>
          {remove.isPending ? t('jobs.delete.pending') : t('jobs.delete.confirm')}
        </PrimaryButton>
        <GhostButton
          type="button"
          onClick={() => {
            setScope(NOTHING_TICKED)
            close()
          }}
        >
          {t('common.cancel')}
        </GhostButton>
      </div>

      {remove.isError && (
        <p role="alert" className="max-w-prose text-xs text-blocked-ink">
          {refusal ? t(`jobs.refusal.${refusal.reason}`) : t('jobs.delete.off')}
        </p>
      )}
    </ConfirmPanel>
  )
}

/**
 * 「這樣刪會空出多少」。
 *
 * **它跟著勾選走**：只移除鏈接時一個位元組都不會回到磁碟，因為下載目錄裡那一份還在
 * （brief §9.2）。硬鏈接是同一份資料的兩個名字，最後一個名字消失時位元組才回來——所以
 * 這一段寧可多說一句，也不要讓使用者以為勾一個就能拿回一份空間。
 */
function Estimate({
  estimate,
  pending,
  scope,
}: {
  estimate: DeletionEstimate | undefined
  pending: boolean
  scope: DeleteScope
}) {
  const { t, i18n } = useTranslation()

  // 「正在算」是一句話而不是轉圈圈：它說得出正在量什麼，使用者才知道這個等待是值得的。
  if (pending) {
    return (
      <p aria-live="polite" className="max-w-prose text-xs text-ink-dim">
        {t('jobs.delete.estimate.pending')}
      </p>
    )
  }
  if (!estimate) {
    return <p className="max-w-prose text-xs text-ink-dim">{t('jobs.delete.estimate.off')}</p>
  }

  // 來源與所有鏈接都刪掉才算數。其中一邊沒勾就是 0，不是「一半」。
  const frees = scope.unlink && scope.deleteFiles ? estimate.reclaimable : 0
  const missing = estimate.links_missing + estimate.sources_missing

  return (
    <div aria-live="polite" className="grid gap-1 border-l-2 border-rule pl-3">
      <p className="value text-xs text-ink-dim">
        {[
          t('jobs.delete.estimate.links', { count: estimate.links }),
          t('jobs.delete.estimate.sources', { count: estimate.sources }),
        ].join(' · ')}
      </p>
      {missing > 0 && (
        <p className="text-xs text-ink-dim">
          {t('jobs.delete.estimate.missing', { count: missing })}
        </p>
      )}
      <p className="max-w-prose text-xs text-ink">
        {frees > 0
          ? t('jobs.delete.estimate.frees', { size: formatSize(frees, i18n.language) })
          : t('jobs.delete.estimate.freesNothing')}
      </p>
      {estimate.held > 0 && (
        <p className="max-w-prose text-xs text-ink-dim">
          {t('jobs.delete.estimate.held', { size: formatSize(estimate.held, i18n.language) })}
        </p>
      )}
    </div>
  )
}

/** 刪完那一句。說的是**真的**做掉了什麼——後端回的那一份，不是勾選的回聲。 */
function done(
  // `TFunction` 而不是 `useTranslation()['t']`：後者要把整棵鍵樹再展開一次，tsc 會報
  // 「型別展開太深」（同 `JobTimeline.tsx`）。
  t: TFunction,
  locale: string,
  outcome: { links: number; sources: number; freed: number },
): string {
  const counts = { links: outcome.links, sources: outcome.sources }
  return outcome.freed > 0
    ? t('jobs.delete.done', { ...counts, size: formatSize(outcome.freed, locale) })
    : t('jobs.delete.doneNothing', counts)
}
