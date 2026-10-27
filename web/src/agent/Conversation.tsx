import { Chat, useChat } from '@ai-sdk/react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { isDataUIPart, isTextUIPart, isToolUIPart, type UIMessage } from 'ai'
import { Fragment, useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { useTranslation } from 'react-i18next'

import {
  agentRefusalOf,
  agentStatusQueryOptions,
  agentTransport,
  isSlashCommand,
  readConversation,
  runSlashCommand,
  slashMatches,
  type SlashName,
  type SlashResult,
} from '../api/agent'
import { ApiError, signedOut } from '../api/client'
import { GhostButton, Notice, PrimaryButton } from '../components/controls'
import { ExpandHint } from '../components/ExpandHint'
import { RequestFailed } from '../components/RequestFailed'
import i18n from '../i18n'
import { Markdown } from './Markdown'
import { PanelFailed, PanelLoading } from './PanelStates'
import { INPUT_ID, PANEL_TITLE_ID, SLASH_HINT_ID, slashOptionId, usePanel } from './panelState'
import { SlashHint, SlashOutput } from './Slash'
import { ToolCall } from './ToolCall'

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
type Failure =
  | { kind: 'busy' }
  | { kind: 'paused' }
  | { kind: 'unknown'; word: string }
  | { kind: 'request'; error: unknown }

/** 指令的結果與它接在第幾則訊息之後（打它的那一刻有幾則）。 */
interface Output {
  key: number
  after: number
  result: Exclude<SlashResult, { command: 'new' }>
}

function Chatting({ chat }: { chat: Chat<UIMessage> }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { draft, setDraft, startNew, restarted } = usePanel()
  const { messages, sendMessage, status, stop, setMessages, clearError } = useChat({ chat })
  const [failure, setFailure] = useState<Failure | null>(null)
  const [outputs, setOutputs] = useState<Output[]>([])
  const [running, setRunning] = useState(false)
  // 提示清單：上下鍵移到哪一列；按了 Esc 就收起，改字才再出現。
  const [active, setActive] = useState(0)
  const [hintClosed, setHintClosed] = useState(false)
  const streaming = status === 'submitted' || status === 'streaming'
  // 指令在跑時也不收新的一則，但沒有串流可以停。
  const busy = streaming || running
  const input = useRef<HTMLTextAreaElement>(null)
  const outputKey = useRef(0)
  const options = hintClosed ? [] : slashMatches(draft)
  const picked = options[Math.min(active, options.length - 1)]

  // 剛按「助理」打開時對話還在讀，焦點先落在面板標題（`AgentToggle`）；輸入欄出現了就接過來。
  // 只接標題上的：換頁時面板跟著重掛，不該把焦點從頁面上搶走。
  useEffect(() => {
    if (document.activeElement?.id === PANEL_TITLE_ID) input.current?.focus()
  }, [])

  function edit(next: string) {
    setDraft(next)
    setActive(0)
    setHintClosed(false)
  }

  async function submit(typed = draft) {
    const text = typed.trim()
    if (text === '' || busy) return
    setDraft('')
    setFailure(null)
    if (isSlashCommand(text)) {
      await command(text)
      return
    }
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
    await turnedDown(error)
  }

  /** 訊息或指令被擋下：換一段對話、換成「AI 沒開」，或在輸入欄上方說為什麼（字已經放回去了）。 */
  async function turnedDown(error: unknown) {
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
    if (refusal?.reason === 'busy') setFailure({ kind: 'busy' })
    else if (refusal?.reason === 'ai_paused') setFailure({ kind: 'paused' })
    else if (refusal?.reason === 'unknown_command')
      setFailure({ kind: 'unknown', word: refusal.detail })
    else setFailure({ kind: 'request', error })
  }

  /** 斜線指令：不經過模型（`services/slash.py`）。結果接在當下的對話後面，只在這個分頁。 */
  async function command(text: string) {
    setRunning(true)
    try {
      const result = await runSlashCommand(chat.id, text)
      if (result.command === 'new') {
        startNew()
        return
      }
      let after = messages.length
      if (result.command === 'compact' && result.after !== null) {
        // 伺服器換掉了歷史：接回壓縮後的那一份，舊的指令結果跟著不在了。
        const fresh = (await readConversation(chat.id)) ?? []
        setMessages(fresh)
        setOutputs([])
        after = fresh.length
      }
      const key = ++outputKey.current
      setOutputs((current) => [...current, { key, after, result }])
    } catch (error) {
      setDraft(text)
      await turnedDown(error)
    } finally {
      setRunning(false)
    }
  }

  function pick(name: SlashName) {
    void submit(`/${name}`)
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    void submit()
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // 組字中的按鍵是選字，不是送出或移動（中文、日文輸入法）。
    if (event.nativeEvent.isComposing) return
    if (picked !== undefined && onHintKey(event, picked)) {
      event.preventDefault()
      return
    }
    if (event.key !== 'Enter' || event.shiftKey) return
    event.preventDefault()
    void submit()
  }

  /**
   * 提示清單開著時的按鍵（APG combobox 的 listbox 彈出：焦點留在輸入欄）。處理了回 `true`。
   * 滑鼠點一列直接執行：那是看著說明選的。
   */
  function onHintKey(event: KeyboardEvent<HTMLTextAreaElement>, current: SlashName): boolean {
    const at = options.indexOf(current)
    switch (event.key) {
      case 'ArrowDown':
        setActive((at + 1) % options.length)
        return true
      case 'ArrowUp':
        setActive((at - 1 + options.length) % options.length)
        return true
      case 'Tab':
        if (event.shiftKey) return false
        edit(`/${current}`)
        return true
      case 'Enter':
        if (event.shiftKey) return false
        // 打到一半（`/c`）先補完、再按一次才執行：`/compact` 換掉的歷史回不來。
        if (draft === `/${current}`) pick(current)
        else edit(`/${current}`)
        return true
      case 'Escape':
        // 先收起清單；再按一次 Esc 才是收起面板（`AgentPanel` 看 `defaultPrevented`）。
        setHintClosed(true)
        return true
      default:
        return false
    }
  }

  return (
    <>
      <Transcript messages={messages} outputs={outputs} busy={streaming} restarted={restarted} />
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
          {failure?.kind === 'paused' ? (
            <Notice signal="assigned" label={t('agent.failure.waitLabel')}>
              {t('agent.failure.paused')}
            </Notice>
          ) : null}
          {failure?.kind === 'unknown' ? (
            <p className="text-sm text-ink">{t('agent.failure.unknown', { word: failure.word })}</p>
          ) : null}
          {failure?.kind === 'request' ? (
            <div className="grid gap-1">
              <RequestFailed error={failure.error} lead={t('agent.failure.lead')} />
              <p className="text-xs text-ink-dim">{t('agent.failure.restored')}</p>
            </div>
          ) : null}
        </div>
        {picked !== undefined ? (
          <SlashHint options={options} active={options.indexOf(picked)} onPick={pick} />
        ) : null}
        <label htmlFor={INPUT_ID} className="sr-only">
          {t('agent.inputLabel')}
        </label>
        <textarea
          ref={input}
          id={INPUT_ID}
          value={draft}
          onChange={(event) => edit(event.target.value)}
          onKeyDown={onKeyDown}
          rows={2}
          aria-describedby={`${INPUT_ID}-hint`}
          aria-autocomplete="list"
          aria-controls={picked !== undefined ? SLASH_HINT_ID : undefined}
          aria-activedescendant={picked !== undefined ? slashOptionId(picked) : undefined}
          className="value field-sizing-content max-h-36 min-h-16 w-full resize-none border-2 border-rule-strong bg-hull px-3 py-2.5 text-sm text-ink focus:border-ink"
        />
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <p id={`${INPUT_ID}-hint`} className="min-w-0 flex-1 text-xs text-ink-dim">
            {t('agent.inputHint')}
          </p>
          {/* 主要鍵的寬由外層限（DESIGN.md Buttons）；`grid` 讓 Ghost 也撐滿同一格，換鍵時不移位。 */}
          <div className="grid w-32">
            {streaming ? (
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
  outputs,
  busy,
  restarted,
}: {
  messages: UIMessage[]
  outputs: Output[]
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
      {outputsAfter(outputs, 0)}
      {messages.map((message, index) => (
        <Fragment key={message.id}>
          <Message
            message={message}
            continued={
              index > 0 &&
              messages[index - 1].role === message.role &&
              !outputs.some((output) => output.after === index)
            }
          />
          {outputsAfter(outputs, index + 1)}
        </Fragment>
      ))}
    </div>
  )
}

function outputsAfter(outputs: Output[], after: number) {
  return outputs
    .filter((output) => output.after === after)
    .map((output) => <SlashOutput key={`slash:${output.key}`} result={output.result} />)
}

function Message({ message, continued }: { message: UIMessage; continued: boolean }) {
  const { t } = useTranslation()

  if (message.role === 'user') {
    const text = message.parts
      .filter(isTextUIPart)
      .map((part) => part.text)
      .join('')
    // 壓縮的摘要跟著保留下來的第一則使用者訊息（`services/compaction.py`）；它不是你說的話。
    const summaries = message.parts.filter(isDataUIPart).flatMap(summaryOf)
    return (
      <>
        {summaries.map((summary, index) => (
          <Summary key={`${message.id}:summary:${index}`} text={summary} />
        ))}
        {text ? (
          <div className="grid min-w-0 gap-1">
            {continued && summaries.length === 0 ? null : (
              <span className="label text-ink-dim">{t('agent.you')}</span>
            )}
            <p className="border-2 border-rule bg-deck px-3 py-2 text-sm whitespace-pre-wrap break-words text-ink">
              {text}
            </p>
          </div>
        ) : null}
      </>
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
    </div>
  )
}

/** `data-compaction`（pydantic-ai 的 `compaction_payload`）的摘要字；別的資料片段不是摘要。 */
function summaryOf(part: { type: string; data: unknown }): string[] {
  if (part.type !== 'data-compaction') return []
  const content = (part.data as { content?: unknown } | null)?.content
  return typeof content === 'string' && content !== '' ? [content] : []
}

/** 較早的對話換成的那段摘要：收成一行，展開看全文（它是模型寫的，照 markdown 畫）。 */
function Summary({ text }: { text: string }) {
  const { t } = useTranslation()
  return (
    <details className="group min-w-0 border-2 border-rule bg-well">
      <summary className="flex cursor-pointer flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2 [&::-webkit-details-marker]:hidden">
        <span className="label text-ink-dim">{t('agent.summary.label')}</span>
        <span className="min-w-0 flex-1 text-sm text-ink">{t('agent.summary.title')}</span>
        <ExpandHint />
      </summary>
      <div className="border-t-2 border-rule bg-hull px-3 py-2">
        <Markdown text={text} />
      </div>
    </details>
  )
}
