import { useContext, useId } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'

import { aiActivityQueryOptions, AI_ACTIVITY_KEY, type AiActivityEntry } from '../api/aiActivity'
import { CONVERSATIONS_KEY } from '../api/assistant'
import { meQueryOptions } from '../api/auth'
import { RSS_KEY } from '../api/rss'
import { AssistantControlContext } from '../assistant/AssistantControl'
import { toolName } from '../assistant/toolNames'
import { UndoControl } from '../assistant/UndoButton'
import { Notice, PAGE_TITLE } from '../components/controls'
import { Dot } from '../components/Dot'
import { RequestFailed } from '../components/RequestFailed'
import { DetailLine } from '../components/QueueRow'
import { Timestamp } from '../components/Timestamp'
import { useFocusOnSettle } from '../components/useFocusOnSettle'

/**
 * AI 活動頁 `/ai-activity`（M5 票 14，`.scratch/m5/ai-activity-shape.md`）。
 *
 * 助理替人做過的每一件寫入，新的在前：一列一個動作，主詞、動作、對象、時間在列上，細節收在展開裡。
 * 慣例學 GitHub 的 audit log 與 Gmail 的「復原」：撤銷就在那一列上，撤了之後列還在、說已撤銷。
 * 不做篩選、分頁與匯出（筆數是家用的量，超過 200 筆說「更早的不列」）。資料來自對話本身，不另寫日誌。
 */
export function AiActivityPage() {
  const { t } = useTranslation()
  const me = useQuery(meQueryOptions)
  const activity = useQuery(aiActivityQueryOptions)
  const admin = me.data?.role === 'admin'

  return (
    <div className="mx-auto grid w-full max-w-[80rem] gap-4 px-6 py-8">
      <div className="grid gap-1 border-b-2 border-rule-strong pb-2">
        <h1 className={PAGE_TITLE}>{t('aiActivity.title')}</h1>
        <p className="text-sm text-ink-dim">
          {admin ? t('aiActivity.intro.admin') : t('aiActivity.intro.user')}
        </p>
      </div>

      {activity.isPending ? (
        <Loading />
      ) : !activity.data ? (
        <RequestFailed error={activity.error} lead={t('aiActivity.readFailed')} />
      ) : activity.data.entries.length === 0 ? (
        <Notice signal="neutral" label={t('aiActivity.empty.label')}>
          {admin ? t('aiActivity.empty.admin') : t('aiActivity.empty.user')}{' '}
          {t('aiActivity.empty.how')}
        </Notice>
      ) : (
        <>
          <ul className="grid gap-3">
            {activity.data.entries.map((entry) => (
              <li key={`${entry.conversation_id}:${entry.call_id}`} className="min-w-0">
                <ActivityRow entry={entry} />
              </li>
            ))}
          </ul>
          {activity.data.truncated && (
            <p className="text-xs text-ink-dim">{t('aiActivity.truncated')}</p>
          )}
        </>
      )}
    </div>
  )
}

/** 讀取中：三塊與列等高的色條。**不會動**——這個世界沒有骨架屏動畫。 */
function Loading() {
  return (
    <div className="grid gap-3" aria-hidden="true">
      {[0, 1, 2].map((index) => (
        <div key={index} className="grid gap-2 border-2 border-rule bg-well px-4 py-3">
          <span className="block h-5 w-2/5 bg-deck" />
          <span className="block h-4 w-3/5 bg-deck" />
          <span className="block h-4 w-1/5 bg-deck" />
        </div>
      ))}
    </div>
  )
}

/** 結果裡讀得出「對象」的型別；其餘沒有對象就不印（認不得的型別也不印）。 */
function targetOf(entry: AiActivityEntry): string | null {
  const result = entry.result
  switch (entry.result_type) {
    case 'SubmittedJob':
    case 'IndexerAdded':
      return typeof result.name === 'string' ? result.name : null
    case 'Subscribed': {
      const feed = result.feed
      if (typeof feed !== 'object' || feed === null) return null
      const name = (feed as { name?: unknown }).name
      return typeof name === 'string' ? name : null
    }
    default:
      return null
  }
}

/** 撤銷鍵上的字與後果句：結果卡上同一組；沒有專屬文案的型別用通用的一句。 */
function undoCopy(t: TFunction, resultType: string): { label: string; confirm: string } {
  switch (resultType) {
    case 'SubmittedJob':
      return {
        label: t('assistant.cards.submitted.undo'),
        confirm: t('assistant.cards.submitted.undoConfirm'),
      }
    case 'Subscribed':
      return {
        label: t('assistant.cards.subscribed.undo'),
        confirm: t('assistant.cards.subscribed.undoConfirm'),
      }
    default:
      return { label: t('aiActivity.undo.label'), confirm: t('aiActivity.undo.confirm') }
  }
}

