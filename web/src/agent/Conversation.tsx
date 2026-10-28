import { Chat, useChat } from '@ai-sdk/react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import {
  isDataUIPart,
  isTextUIPart,
  isToolUIPart,
  lastAssistantMessageIsCompleteWithApprovalResponses,
  type DynamicToolUIPart,
  type ToolUIPart,
  type UIMessage,
} from 'ai'
import {
  Fragment,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from 'react'
import { useTranslation } from 'react-i18next'

import {
  agentRefusalOf,
  agentStatusQueryOptions,
  agentTransport,
  isSlashCommand,
  readConversation,
  runSlashCommand,
  slashMatches,
  stopOf,
  stopTurn,
  type ResumeMetadata,
  type SlashName,
  type SlashResult,
  type TurnStop,
} from '../api/agent'
import { ApiError, signedOut } from '../api/client'
import { proposalsKey, proposalsQueryOptions, type Proposal } from '../api/proposals'
import { GhostButton, Notice, PrimaryButton, TEXT_LINK } from '../components/controls'
import { ExpandHint } from '../components/ExpandHint'
import { RequestFailed } from '../components/RequestFailed'
import i18n from '../i18n'
import { CardContext, type CardActions } from './cards'
import { ConfirmCard } from './ConfirmCard'
import { Markdown } from './Markdown'
import { PanelFailed, PanelLoading } from './PanelStates'
import {
  INPUT_ID,
  PANEL_TITLE_ID,
  SLASH_HINT_ID,
  slashOptionId,
  useLeavePanel,
  usePanel,
} from './panelState'
import { SlashHint, SlashOutput } from './Slash'
import { ToolCall } from './ToolCall'

/**
 * 一段對話：接回伺服器存著的那一份，之後由 `useChat` 串流（M5 票 12）。
 *
 * **`Chat` 放在查詢快取裡**（`staleTime` / `gcTime` 無限）：面板跟著每一頁的 `AppShell` 重掛，
 * 換頁時還在串流的那一輪要接得上，所以同一個 id 永遠拿回同一份 `Chat`，而不是重建一份。
 *
 * **重新整理、關掉分頁再回來**（M5 票 25）：那一輪在伺服器上照跑。讀到的對話說它還在跑，就重連它的串流
 * 接著畫（`follow`）。
 */
export function Conversation({ conversationId }: { conversationId: string }) {
  const chat = useQuery({
    queryKey: ['agent', 'chat', conversationId],
    queryFn: async ({ signal }) => {
      const stored = await readConversation(conversationId, signal)
      const created = new Chat<UIMessage>({
        id: conversationId,
        messages: stored?.messages ?? [],
        transport: agentTransport(() => i18n.language),
      })
      if (stored?.running) void follow(created, stored.running)
      return created
    },
    staleTime: Infinity,
    gcTime: Infinity,
    // `Chat` 是一個活的物件，不是資料：不要逐欄比對、合併它。
    structuralSharing: false,
  })

  if (chat.isPending) return <PanelLoading />
  if (chat.isError) return <PanelFailed error={chat.error} />
  return <Chatting chat={chat.data} />
}

/**
 * 接上伺服器上正在跑的那一輪：重連它的串流（從頭重播、跟到答完），答完再讀一次存著的那一份——重連與讀對話
 * 之間它剛好跑完的話，串流是 204，畫面要從歷史補上。這段時間使用者又送了一則的話不蓋掉。
 */
async function follow(chat: Chat<UIMessage>, turn: string) {
  await chat.resumeStream({ metadata: { turn } satisfies ResumeMetadata })
  if (chat.status !== 'ready') return
  const before = chat.lastMessage?.id
  const fresh = await readConversation(chat.id).catch(() => null)
  if (fresh === null || chat.status !== 'ready' || chat.lastMessage?.id !== before) return
  chat.messages = fresh.messages
  // 另一個分頁在這之間又開了一輪：接著跟。
  if (fresh.running !== null && fresh.running !== turn) await follow(chat, fresh.running)
}

/**
 * 送不出去的那一則：後端說不行的理由，或請求本身為什麼沒成。`restored`：打的字放回輸入欄了
 * （按「繼續」與按卡片之後的恢復沒有字可放）。
 */
type Failure = { restored: boolean } & (
  | { kind: 'busy' }
  | { kind: 'paused' }
  | { kind: 'unknown'; word: string }
  | { kind: 'spent' }
  | { kind: 'request'; error: unknown }
)

/** 指令的結果與它接在第幾則訊息之後（打它的那一刻有幾則）。 */
interface Output {
  key: number
  after: number
  result: Exclude<SlashResult, { command: 'new' }>
}

function Chatting({ chat }: { chat: Chat<UIMessage> }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { draft, setDraft, startNew, restarted, conversationId } = usePanel()
  const { messages, sendMessage, status, stop, setMessages, clearError } = useChat({ chat })
  const [failure, setFailure] = useState<Failure | null>(null)
  const [outputs, setOutputs] = useState<Output[]>([])
  const [running, setRunning] = useState(false)
  // 按過「繼續」、伺服器說不能續的那幾輪：收掉按鈕。
  const [spent, setSpent] = useState<ReadonlySet<string>>(new Set())
  // 提示清單：上下鍵移到哪一列；按了 Esc 就收起，改字才再出現。
  const [active, setActive] = useState(0)
  const [hintClosed, setHintClosed] = useState(false)
  const streaming = status === 'submitted' || status === 'streaming'
  // 指令在跑時也不收新的一則，但沒有串流可以停。
  const busy = streaming || running
  const input = useRef<HTMLTextAreaElement>(null)
  // 「送出」與「停止」輪流佔同一格：焦點在那一格裡時，換鍵之後交給新的那一顆（WCAG 2.4.3）。
  const action = useRef<HTMLDivElement>(null)
  const actionFocused = useRef(false)
  const outputKey = useRef(0)
  const options = hintClosed ? [] : slashMatches(draft)
  const picked = options[Math.min(active, options.length - 1)]

  // 一輪答完（或停在卡片上）就再問一次這段對話的卡片：新出的卡要畫上去。狀態也再問：這一輪的
  // 失敗可能讓 provider 暫停了，花費提醒也可能變了。
  useEffect(() => {
    if (status === 'ready' || status === 'error') {
      void queryClient.invalidateQueries({ queryKey: proposalsKey(conversationId) })
      void queryClient.invalidateQueries({ queryKey: agentStatusQueryOptions.queryKey })
    }
  }, [status, queryClient, conversationId])

  useLayoutEffect(() => {
    if (actionFocused.current && !action.current?.contains(document.activeElement)) {
      action.current?.querySelector('button')?.focus()
    }
  }, [streaming])

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
    await send(text)
  }

  /**
   * 送一則訊息：打的字，或「繼續」鍵上的字（`continues` 是停下的那一輪）。伺服器沒收下的從畫面上
   * 拿掉；打的字放回輸入欄。
   */
  async function send(text: string, continues?: string) {
    await sendMessage({ text }, continues === undefined ? undefined : { body: { continues } })
    const error = chat.error
    if (error === undefined) return
    clearError()
    // 回應開始串流之後才斷的，伺服器已經收下這一則（它會存到停下之前）：留著。其餘的伺服器沒收，
    // 從畫面上拿掉——重新載入之後它也不會在。
    const unsent = error instanceof ApiError || chat.lastMessage?.role === 'user'
    if (unsent) setMessages((current) => withoutLastUser(current))
    const restored = unsent && continues === undefined
    if (restored) setDraft(text)
    if (continues !== undefined && agentRefusalOf(error)?.reason === 'not_continuable') {
      setSpent((current) => new Set(current).add(continues))
      setFailure({ kind: 'spent', restored: false })
      return
    }
    await report(error, { restored })
  }

  /**
   * 按了「停止」（M5 票 25）：請伺服器停下那一輪。停下的說明經這一條串流送到，串流跟著結束。伺服器說沒有在跑
   * （還沒開始、剛好答完）或請求沒成，就只收掉這一頁的串流。
   */
  async function onStop() {
    try {
      await stopTurn(chat.id)
    } catch {
      void stop()
    }
  }

  /**
   * 另一個分頁正在答（`busy`）：接回伺服器的對話，跟上那一輪。
   */
  async function catchUp() {
    const fresh = await readConversation(chat.id).catch(() => null)
    if (fresh?.running == null) return
    setMessages(fresh.messages)
    void follow(chat, fresh.running)
  }

  /** 送不出去的那一次（訊息、恢復或指令）：後端說不行的理由各有去處，其餘照請求為什麼沒成說。 */
  async function report(error: unknown, { restored }: { restored: boolean }) {
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
    if (refusal?.reason === 'ai_paused') {
      // 面板頂上那一塊說暫停到幾點（`AgentPanel`）。
      void queryClient.invalidateQueries({ queryKey: agentStatusQueryOptions.queryKey })
    }
    if (refusal?.reason === 'busy') {
      setFailure({ kind: 'busy', restored })
      await catchUp()
    } else if (refusal?.reason === 'ai_paused') setFailure({ kind: 'paused', restored })
    else if (refusal?.reason === 'unknown_command')
      setFailure({ kind: 'unknown', word: refusal.detail, restored })
    else setFailure({ kind: 'request', error, restored })
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
        const fresh = (await readConversation(chat.id))?.messages ?? []
        setMessages(fresh)
        setOutputs([])
        after = fresh.length
      }
      const key = ++outputKey.current
      setOutputs((current) => [...current, { key, after, result }])
    } catch (error) {
      setDraft(text)
      await report(error, { restored: true })
    } finally {
      setRunning(false)
    }
  }

  function pick(name: SlashName) {
    void submit(`/${name}`)
  }

  /**
   * 按了卡片之後（`ConfirmCard`）：那一格還在最後一則助理訊息裡等確認，就告訴 `useChat`；等確認的都有
   * 回應了，送出恢復的那一則。伺服器照 Proposal 決定按了什麼，這一則只是觸發（brief §20.24）。
   *
   * 送不出去（另一個分頁正在答、AI 剛被關掉）不要緊：卡片已經做完了，下一則訊息會把結果帶給助理。
   */
  const cardActions: CardActions = {
    respond: async (toolCallId, decided) => {
      const last = chat.lastMessage
      const part = last?.role === 'assistant' ? last.parts.find(isWaiting(toolCallId)) : undefined
      if (part === undefined) return
      await chat.addToolApprovalResponse({
        id: part.approval.id,
        approved: decided.status !== 'rejected',
      })
      if (!lastAssistantMessageIsCompleteWithApprovalResponses({ messages: chat.messages })) {
        return
      }
      setFailure(null)
      await chat.sendMessage()
      const error = chat.error
      if (error === undefined) return
      clearError()
      await report(error, { restored: false })
    },
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
    <CardContext.Provider value={cardActions}>
      <Transcript
        messages={messages}
        outputs={outputs}
        busy={busy}
        restarted={restarted}
        spent={spent}
        onContinue={(turn) => {
          setFailure(null)
          // 「繼續」一按就收掉：焦點先交給輸入欄，不掉回 `body`。
          input.current?.focus()
          void send(t('agent.stopped.continue'), turn)
        }}
      />
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
          {failure?.kind === 'spent' ? (
            <p className="text-sm text-ink">{t('agent.failure.spent')}</p>
          ) : null}
          {failure?.kind === 'request' ? (
            <RequestFailed error={failure.error} lead={t('agent.failure.lead')} />
          ) : null}
          {failure?.restored ? (
            <p className="text-xs text-ink-dim">{t('agent.failure.restored')}</p>
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
          <div
            ref={action}
            onFocus={() => {
              actionFocused.current = true
            }}
            onBlur={(event) => {
              // 換鍵時舊的那一顆被拿掉：那不算離開。點到別處（還在畫面上的那一顆失去焦點）才算。
              const left = event.target
              queueMicrotask(() => {
                if (left.isConnected) actionFocused.current = false
              })
            }}
            className="grid w-32"
          >
            {streaming ? (
              <GhostButton type="button" onClick={() => void onStop()}>
                {t('agent.stop')}
              </GhostButton>
            ) : (
              <PrimaryButton type="submit">{t('agent.send')}</PrimaryButton>
            )}
          </div>
        </div>
      </form>
    </CardContext.Provider>
  )
}

/** 最後一則助理訊息裡、這一次 tool call 那一格，還在等確認的話。 */
function isWaiting(toolCallId: string) {
  return (
    part: UIMessage['parts'][number],
  ): part is Extract<ToolUIPart | DynamicToolUIPart, { state: 'approval-requested' }> =>
    isToolUIPart(part) && part.toolCallId === toolCallId && part.state === 'approval-requested'
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
  spent,
  onContinue,
}: {
  messages: UIMessage[]
  outputs: Output[]
  busy: boolean
  restarted: boolean
  /** 伺服器說不能再續的那幾輪。 */
  spent: ReadonlySet<string>
  onContinue: (turn: string) => void
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
            runId={lastOfItsRun(messages, index)}
            // 「繼續」只接最後一輪：只畫在最後一則上，答著、跑指令時不畫。
            offer={index === messages.length - 1 && !busy ? (turn) => !spent.has(turn) : null}
            onContinue={onContinue}
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

function runIdOf(message: UIMessage | undefined): string | null {
  if (message?.role !== 'assistant') return null
  const metadata = message.metadata
  if (typeof metadata !== 'object' || metadata === null || !('runId' in metadata)) return null
  return typeof metadata.runId === 'string' ? metadata.runId : null
}

function Message({
  message,
  continued,
  runId,
  offer,
  onContinue,
}: {
  message: UIMessage
  continued: boolean
  runId: string | null
  /** 這一則是最後一則的話，哪一輪還畫「繼續」；不是最後一則是 `null`。 */
  offer: ((turn: string) => boolean) | null
  onContinue: (turn: string) => void
}) {
  const { t } = useTranslation()
  const leave = useLeavePanel()

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
  // 只有停下的說明的那一則是 Berth 說的，不標「助理」。
  const spoken = message.parts.some((part) => isTextUIPart(part) || isToolUIPart(part))

  return (
    <div className="grid min-w-0 gap-2">
      {continued || !spoken ? null : (
        <span className="label text-ink-dim">{t('agent.assistant')}</span>
      )}
      {message.parts.map((part, index) => {
        // 一則訊息裡的片段沒有自己的 id；位置就是它的身分（只會往後長，不會重排）。
        const key = `${message.id}:${index}`
        if (isTextUIPart(part)) return part.text ? <Markdown key={key} text={part.text} /> : null
        if (isToolUIPart(part)) return <ToolPart key={key} part={part} />
        const stop = isDataUIPart(part) ? stopOf(part) : null
        if (stop !== null) {
          const offered = stop.continuable && offer !== null && offer(stop.turn_id)
          return (
            <StopNote
              key={key}
              stop={stop}
              onContinue={offered ? () => onContinue(stop.turn_id) : null}
            />
          )
        }
        return null
      })}
      {runId ? (
        <Link
          to="/agent/runs/$runId"
          params={{ runId }}
          aria-label={t('agent.stepsLabel')}
          onClick={leave}
          className={`${TEXT_LINK} justify-self-start text-ink-dim`}
        >
          {t('agent.steps')}
        </Link>
      ) : null}
    </div>
  )
}

/**
 * 防護停下的說明（M5 票 22，`.scratch/m5/side-panel-shape.md`〈面板結構〉）：Berth 說的，不是助理的話。
 * `assigned` 不是 `blocked`：這一輪已經結束，要人決定換個問法、再問，或按一次「繼續」。
 */
function StopNote({ stop, onContinue }: { stop: TurnStop; onContinue: (() => void) | null }) {
  const { t } = useTranslation()
  return (
    <div data-stop={stop.reason} className="grid min-w-0 gap-2">
      <Notice signal="assigned" label={t('agent.stopped.label')}>
        {stop.note}
      </Notice>
      {onContinue !== null ? (
        <div className="grid w-32">
          <GhostButton type="button" onClick={onContinue}>
            {t('agent.stopped.continue')}
          </GhostButton>
        </div>
      ) : null}
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

/**
 * 一格工具呼叫。它提出過確認卡的話畫那張卡（卡片由伺服器的 Proposal 決定，不由模型決定），否則是
 * 收成一行的工具。
 */
function ToolPart({ part }: { part: ToolUIPart | DynamicToolUIPart }) {
  const { conversationId } = usePanel()
  const card = useQuery({
    ...proposalsQueryOptions(conversationId),
    select: (found: Proposal[]) => found.find((p) => p.tool_call_id === part.toolCallId),
  })
  if (card.data) return <ConfirmCard proposal={card.data} toolCallId={part.toolCallId} />
  return <ToolCall part={part} />
}
