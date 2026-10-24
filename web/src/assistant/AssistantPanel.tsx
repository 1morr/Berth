import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
  type RefObject,
} from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useRouterState } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import {
  assistantRefusalOf,
  assistantStatusQueryOptions,
  conversationQueryOptions,
  conversationsQueryOptions,
  CONVERSATIONS_KEY,
  sendMessage,
  type NoticePart,
  type ReplyLanguage,
} from '../api/assistant'
import { useJobStream } from '../api/events'
import { displayRound } from '../i18n/displayRound'
import { COMPACT_BUTTON, GHOST_LINK, GhostButton, Notice, TEXT_LINK } from '../components/controls'
import { Dot } from '../components/Dot'
import { problemText } from '../components/requestProblem'
import { SIGNAL_FILL, type Signal } from '../components/signal'
import { Timestamp } from '../components/Timestamp'
import { ProposalsContext, type Proposals } from './proposals'
import { reasonText } from './refusals'
import { ResultCard } from './ResultCard'
import { toolName } from './toolNames'
import { ToolCallContext } from './toolCall'
import { blocksOf, withChunk, type Block, type Item, type Pending } from './transcript'

/**
 * 助理的側面板（M5 票 08，`.scratch/m5/side-panel-shape.md`）。`AppShell` 決定它在哪裡、開著沒有；
 * 這裡是面板裡的一切：沒設定好的說法、只能聊天的標示、對話、歷史清單、輸入。
 *
 * **模型的字永遠是中性的散文**：不塗任何信號色、不畫成成功——做了什麼只以工具結果的卡為準
 * （`ResultCard`，票 09）。
 */

/** 面板的 id：頁首的「助理」鍵以 `aria-controls` 指著它。 */
export const PANEL_ID = 'assistant'

/** 面板並排的寬度（Tailwind 的 `lg`）：以下面板取代頁面。 */
const WIDE = '(min-width: 64rem)'

type Selection = { kind: 'latest' } | { kind: 'new' } | { kind: 'id'; id: number }

/** 頁面請求面板顯示某一則對話（AI 活動頁，M5 票 14）。`nonce` 讓同一則被連續請求兩次也算兩次。 */
export interface ConversationRequest {
  id: number
  nonce: number
}

