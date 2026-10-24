import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
  type RefObject,
} from 'react'
import type { TFunction } from 'i18next'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
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
import { COMPACT_BUTTON, GHOST_LINK, GhostButton, Notice } from '../components/controls'
import { problemText } from '../components/requestProblem'
import { SIGNAL_FILL, type Signal } from '../components/signal'
import { Timestamp } from '../components/Timestamp'
import { blocksOf, withChunk, type Block, type Item, type Pending } from './transcript'

/**
 * 助理的側面板（M5 票 08，`.scratch/m5/side-panel-shape.md`）。`AppShell` 決定它在哪裡、開著沒有；
 * 這裡是面板裡的一切：沒設定好的說法、只能聊天的標示、對話、歷史清單、輸入。
 *
 * **模型的字永遠是中性的散文**：不塗任何信號色、不畫成成功——做了什麼只以工具結果的卡為準（票 09 起）。
 */

/** 面板的 id：頁首的「助理」鍵以 `aria-controls` 指著它。 */
export const PANEL_ID = 'assistant'

type Selection = { kind: 'latest' } | { kind: 'new' } | { kind: 'id'; id: number }

export function AssistantPanel({
  admin,
  focusOnMount,
  onClose,
}: {
  admin: boolean
  /** 使用者按「助理」打開的：焦點進輸入框。重整時照記憶打開的不搶焦點。 */
  focusOnMount: boolean
  onClose: () => void
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
              <span className="text-sm break-words text-ink">{row.title}</span>
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
      <Transcript
        blocks={blocks}
        admin={admin}
        failed={currentId !== null && conversation.isError}
        replying={replying}
      />
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
      <ol role="log" aria-label={t('assistant.label')} className="grid gap-3">
        {blocks.map((block) =>
          block.kind === 'user' ? (
            <li key={block.key} className="grid gap-1.5 bg-deck px-3 py-2.5">
              <span className="label text-ink-dim">{t('assistant.you')}</span>
              <p className="text-sm break-words whitespace-pre-wrap text-ink">{block.text}</p>
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
        <p aria-busy className="value mt-3 text-xs text-ink-dim">
          {t('assistant.replying')}
        </p>
      )}
    </div>
  )
}

function ItemView({ item, admin }: { item: Item; admin: boolean }) {
  const { t } = useTranslation()
  switch (item.kind) {
    case 'text':
      return <p className="text-sm break-words whitespace-pre-wrap text-ink">{item.text}</p>
    case 'tool': {
      const tool = toolName(t, item.name)
      if (item.state === 'running') {
        return (
          <p className="value flex flex-wrap items-center gap-2 text-xs text-ink">
            <span className={`label px-1.5 py-0.5 ${SIGNAL_FILL.working}`}>
              {t('assistant.tools.chip')}
            </span>
            {t('assistant.tools.running', { tool })}
          </p>
        )
      }
      if (item.state === 'refused') {
        return (
          <p className="value text-xs wrap-anywhere text-ink">
            {t('assistant.tools.refused', { tool })}
            {item.reason && <span className="text-ink-dim"> · {item.reason}</span>}
          </p>
        )
      }
      return <p className="value text-xs text-ink-dim">{t('assistant.tools.done', { tool })}</p>
    }
    case 'notice':
      return <NoticeView notice={item.notice} admin={admin} />
  }
}

/** 工具在畫面上的名字。沒有文案的工具（後端先加了）退回「工具」，不印出 key。 */
function toolName(t: TFunction, name: string): string {
  return name === 'recent_imports'
    ? t('assistant.tools.recent_imports')
    : t('assistant.tools.other')
}

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
      text = t('assistant.notice.roundLimit')
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
          <Link
            to="/settings/ai"
            className="underline decoration-rule-strong underline-offset-4 hover:decoration-ink"
          >
            {t('assistant.notice.settings')}
          </Link>
        </>
      )}
    </Notice>
  )
}
