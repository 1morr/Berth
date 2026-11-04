import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { conversationsQueryOptions, type ConversationEntry } from '../api/agent'
import { Timestamp } from '../components/Timestamp'
import { PanelFailed, PanelLoading } from './PanelStates'
import { usePanel } from './panelState'

/**
 * 我的對話（M5.5 票 18）：面板頁首的「對話」打開的那一塊，與 `/history` 的結果畫同一份清單。選一段走
 * `switchTo`；在跑的那一段標「回答中」，現在這一段標「目前這段」（`aria-current`）。
 */

/** 頁首「對話」打開的那一塊：每次打開都重問一次（誰在跑會變）。 */
export function ConversationPicker({ id, onPicked }: { id: string; onPicked: () => void }) {
  const { t } = useTranslation()
  const found = useQuery(conversationsQueryOptions)
  return (
    <div id={id} className="max-h-[50dvh] overflow-y-auto border-b-2 border-rule bg-hull">
      {found.isPending ? <PanelLoading /> : null}
      {found.isError ? <PanelFailed error={found.error} /> : null}
      {found.data?.length === 0 ? (
        <p className="p-4 text-sm text-ink-dim">{t('agent.conversations.none')}</p>
      ) : null}
      {found.data !== undefined && found.data.length > 0 ? (
        <div className="p-2">
          <ConversationEntries entries={found.data} onPicked={onPicked} takeFocus />
        </div>
      ) : null}
    </div>
  )
}

/**
 * 一段一列的按鈕。`onPicked`：選了之後（例如收起那一塊）。
 *
 * `takeFocus`：第一次畫出來時把焦點交給目前這段（沒有就第一段）。抬頭列的「對話」打開的清單排在整排抬頭鍵
 * 之後，不交的話 Tab 要先經過「新對話」「關閉」才進得去（M5.5 票 19 的 critique）；`Esc` 收起時焦點回「對話」。
 * `/history` 的那一份在對話紀錄裡，不搶焦點。
 */
export function ConversationEntries({
  entries,
  onPicked,
  takeFocus = false,
}: {
  entries: ConversationEntry[]
  onPicked?: () => void
  takeFocus?: boolean
}) {
  const { t } = useTranslation()
  const { conversationId, switchTo } = usePanel()
  const target = entries.some((entry) => entry.id === conversationId)
    ? conversationId
    : entries[0]?.id
  return (
    <ul aria-label={t('agent.conversations.label')} className="grid gap-1">
      {entries.map((entry) => {
        const current = entry.id === conversationId
        return (
          <li key={entry.id}>
            <button
              // 只在掛上去的那一刻聚焦：使用者剛按「對話」打開它；之後清單重讀、列還在，不會再搶。
              autoFocus={takeFocus && entry.id === target}
              type="button"
              aria-current={current ? 'true' : undefined}
              onClick={() => {
                if (!current) switchTo(entry.id)
                onPicked?.()
              }}
              className={`grid w-full min-w-0 gap-0.5 border-2 px-3 py-2 text-left ${
                current
                  ? 'border-transparent bg-deck shadow-[inset_3px_0_0_var(--color-ink)]'
                  : 'border-transparent hover:border-rule-strong'
              }`}
            >
              <span className="text-sm wrap-anywhere text-ink">
                {entry.title || t('agent.conversations.untitled')}
              </span>
              <span className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-xs text-ink-dim">
                <Timestamp at={entry.updated_at} past />
                {entry.running ? (
                  <span className="label bg-working px-1.5 py-0.5 text-on-signal">
                    {t('agent.conversations.running')}
                  </span>
                ) : null}
                {current ? (
                  <span className="label text-ink">{t('agent.conversations.current')}</span>
                ) : null}
              </span>
            </button>
          </li>
        )
      })}
    </ul>
  )
}
