import { Chat, useChat } from '@ai-sdk/react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { isTextUIPart, isToolUIPart, type UIMessage } from 'ai'
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { useTranslation } from 'react-i18next'

import {
  agentRefusalOf,
  agentStatusQueryOptions,
  agentTransport,
  readConversation,
} from '../api/agent'
import { ApiError, signedOut } from '../api/client'
import { GhostButton, Notice, PrimaryButton, TEXT_LINK } from '../components/controls'
import { RequestFailed } from '../components/RequestFailed'
import i18n from '../i18n'
import { Markdown } from './Markdown'
import { PanelFailed, PanelLoading } from './PanelStates'
import { INPUT_ID, PANEL_TITLE_ID, usePanel } from './panelState'
import { ToolCall } from './ToolCall'
import { useNarrow } from './useNarrow'

/**
 * 一段對話：接回伺服器存著的那一份，之後由 `useChat` 串流（M5 票 12）。
 *
 * **`Chat` 放在查詢快取裡**（`staleTime` / `gcTime` 無限）：面板跟著每一頁的 `AppShell` 重掛，
 * 換頁時還在串流的那一輪要接得上，所以同一個 id 永遠拿回同一份 `Chat`，而不是重建一份。
 */
export function Conversation({ conversationId }: { conversationId: string }) {
  const chat = useQuery({
    queryKey: ['agent', 'chat', conversationId],
    queryFn: async ({ signal }) =>
      new Chat<UIMessage>({
        id: conversationId,
        messages: (await readConversation(conversationId, signal)) ?? [],
        transport: agentTransport(() => i18n.language),
      }),
    staleTime: Infinity,
    gcTime: Infinity,
    // `Chat` 是一個活的物件，不是資料：不要逐欄比對、合併它。
    structuralSharing: false,
  })

  if (chat.isPending) return <PanelLoading />
  if (chat.isError) return <PanelFailed error={chat.error} />
  return <Chatting chat={chat.data} />
}

/** 送不出去的那一則：後端說不行的理由，或請求本身為什麼沒成。 */
type Failure = { kind: 'busy' } | { kind: 'request'; error: unknown }

function Chatting({ chat }: { chat: Chat<UIMessage> }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { draft, setDraft, startNew, restarted } = usePanel()
  const { messages, sendMessage, status, stop, setMessages, clearError } = useChat({ chat })
  const [failure, setFailure] = useState<Failure | null>(null)
  const busy = status === 'submitted' || status === 'streaming'
  const input = useRef<HTMLTextAreaElement>(null)

  // 剛按「助理」打開時對話還在讀，焦點先落在面板標題（`AgentToggle`）；輸入欄出現了就接過來。
  // 只接標題上的：換頁時面板跟著重掛，不該把焦點從頁面上搶走。
  useEffect(() => {
    if (document.activeElement?.id === PANEL_TITLE_ID) input.current?.focus()
  }, [])

  async function submit() {
    const text = draft.trim()
    if (text === '' || busy) return
    setDraft('')
    setFailure(null)
    await sendMessage({ text })
    const error = chat.error
    if (error === undefined) return
    clearError()
    // 回應開始串流之後才斷的，伺服器已經收下這一則（它會存到停下之前）：留著。其餘的伺服器沒收，
    // 從畫面上拿掉、字放回輸入欄——重新載入之後它也不會在。
    const unsent = error instanceof ApiError || chat.lastMessage?.role === 'user'
    if (unsent) {
      setMessages((current) => withoutLastUser(current))
      setDraft(text)
    }
    const refusal = agentRefusalOf(error)
    if (refusal?.reason === 'conversation_missing') {
      startNew(true)
      return
    }
    if (refusal?.reason === 'ai_disabled' || signedOut(error)) {
      // 面板換成「AI 沒開」那一種；401 由問狀態的那一次重跑守衛、送回登入頁（`router.ts`）。
      await queryClient.refetchQueries({ queryKey: agentStatusQueryOptions.queryKey })
      return
    }
    setFailure(refusal?.reason === 'busy' ? { kind: 'busy' } : { kind: 'request', error })
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    void submit()
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // 組字中的 Enter 是選字，不是送出（中文、日文輸入法）。
    if (event.key !== 'Enter' || event.shiftKey || event.nativeEvent.isComposing) return
    event.preventDefault()
    void submit()
  }

  return (
    <>
      <Transcript messages={messages} busy={busy} restarted={restarted} />
      <form
        onSubmit={onSubmit}
        className="grid gap-2 border-t-2 border-rule px-4 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]"
      >
        {/* 一直掛著的 live region：送不出去的那一句（訊息被拿掉、字放回輸入欄）要念得到；跟著結果一起
            掛上去的 region 多數閱讀器不念（DESIGN.md 就地確認那一節）。 */}
        <div aria-live="polite" className="grid gap-2 empty:hidden">
          {failure?.kind === 'busy' ? (
            <Notice signal="assigned" label={t('agent.failure.waitLabel')}>
              {t('agent.failure.busy')}
            </Notice>
          ) : null}
          {failure?.kind === 'request' ? (
            <div className="grid gap-1">
              <RequestFailed error={failure.error} lead={t('agent.failure.lead')} />
              <p className="text-xs text-ink-dim">{t('agent.failure.restored')}</p>
            </div>
          ) : null}
        </div>
        <label htmlFor={INPUT_ID} className="sr-only">
          {t('agent.inputLabel')}
        </label>
        <textarea
          ref={input}
          id={INPUT_ID}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={onKeyDown}
          rows={2}
          aria-describedby={`${INPUT_ID}-hint`}
          className="value field-sizing-content max-h-36 min-h-16 w-full resize-none border-2 border-rule-strong bg-hull px-3 py-2.5 text-sm text-ink focus:border-ink"
        />
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <p id={`${INPUT_ID}-hint`} className="min-w-0 flex-1 text-xs text-ink-dim">
            {t('agent.inputHint')}
          </p>
          {/* 主要鍵的寬由外層限（DESIGN.md Buttons）；`grid` 讓 Ghost 也撐滿同一格，換鍵時不移位。 */}
          <div className="grid w-32">
            {busy ? (
              <GhostButton type="button" onClick={() => void stop()}>
                {t('agent.stop')}
              </GhostButton>
            ) : (
              <PrimaryButton type="submit">{t('agent.send')}</PrimaryButton>
            )}
          </div>
        </div>
      </form>
    </>
  )
}

