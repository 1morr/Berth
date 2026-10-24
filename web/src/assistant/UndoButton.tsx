import { useContext, useId, useState } from 'react'
import { useMutation, useQueryClient, type QueryKey } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { undoRefusalOf, undoToolCall, type ToolResults } from '../api/assistant'
import { ConfirmPanel } from '../components/ConfirmPanel'
import { CONFIRM_ACTIONS, GhostButton, PrimaryButton } from '../components/controls'
import { RequestFailed } from '../components/RequestFailed'
import { useInPlaceConfirm } from '../components/useInPlaceConfirm'
import { ProposalsContext } from './proposals'
import { reasonText } from './refusals'
import { ToolCallContext } from './toolCall'

/**
 * 撤銷的核心（M5 票 11、14）：走那個工具的命令標著的反向命令，**經過那則對話**（`POST /conversations/{id}/
 * messages/{message}/tools/{call}/undo`）——撤掉之後對話多一則，模型下一輪知道、卡片照它說已撤銷。
 * 不依賴面板的 context：面板的結果卡（`UndoButton`）與 AI 活動頁的列各自給位址。呼叫端自己決定
 * 按不按得到（後端說的 `undoable`、還沒撤銷過）。
 *
 * 就地確認，`confirm` 說清楚會撤掉什麼。撤銷被拒（qBittorrent 連不上）時什麼都沒記，說原因、再按一次會接著做。
 */
/** 撤回 Job 被拒時（qBittorrent 連不上、已經下載完）：Job 頁同一句（`jobs.refusal.*`）。 */
const JOB_REASONS = {
  client_unreachable: 'jobs.refusal.client_unreachable',
  not_undoable: 'jobs.refusal.not_undoable',
  moved_on: 'jobs.refusal.moved_on',
  job_missing: 'jobs.refusal.job_missing',
} as const

export function UndoControl({
  conversationId,
  messageId,
  callId,
  label,
  confirm,
  invalidate = [],
  busy = false,
  onUndone,
}: {
  conversationId: number
  messageId: number
  callId: string
  label: string
  confirm: string
  /** 撤掉之後要重問的查詢（Job、RSS、作品頁的季表）。 */
  invalidate?: QueryKey[]
  /** 面板的回覆還在跑：鍵先停著，等它講完（後端那時回 `busy`）。 */
  busy?: boolean
  /** 撤掉之後、查詢重問之外要做的事（面板重讀這則對話）。 */
  onUndone?: () => Promise<void> | void
}) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { asked, open, close, trigger, panel, onKeyDown } = useInPlaceConfirm()
  const titleId = useId()
  const [refused, setRefused] = useState('')
  const undo = useMutation({
    mutationFn: () => undoToolCall(conversationId, messageId, callId),
    onSuccess: async (part) => {
      if (part.result_type === 'Refusal') {
        const refusal = part.result as ToolResults['Refusal']
        setRefused(
          Object.hasOwn(JOB_REASONS, refusal.reason)
            ? t(JOB_REASONS[refusal.reason as keyof typeof JOB_REASONS])
            : reasonText(t, refusal.reason, refusal.detail),
        )
        return
      }
      setRefused('')
      close()
      await Promise.all([
        ...invalidate.map((queryKey) => queryClient.invalidateQueries({ queryKey })),
        onUndone?.(),
      ])
    },
  })
  const refusal = undoRefusalOf(undo.error)

  if (!asked) {
    return (
      <div>
        <GhostButton ref={trigger} type="button" onClick={open}>
          {label}
        </GhostButton>
      </div>
    )
  }

  return (
    <ConfirmPanel panelRef={panel} onKeyDown={onKeyDown} labelledBy={titleId}>
      <p id={titleId} className="max-w-prose text-xs text-ink">
        {confirm}
      </p>
      <div className={CONFIRM_ACTIONS}>
        <PrimaryButton type="button" busy={undo.isPending || busy} onClick={() => undo.mutate()}>
          {undo.isPending ? t('assistant.undo.undoing') : label}
        </PrimaryButton>
        <GhostButton type="button" onClick={close}>
          {t('common.cancel')}
        </GhostButton>
      </div>
      {busy && <p className="text-xs text-ink-dim">{t('assistant.undo.wait')}</p>}
      {refused && (
        <p role="alert" className="max-w-prose text-xs text-blocked-ink">
          {/* 接在句子中間：理由自己的句號拿掉，免得疊兩個。 */}
          {t('assistant.undo.refused', { reason: refused.replace(/[。.]$/u, '') })}
        </p>
      )}
      {undo.isError &&
        (refusal ? (
          <p role="alert" className="max-w-prose text-xs text-blocked-ink">
            {t(`assistant.undo.refusal.${refusal.reason}`)}
          </p>
        ) : (
          <RequestFailed error={undo.error} lead={t('assistant.undo.failed')} />
        ))}
    </ConfirmPanel>
  )
}

/**
 * 結果卡上的撤銷（M5 票 11）：位址讀面板的 context。只在這個人按得到（後端說的 `undoable`）、還沒撤銷過時給；
 * 還在串流、結果還沒存下來時不給。
 */
export function UndoButton({
  label,
  confirm,
  invalidate = [],
}: {
  label: string
  confirm: string
  /** 撤掉之後要重問的查詢（Job、RSS、作品頁的季表）。對話本身一律重讀。 */
  invalidate?: QueryKey[]
}) {
  const { conversationId, replying, refresh } = useContext(ProposalsContext)
  const { callId, messageId, undoable, undone } = useContext(ToolCallContext)

  if (!undoable || undone !== null || conversationId === null || messageId === null) return null

  return (
    <UndoControl
      conversationId={conversationId}
      messageId={messageId}
      callId={callId}
      label={label}
      confirm={confirm}
      invalidate={invalidate}
      busy={replying}
      onUndone={refresh}
    />
  )
}