export function AssistantPanel({
  admin,
  focusOnMount,
  onClose,
  request = null,
  onRequestHandled,
}: {
  admin: boolean
  /** 使用者按「助理」打開的：焦點進輸入框。重整時照記憶打開的不搶焦點。 */
  focusOnMount: boolean
  onClose: () => void
  request?: ConversationRequest | null
  /** 請求接下了：`AppShell` 清掉它，之後關了再開不會又跳回那一則。 */
  onRequestHandled?: () => void
}) {
  const { t } = useTranslation()
  const status = useQuery(assistantStatusQueryOptions)
  const ready = status.data?.ready === true

  const [view, setView] = useState<'chat' | 'history'>('chat')
  const [selection, setSelection] = useState<Selection>({ kind: 'latest' })
  const input = useRef<HTMLTextAreaElement>(null)

  // 輸入框畫出來的那一刻給一次（狀態讀到之前它還不在）；之後焦點是使用者的。
  const focused = useRef(false)
  useEffect(() => {
    if (!focusOnMount || focused.current || !input.current) return
    focused.current = true
    input.current.focus()
  }, [focusOnMount, ready])

  // 頁面要看某一則：換到那一則、回到對話（在 render 裡接，不在 effect 裡 setState）。
  const [seen, setSeen] = useState<ConversationRequest | null>(null)
  if (request !== null && request !== seen) {
    setSeen(request)
    setSelection({ kind: 'id', id: request.id })
    setView('chat')
  }
  // 焦點進輸入框（按開的焦點進面板，同「助理」鍵）；接下之後 `AppShell` 清掉請求。
  useEffect(() => {
    if (request === null) return
    input.current?.focus()
    onRequestHandled?.()
  }, [request, onRequestHandled])

  // 歷史清單挑了一則：清單那一列跟著清單消失，焦點回輸入框（shape 第 6 節）。輸入框在清單收起、
  // 對話那一塊不再 `hidden` 之後才拿得到焦點，所以等畫完再給。
  const backToChat = useRef(false)
  useEffect(() => {
    if (view !== 'chat' || !backToChat.current) return
    backToChat.current = false
    input.current?.focus()
  }, [view])

  const onKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (event.key === 'Escape' && !event.nativeEvent.isComposing) {
      event.stopPropagation()
      onClose()
    }
  }

  return (
    <aside
      id={PANEL_ID}
      aria-label={t('assistant.label')}
      onKeyDown={onKeyDown}
      // `lg` 以上固定在右側全高（`AppShell` 讓出同寬的一欄）；以下取代 `main`，捲過頁首之後佔滿畫面。
      className="sticky top-0 flex h-dvh flex-col bg-well lg:fixed lg:inset-y-0 lg:right-0 lg:w-[26rem] lg:border-l-2 lg:border-rule-strong xl:w-[28rem]"
    >
      <div className="flex flex-wrap items-center gap-2 border-b-2 border-rule bg-deck px-4 py-2.5">
        <h2 className="label mr-auto bg-deck text-ink">{t('assistant.label')}</h2>
        {ready && (
          <>
            <Link
              to="/ai-activity"
              className={COMPACT_BUTTON}
              // `lg` 以下面板取代頁面：不收起面板就換了一頁卻看不到。
              onClick={() => {
                if (!window.matchMedia(WIDE).matches) onClose()
              }}
            >
              {t('assistant.activity')}
            </Link>
            <button
              type="button"
              className={COMPACT_BUTTON}
              onClick={() => {
                setSelection({ kind: 'new' })
                setView('chat')
                input.current?.focus()
              }}
            >
              {t('assistant.newConversation')}
            </button>
            <button
              type="button"
              className={COMPACT_BUTTON}
              onClick={() => setView(view === 'history' ? 'chat' : 'history')}
            >
              {view === 'history' ? t('assistant.back') : t('assistant.history')}
            </button>
          </>
        )}
        <button type="button" className={COMPACT_BUTTON} onClick={onClose}>
          {t('assistant.close')}
        </button>
      </div>
      {status.data && !ready && <NotReady admin={admin} />}
      {ready && view === 'history' && (
        <ConversationList
          onPick={(id) => {
            setSelection({ kind: 'id', id })
            backToChat.current = true
            setView('chat')
          }}
        />
      )}
      {ready && (
        <Chat
          hidden={view !== 'chat'}
          admin={admin}
          chatOnly={status.data?.chat_only === true}
          selection={selection}
          onSelect={(id) => setSelection({ kind: 'id', id })}
          input={input}
        />
      )}
    </aside>
  )
}

function NotReady({ admin }: { admin: boolean }) {
  const { t } = useTranslation()
  return (
    <div className="m-4 grid gap-3 border-2 border-rule bg-well px-4 py-3">
      <p className="text-sm text-ink">
        {admin ? t('assistant.notReady.admin') : t('assistant.notReady.user')}
      </p>
      {admin && (
        <Link to="/settings/ai" className={GHOST_LINK}>
          {t('assistant.notReady.settings')}
        </Link>
      )}
    </div>
  )
}