function withoutLastUser(messages: UIMessage[]): UIMessage[] {
  const index = messages.findLastIndex((message) => message.role === 'user')
  return index === -1 ? messages : messages.slice(0, index)
}

/**
 * 對話紀錄。`role="log"`：新的一則接在最後；串流中 `aria-busy`，答完才念，不逐字念。
 * 一則回覆在重新載入之後會被拆成好幾則 UI 訊息（brief §20.24 第 7 點），連著的助理訊息只標一次「助理」。
 */
function Transcript({
  messages,
  busy,
  restarted,
}: {
  messages: UIMessage[]
  busy: boolean
  restarted: boolean
}) {
  const { t } = useTranslation()
  const log = useRef<HTMLDivElement>(null)
  const pinned = useRef(true)

  // 貼在底部時跟著新的字往下；使用者往上捲去看舊的，就不搶回來。
  useEffect(() => {
    const element = log.current
    if (element && pinned.current) element.scrollTop = element.scrollHeight
  })

  return (
    <div
      ref={log}
      role="log"
      aria-label={t('agent.title')}
      aria-busy={busy}
      onScroll={(event) => {
        const element = event.currentTarget
        pinned.current = element.scrollHeight - element.scrollTop - element.clientHeight < 48
      }}
      className="grid min-h-0 flex-1 content-start gap-4 overflow-y-auto overscroll-contain px-4 py-4"
    >
      {restarted && messages.length === 0 ? (
        <p className="text-sm text-ink">{t('agent.failure.missing')}</p>
      ) : null}
      {messages.length === 0 ? (
        <p className="max-w-prose text-sm text-ink">{t('agent.empty')}</p>
      ) : null}
      {messages.map((message, index) => (
        <Message
          key={message.id}
          message={message}
          continued={index > 0 && messages[index - 1].role === message.role}
          runId={lastOfItsRun(messages, index)}
        />
      ))}
    </div>
  )
}

/**
 * 這一則助理訊息是它那一輪的最後一則的話，那一輪的 id（M5 票 21）；否則 `null`。後端在每一則助理訊息的
 * `metadata.runId` 寫它是哪一輪的（串流時在開頭，重新載入時每一則都有）。重新載入之後一輪會拆成好幾則，
 * 「步驟」只掛在最後一則下面。
 */
function lastOfItsRun(messages: UIMessage[], index: number): string | null {
  const runId = runIdOf(messages[index])
  if (runId === null) return null
  const next = messages.at(index + 1)
  return next !== undefined && runIdOf(next) === runId ? null : runId
}

function runIdOf(message: UIMessage): string | null {
  if (message.role !== 'assistant') return null
  const metadata = message.metadata
  if (typeof metadata !== 'object' || metadata === null || !('runId' in metadata)) return null
  return typeof metadata.runId === 'string' ? metadata.runId : null
}

function Message({
  message,
  continued,
  runId,
}: {
  message: UIMessage
  continued: boolean
  runId: string | null
}) {
  const { t } = useTranslation()
  const narrow = useNarrow()
  const { setOpen } = usePanel()

  if (message.role === 'user') {
    const text = message.parts
      .filter(isTextUIPart)
      .map((part) => part.text)
      .join('')
    return (
      <div className="grid min-w-0 gap-1">
        {continued ? null : <span className="label text-ink-dim">{t('agent.you')}</span>}
        <p className="border-2 border-rule bg-deck px-3 py-2 text-sm whitespace-pre-wrap break-words text-ink">
          {text}
        </p>
      </div>
    )
  }
  if (message.role !== 'assistant') return null

  return (
    <div className="grid min-w-0 gap-2">
      {continued ? null : <span className="label text-ink-dim">{t('agent.assistant')}</span>}
      {message.parts.map((part, index) => {
        // 一則訊息裡的片段沒有自己的 id；位置就是它的身分（只會往後長，不會重排）。
        const key = `${message.id}:${index}`
        if (isTextUIPart(part)) return part.text ? <Markdown key={key} text={part.text} /> : null
        if (isToolUIPart(part)) return <ToolCall key={key} part={part} />
        return null
      })}
      {runId ? (
        <Link
          to="/agent/runs/$runId"
          params={{ runId }}
          aria-label={t('agent.stepsLabel')}
          // 窄版的面板蓋滿整個視窗：不收起來的話，換過去的那一頁看不到。
          onClick={() => {
            if (narrow) setOpen(false)
          }}
          className={`${TEXT_LINK} justify-self-start text-ink-dim`}
        >
          {t('agent.steps')}
        </Link>
      ) : null}
    </div>
  )
}
