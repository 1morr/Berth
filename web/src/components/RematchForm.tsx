import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useId, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'

import { rematch, rematchRefusalText, type RematchBody } from '../api/files'
import { reviewQueryOptions } from '../api/review'
import type { PlanAction } from '../api/plans'
import { ConfirmPanel } from './ConfirmPanel'
import { CONFIRM_ACTIONS, Field, GhostButton, Notice, PrimaryButton } from './controls'
import { useInPlaceConfirm } from './useInPlaceConfirm'

/** 修正得成的那三種（`domain.REMATCH_ACTIONS`）：指派到某一集、標記為特典、忽略。 */
type RematchAction = Extract<PlanAction, 'import' | 'extra' | 'skip'>

const CHOICES: readonly RematchAction[] = ['import', 'extra', 'skip']

/**
 * 修正一個檔案（brief §7.4、§9.4、M2 票 08）：`/review` 的對不到那一列與 Media 詳情的兩個入口
 * （Unmatched 區、檔案清單的一列）**用同一個表單、打同一支**（`POST /files/rematch`）。
 *
 * 改得成哪幾種是後端給的（`actions`，依檔案分類），前端不自己判斷；路徑也是後端算的，
 * 成功之後重問一次那一頁。
 *
 * **已入庫的檔案先就地確認**（PRODUCT 原則 2）：改指派會拆掉媒體庫裡現在那一條，標記特典與忽略
 * 會連旁邊的字幕一起拿掉——按之前說清楚。對不到的檔案不在媒體庫裡，沒有東西會被拿掉，直接套用。
 */
export function RematchForm({
  subject,
  actions,
  mediaKind,
  linked,
  initial,
  onCancel,
  onDone,
}: {
  /** 已入庫的帶 `ledger_id`，對不到的帶 `job_file_id`。 */
  subject: Pick<RematchBody, 'ledger_id'> | Pick<RematchBody, 'job_file_id'>
  actions: readonly PlanAction[]
  /** 劇集的指派要季集，電影的「指派」就是入庫。沒有作品時只剩忽略（後端給的 `actions`）。 */
  mediaKind: 'tv' | 'movie' | null
  /** 它現在在媒體庫裡嗎（決定要不要先確認）。 */
  linked: boolean
  initial?: { season: number | null; episode_start: number | null; episode_end: number | null }
  onCancel?: () => void
  onDone: (said: string) => void
}) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const selectId = useId()
  const refusalId = useId()
  const warningId = useId()
  const offered = CHOICES.filter((choice) => actions.includes(choice))
  const [action, setAction] = useState<RematchAction>(offered[0] ?? 'skip')
  const [season, setSeason] = useState(numberText(initial?.season ?? null))
  const [start, setStart] = useState(numberText(initial?.episode_start ?? null))
  const [end, setEnd] = useState(numberText(initial?.episode_end ?? null))
  const { asked, open, close, trigger, panel, onKeyDown } = useInPlaceConfirm()
  const numbered = action === 'import' && mediaKind === 'tv'

  const apply = useMutation({
    mutationFn: () =>
      rematch({
        ...subject,
        action,
        season: numbered ? numberOf(season) : null,
        episode_start: numbered ? numberOf(start) : null,
        episode_end: numbered ? numberOf(end) : null,
      }),
    onSuccess: () => {
      // 佇列那一列消失、Media 詳情的檔案清單與 Unmatched 區換了、下載列表的計數也變了。
      void queryClient.invalidateQueries({ queryKey: reviewQueryOptions().queryKey })
      void queryClient.invalidateQueries({ queryKey: ['media'] })
      void queryClient.invalidateQueries({ queryKey: ['jobs'] })
      onDone(t('rematch.done'))
    },
  })
  const refused = apply.isError ? rematchRefusalText(t, apply.error) : null
  const busy = apply.isPending

  function submit(event: FormEvent) {
    event.preventDefault()
    if (linked) open()
    else apply.mutate()
  }

  return (
    <form
      onSubmit={submit}
      aria-describedby={refused ? refusalId : undefined}
      className="grid min-w-0 gap-3 border-2 border-rule bg-hull px-3 py-3"
    >
      <div className="grid grid-cols-2 items-start gap-3 sm:grid-cols-4">
        <p className="col-span-2 grid gap-2 sm:col-span-1">
          <label htmlFor={selectId} className="label text-ink-dim">
            {t('rematch.field.action')}
          </label>
          <select
            id={selectId}
            value={action}
            onChange={(event) => setAction(event.target.value as RematchAction)}
            className="value w-full border-2 border-rule bg-hull px-3 py-2.5 text-sm text-ink focus:border-rule-strong"
          >
            {offered.map((choice) => (
              <option key={choice} value={choice}>
                {choice === 'import' && mediaKind === 'movie'
                  ? t('rematch.action.importMovie')
                  : t(`rematch.action.${choice}`)}
              </option>
            ))}
          </select>
        </p>
        {numbered && (
          <>
            <Field
              label={t('rematch.field.season')}
              type="number"
              inputMode="numeric"
              min={0}
              required
              value={season}
              onChange={(event) => setSeason(event.target.value)}
            />
            <Field
              label={t('rematch.field.start')}
              type="number"
              inputMode="numeric"
              min={0}
              required
              value={start}
              onChange={(event) => setStart(event.target.value)}
            />
            <Field
              label={t('rematch.field.end')}
              hint={t('rematch.endHint')}
              type="number"
              inputMode="numeric"
              min={0}
              value={end}
              onChange={(event) => setEnd(event.target.value)}
            />
          </>
        )}
      </div>

      {refused !== null && (
        <div id={refusalId}>
          <Notice signal="blocked" label={t('common.failed')}>
            {refused}
          </Notice>
        </div>
      )}

      {asked ? (
        <ConfirmPanel panelRef={panel} onKeyDown={onKeyDown} labelledBy={warningId}>
          <p id={warningId} className="max-w-prose text-xs text-ink">
            {t(CONSEQUENCE[action])}
          </p>
          <div className={CONFIRM_ACTIONS}>
            <PrimaryButton
              type="button"
              disabled={busy}
              onClick={() => {
                close()
                apply.mutate()
              }}
            >
              {busy ? t('rematch.working') : t('rematch.confirmAction')}
            </PrimaryButton>
            <GhostButton type="button" onClick={close}>
              {t('common.cancel')}
            </GhostButton>
          </div>
        </ConfirmPanel>
      ) : (
        <div className="flex flex-wrap gap-2">
          <GhostButton ref={trigger} type="submit" disabled={busy}>
            {busy ? t('rematch.working') : t('rematch.apply')}
          </GhostButton>
          {onCancel && (
            <GhostButton type="button" onClick={onCancel}>
              {t('rematch.cancel')}
            </GhostButton>
          )}
        </div>
      )}
    </form>
  )
}

/** 已入庫的檔案按下去會怎樣：改指派是搬、標記特典是搬到特典資料夾而字幕留不住、忽略是拿掉。 */
const CONSEQUENCE = {
  import: 'rematch.confirmMove',
  extra: 'rematch.confirmExtra',
  skip: 'rematch.confirmDrop',
} as const satisfies Record<RematchAction, string>

function numberText(value: number | null): string {
  return value === null ? '' : String(value)
}

function numberOf(text: string): number | null {
  return text.trim() === '' ? null : Number(text)
}