function ConversationList({ onPick }: { onPick: (id: number) => void }) {
  const { t } = useTranslation()
  const list = useQuery(conversationsQueryOptions)
  return (
    <section aria-labelledby="assistant-history" className="min-h-0 flex-1 overflow-y-auto p-4">
      <h3 id="assistant-history" className="label mb-3 border-b-2 border-rule-strong pb-2 text-ink">
        {t('assistant.list.title')}
      </h3>
      {list.isError && <p className="text-sm text-ink">{t('assistant.list.readFailed')}</p>}
      {list.data?.length === 0 && (
        <p className="text-sm text-ink-dim">{t('assistant.list.empty')}</p>
      )}
      <ul className="grid gap-2">
        {list.data?.map((row) => (
          <li key={row.id}>
            <button
              type="button"
              onClick={() => onPick(row.id)}
              className="grid w-full gap-1 border-2 border-rule px-3 py-2 text-left hover:border-rule-strong"
            >
              <span className="min-w-0 text-sm break-words text-ink">{row.title}</span>
              <span className="text-xs text-ink-dim">
                <Timestamp at={row.updated_at} past />
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}

function Chat({
  hidden,
  admin,
  chatOnly,
  selection,
  onSelect,
  input,
}: {
  hidden: boolean
  admin: boolean
  chatOnly: boolean
  selection: Selection
  onSelect: (id: number) => void
  input: RefObject<HTMLTextAreaElement | null>
}) {
  const { t, i18n } = useTranslation()
  const queryClient = useQueryClient()
  // 送出時畫面在哪一頁：作品頁時後端把那部作品跟著這句話交給模型（M5 票 12）。
  const page = useRouterState({ select: (state) => state.location.pathname })
  const list = useQuery({ ...conversationsQueryOptions, enabled: selection.kind === 'latest' })
  const currentId =
    selection.kind === 'id'
      ? selection.id
      : selection.kind === 'latest'
        ? (list.data?.[0]?.id ?? null)
        : null
  const conversation = useQuery({
    ...conversationQueryOptions(currentId ?? 0),
    enabled: currentId !== null,
  })

  const [draft, setDraft] = useState('')
  const [pending, setPending] = useState<Pending | null>(null)
  const [problem, setProblem] = useState('')

  const messages = currentId === null ? [] : (conversation.data?.messages ?? [])
  const blocks = blocksOf(messages, pending)
  const replying = pending === null && conversation.data?.replying === true
  // 確認卡的現況（票 10）：卡片從存下的工具結果畫，狀態與結果讀這一份。回覆在跑時按不得。
  const cards = conversation.data?.proposals
  const proposals = useMemo<Proposals>(
    () => ({
      conversationId: currentId,
      cards: new Map((currentId === null ? [] : (cards ?? [])).map((card) => [card.id, card])),
      replying: pending !== null || replying,
      refresh: () => queryClient.invalidateQueries({ queryKey: CONVERSATIONS_KEY }),
    }),
    [cards, currentId, pending, replying, queryClient],
  )

  const send = async () => {
    const text = draft.trim()
    if (!text || pending) return
    setProblem('')
    setPending({ text, after: messages.at(-1)?.id ?? 0, items: [] })
    let started = false
    try {
      await sendMessage({
        conversationId: currentId,
        text,
        language: i18n.language as ReplyLanguage,
        page,
        onChunk: (chunk) => {
          if (chunk.type === 'start') {
            started = true
            setDraft('')
            onSelect(chunk.conversation_id)
            return
          }
          setPending((current) =>
            current ? { ...current, items: withChunk(current.items, chunk) } : current,
          )
        },
      })
    } catch (error) {
      const refusal = assistantRefusalOf(error)
      setProblem(
        refusal
          ? t(`assistant.refusal.${refusal.reason}`)
          : started
            ? t('assistant.streamBroken')
            : problemText(t, error, t('assistant.sendFailed')),
      )
    } finally {
      // 真相在資料庫：重讀完再收掉先畫上去的那一段，畫面不會閃一下空的。
      await queryClient.invalidateQueries({ queryKey: CONVERSATIONS_KEY })
      setPending(null)
    }
  }

  const onSubmit = (event: FormEvent) => {
    event.preventDefault()
    void send()
  }

  const onInputKey = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    // 輸入法組字中的 Enter 是選字，不是送出。
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      void send()
    }
  }

  return (
    <div hidden={hidden} className="flex min-h-0 flex-1 flex-col">
      {chatOnly && (
        <div className="px-4 pt-4">
          <Notice signal="neutral" label={t('assistant.chatOnly.label')}>
            {t('assistant.chatOnly.body')}
          </Notice>
        </div>
      )}
      <ProposalsContext value={proposals}>
        <Transcript
          blocks={blocks}
          admin={admin}
          failed={currentId !== null && conversation.isError}
          replying={replying}
        />
      </ProposalsContext>
      <form onSubmit={onSubmit} className="grid gap-2 border-t-2 border-rule px-4 py-3">
        <label htmlFor="assistant-input" className="sr-only">
          {t('assistant.input')}
        </label>
        <textarea
          id="assistant-input"
          ref={input}
          rows={3}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={onInputKey}
          className="resize-y border-2 border-rule-strong bg-hull px-3 py-2.5 text-sm text-ink focus:border-ink"
        />
        <div className="flex flex-wrap items-center gap-3">
          <GhostButton type="submit" busy={pending !== null || replying}>
            {pending !== null ? t('assistant.sending') : t('assistant.send')}
          </GhostButton>
          <p role="status" className="min-w-0 flex-1 text-xs break-words text-ink">
            {problem}
          </p>
        </div>
      </form>
    </div>
  )
}

function Transcript({
  blocks,
  admin,
  failed,
  replying,
}: {
  blocks: Block[]
  admin: boolean
  failed: boolean
  replying: boolean
}) {
  const { t } = useTranslation()
  const scroller = useRef<HTMLDivElement>(null)
  const atBottom = useRef(true)

  // 新字進來時，本來就在最底才跟著捲（shape 第 5 節）；往上翻著看的人不被拉回去。
  useEffect(() => {
    const element = scroller.current
    if (element && atBottom.current) element.scrollTop = element.scrollHeight
  })

  return (
    <div
      ref={scroller}
      onScroll={(event) => {
        const element = event.currentTarget
        atBottom.current = element.scrollHeight - element.scrollTop - element.clientHeight < 24
      }}
      className="min-h-0 flex-1 overflow-y-auto px-4 py-4"
    >
      {failed && <p className="text-sm text-ink">{t('assistant.readFailed')}</p>}
      {blocks.length === 0 && !failed && (
        <p className="text-sm text-ink-dim">{t('assistant.empty')}</p>
      )}
      {blocks.some(hasJobCard) && <JobStream />}
      <ol role="log" aria-label={t('assistant.log')} className="grid gap-3">
        {blocks.map((block) =>
          block.kind === 'user' ? (
            <li key={block.key} className="grid gap-1.5 bg-deck px-3 py-2.5">
              <span className="label text-ink-dim">{t('assistant.you')}</span>
              <p className="min-w-0 text-sm break-words whitespace-pre-wrap text-ink">
                {block.text}
              </p>
              {block.page && <PageNote page={block.page} />}
            </li>
          ) : (
            <li key={block.key} aria-busy={block.busy} className="grid gap-1.5 px-3 py-2.5">
              <span className="label text-ink-dim">{t('assistant.speaker')}</span>
              {block.items.map((item) => (
                <ItemView key={item.key} item={item} admin={admin} />
              ))}
            </li>
          ),
        )}
      </ol>
      {replying && (
        <p aria-busy className="mt-3 text-xs text-ink-dim">
          {t('assistant.replying')}
        </p>
      )}
    </div>
  )
}

/** 使用者說這句話時正在看的作品：模型拿到的就是這一部（M5 票 12）。 */
function PageNote({ page }: { page: NonNullable<Extract<Block, { kind: 'user' }>['page']> }) {
  const { t, i18n } = useTranslation()
  const title = displayRound(i18n.language, { 'zh-Hant': page.title, en: page.title_en })
  return (
    <p className="value text-xs wrap-anywhere text-ink-dim">{t('assistant.onPage', { title })}</p>
  )
}

/** 對話裡有送單卡時才掛 `/events/stream`（同 `useJobStream` 的「掛在需要它的那一頁上」）：卡片跟著推播重問。 */
function JobStream() {
  useJobStream()
  return null
}

function hasJobCard(block: Block): boolean {
  return (
    block.kind === 'assistant' &&
    block.items.some((item) => item.kind === 'tool' && item.output?.type === 'SubmittedJob')
  )
}

function ItemView({ item, admin }: { item: Item; admin: boolean }) {
  const { t } = useTranslation()
  // 這個人拿得到的工具與它們的等級（M5 票 11）：後端讀命令的標記，這裡不另寫一份。
  const status = useQuery(assistantStatusQueryOptions)
  switch (item.kind) {
    case 'text':
      return <p className="min-w-0 text-sm break-words whitespace-pre-wrap text-ink">{item.text}</p>
    case 'tool': {
      const tool = toolName(t, item.name)
      const known = status.data?.tools.find((one) => one.name === item.name)
      // 清單上沒有的（舊對話裡、這一版拿掉了，或角色拿不到了）照查詢的說法：說錯的代價是一個動詞。
      const lines = known && known.effect !== 'read' ? WRITE_LINES : LOOKUP_LINES
      if (item.state === 'running') {
        return (
          <p className="value flex flex-wrap items-center gap-2 text-xs text-ink">
            <span className={`label px-1.5 py-0.5 ${SIGNAL_FILL.working}`}>{t(lines.chip)}</span>
            {t(lines.running, { tool })}
          </p>
        )
      }
      if (item.state === 'refused') {
        return (
          <p className="value text-xs wrap-anywhere text-ink">
            {t(lines.refused, { tool })}
            {item.reason && (
              <>
                {' '}
                <Dot />{' '}
                <span className="text-ink-dim">{reasonText(t, item.reason, item.detail)}</span>
              </>
            )}
          </p>
        )
      }
      return (
        <>
          <p className="value text-xs text-ink-dim">
            {item.state === 'proposed'
              ? t('assistant.tools.proposed', { tool })
              : t(lines.done, { tool })}
          </p>
          {item.output && (
            <ToolCallContext
              value={{
                callId: item.callId,
                messageId: item.messageId,
                undoable: known?.undoable === true,
                undone: item.undone,
              }}
            >
              <ResultCard output={item.output} />
            </ToolCallContext>
          )}
        </>
      )
    }
    case 'notice':
      return <NoticeView notice={item.notice} admin={admin} />
  }
}

const LOOKUP_LINES = {
  chip: 'assistant.tools.chip',
  running: 'assistant.tools.running',
  done: 'assistant.tools.done',
  refused: 'assistant.tools.refused',
} as const

/** 會改東西的工具（可逆的直接做、不可逆的出卡）：狀態行說「正在送單」，不說「正在查」（M5 票 12）。 */
const WRITE_LINES = {
  chip: 'assistant.tools.write.chip',
  running: 'assistant.tools.write.running',
  done: 'assistant.tools.write.done',
  refused: 'assistant.tools.write.refused',
} as const

/** 等一下就好的（Berth 自己會好、或使用者再送一次）是 `assigned`；要管理員改設定的是 `blocked`。 */
const WAITABLE: ReadonlySet<NoticePart['failure']> = new Set([
  'rate_limited',
  'provider_down',
  'unreachable',
])

function NoticeView({ notice, admin }: { notice: NoticePart; admin: boolean }) {
  const { t } = useTranslation()
  let signal: Signal
  let label: string
  let text: string
  switch (notice.notice) {
    case 'round_limit':
      signal = 'assigned'
      label = t('assistant.notice.stopped')
      text = t('assistant.notice.roundLimit', { count: notice.limit ?? 0 })
      break
    case 'internal_error':
      signal = 'blocked'
      label = t('assistant.notice.failed')
      text = t('assistant.notice.internal')
      break
    case 'provider_failed': {
      const failure = notice.failure ?? 'rejected'
      signal = WAITABLE.has(failure) ? 'assigned' : 'blocked'
      label = signal === 'assigned' ? t('assistant.notice.wait') : t('assistant.notice.failed')
      text =
        failure === 'rate_limited'
          ? notice.retry_after === null || notice.retry_after === undefined
            ? t('assistant.notice.failure.rate_limitedUnknown')
            : t('assistant.notice.failure.rate_limited', { count: Math.ceil(notice.retry_after) })
          : t(`assistant.notice.failure.${failure}`)
      break
    }
  }
  return (
    <Notice signal={signal} label={label}>
      {text}
      {admin && signal === 'blocked' && notice.notice === 'provider_failed' && (
        <>
          {' '}
          <Link to="/settings/ai" className={TEXT_LINK}>
            {t('assistant.notice.settings')}
          </Link>
        </>
      )}
    </Notice>
  )
}