/** 輸入與輸出 token 加起來；兩格都不知道是 `null`。 */
/** 輸入加輸出。任一格不知道就是不知道：加一半會是一個看起來像總數、其實少算的數。 */
function totalTokens(tokens: AiActivityEntry['tokens']): number | null {
  if (tokens.input === null || tokens.output === null) return null
  return tokens.input + tokens.output
}

function ActivityRow({ entry }: { entry: AiActivityEntry }) {
  const { t, i18n } = useTranslation()
  const { openConversation } = useContext(AssistantControlContext)
  const headingId = useId()
  const target = targetOf(entry)
  const total = totalTokens(entry.tokens)
  const args = Object.entries(entry.arguments)
  const copy = undoCopy(t, entry.result_type)

  // 撤銷之後這一格換成「已撤銷」，鍵本身消失了：焦點留在這一句上，不掉回頁面頂端。
  const status = useFocusOnSettle<HTMLParagraphElement>(entry.undo === 'undone')

  return (
    <article
      aria-labelledby={headingId}
      className="grid gap-2 border-2 border-rule bg-well px-4 py-3"
    >
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <span className="label bg-deck px-2 py-1.5 text-ink">{toolName(t, entry.tool)}</span>
        {target !== null && (
          <h2 id={headingId} className="value min-w-0 wrap-anywhere text-ink">
            {target}
          </h2>
        )}
        {/* 沒有對象時標題不畫，名字仍要有：這一列的可存取名稱退回動作名。 */}
        {target === null && (
          <h2 id={headingId} className="sr-only">
            {toolName(t, entry.tool)}
          </h2>
        )}
      </div>

      <p className="text-sm text-ink-dim">
        <Timestamp at={entry.at} past /> <Dot />{' '}
        <span>
          {t(entry.via === 'ai' ? 'aiActivity.viaAi' : 'aiActivity.viaConfirmed', {
            name: entry.user_name,
          })}
        </span>{' '}
        <Dot />{' '}
        {entry.own ? (
          <button
            type="button"
            onClick={() => openConversation(entry.conversation_id)}
            className="inline text-left text-ink underline decoration-rule-strong underline-offset-4 hover:decoration-ink"
          >
            {t('aiActivity.from', { title: entry.conversation_title })}
          </button>
        ) : (
          <span>{t('aiActivity.from', { title: entry.conversation_title })}</span>
        )}{' '}
        <Dot />{' '}
        <span className="value text-xs">
          {t('aiActivity.tokens', {
            total: total === null ? '—' : new Intl.NumberFormat(i18n.language).format(total),
          })}
        </span>
      </p>

      {entry.reason !== '' && (
        <div className="grid gap-0.5">
          <span className="label text-ink-dim">{t('aiActivity.reason')}</span>
          <p className="max-w-prose text-sm break-words whitespace-pre-wrap text-ink">
            {entry.reason}
          </p>
        </div>
      )}

      {args.length > 0 && (
        <details>
          <summary className="flex min-h-6 w-fit cursor-pointer items-center">
            <span className="label text-ink-dim">{t('aiActivity.input')}</span>
          </summary>
          <dl className="mt-2 grid gap-1 border-2 border-rule bg-hull px-3 py-2">
            {args.map(([name, value]) => (
              <DetailLine key={name} term={name}>
                {typeof value === 'string' ? value : JSON.stringify(value)}
              </DetailLine>
            ))}
          </dl>
        </details>
      )}

      {entry.undo === 'undoable' && (
        <UndoControl
          conversationId={entry.conversation_id}
          messageId={entry.message_id}
          callId={entry.call_id}
          label={copy.label}
          confirm={copy.confirm}
          invalidate={[
            [...AI_ACTIVITY_KEY],
            ['jobs'],
            ['media'],
            [...RSS_KEY],
            // 該對話的卡片與歷史清單：前綴比對，一併重讀。
            [...CONVERSATIONS_KEY],
          ]}
        />
      )}
      {entry.undo === 'undone' && (
        <p ref={status} tabIndex={-1} className="text-xs text-ink">
          {t('aiActivity.undone')} <Timestamp at={entry.undone_at} past />
        </p>
      )}
      {entry.undo === 'no_inverse' && (
        <p className="text-xs text-ink-dim">{t('aiActivity.noInverse')}</p>
      )}
      {entry.undo === 'not_allowed' && (
        <p className="text-xs text-ink-dim">{t('aiActivity.notAllowed')}</p>
      )}
    </article>
  )
}
