import { useContext, useId, useState, type ComponentType } from 'react'
import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'

import {
  confirmProposal,
  proposalRefusalOf,
  rejectProposal,
  type DownloadsDeletion,
  type IndexerAddition,
  type ProposalCard,
  type ProposalPreviews,
  type ProposalPreviewType,
} from '../api/assistant'
import { CONFIRM_ACTIONS, GhostButton, PrimaryButton } from '../components/controls'
import { Dot } from '../components/Dot'
import { problemText } from '../components/requestProblem'
import { SIGNAL_FILL } from '../components/signal'
import { formatSize } from '../media/searchResult'
import { ProposalsContext } from './proposals'

/**
 * 確認卡（M5 票 10，CONTEXT.md 的 Proposal，DESIGN.md〈助理側面板〉的確認卡）：不可逆的工具 AI 不能自己做，
 * 停在這張卡上，人按了「確認」才以他執行。
 *
 * 卡上講的是**會發生什麼**（加哪一站、在哪個網址；刪哪幾個檔案、空不空得出空間），不是工具名；依後端給的
 * 預覽型別挑那一段（`ProposalPreviewType` 一種一格，要人按的工具多一種而這裡沒跟上時 `tsc` 紅）。
 * 存下的工具結果是提出時的樣子，按過之後的狀態與結果讀對話的 `proposals`（`ProposalsContext`）。
 */

const PREVIEWS: {
  [K in ProposalPreviewType]: ComponentType<{ preview: ProposalPreviews[K] }>
} = {
  IndexerAddition: IndexerAdditionView,
  DownloadsDeletion: DownloadsDeletionView,
}

/** 卡片標題與確認鍵的字：一個要人按的工具一組。沒有文案的（後端先加了）退回通用的說法。 */
const TITLES = {
  add_indexer: 'assistant.proposal.tool.add_indexer',
  delete_downloads: 'assistant.proposal.tool.delete_downloads',
} as const

const CONFIRMS = {
  add_indexer: 'assistant.proposal.confirm.add_indexer',
  delete_downloads: 'assistant.proposal.confirm.delete_downloads',
} as const

export function ProposalCardView({ result }: { result: ProposalCard }) {
  const { t } = useTranslation()
  const { cards, replying, refresh } = useContext(ProposalsContext)
  const card = cards.get(result.id) ?? result
  const id = useId()
  const [pressing, setPressing] = useState<'confirm' | 'reject' | null>(null)
  const [problem, setProblem] = useState('')
  const waiting = card.status === 'proposed'
  const known = knownTool(card.tool)

  const decide = async (action: 'confirm' | 'reject') => {
    if (pressing) return
    setPressing(action)
    setProblem('')
    try {
      await (action === 'confirm' ? confirmProposal(card.id) : rejectProposal(card.id))
    } catch (error) {
      const refusal = proposalRefusalOf(error)
      setProblem(
        refusal
          ? t(`assistant.proposal.refusal.${refusal.reason}`)
          : problemText(t, error, t('assistant.proposal.failed')),
      )
    } finally {
      await refresh()
      setPressing(null)
    }
  }

  return (
    // 等人按的那幾張線變重（Cards / Containers：需要注意時換 `rule-strong`，不是變紅）。
    <section
      aria-labelledby={id}
      className={`border-2 ${waiting ? 'border-rule-strong' : 'border-rule'}`}
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b-2 border-rule bg-deck px-3 py-2">
        <h3 id={id} className="label mr-auto text-ink">
          {known ? t(TITLES[known]) : t('assistant.proposal.tool.other')}
        </h3>
        <StatusChip card={card} />
      </div>
      <div className="grid gap-3 px-3 py-2.5">
        <Preview type={card.preview_type} preview={card.preview} />
        {card.reason && (
          <p className="text-xs break-words text-ink-dim">
            <span className="label text-ink-dim">{t('assistant.proposal.reason')}</span>{' '}
            {card.reason}
          </p>
        )}
        {waiting && (
          <div className="grid gap-2">
            <div className={CONFIRM_ACTIONS}>
              <PrimaryButton
                type="button"
                busy={pressing !== null || replying}
                onClick={() => void decide('confirm')}
              >
                {pressing === 'confirm'
                  ? t('assistant.proposal.confirming')
                  : known
                    ? t(CONFIRMS[known])
                    : t('assistant.proposal.confirm.other')}
              </PrimaryButton>
              <GhostButton
                type="button"
                busy={pressing !== null || replying}
                onClick={() => void decide('reject')}
              >
                {t('assistant.proposal.reject')}
              </GhostButton>
            </div>
            {replying && <p className="text-xs text-ink-dim">{t('assistant.proposal.wait')}</p>}
          </div>
        )}
        {/* 一直掛著：按下去之後的結果與被拒的理由由它念（跟著結果才掛上去的 live region 多數閱讀器不念）。 */}
        <div role="status" className="text-xs break-words text-ink empty:hidden">
          {!waiting && <Outcome card={card} />}
          {problem}
        </div>
      </div>
    </section>
  )
}

function StatusChip({ card }: { card: ProposalCard }) {
  const { t } = useTranslation()
  // 等人按的是 `assigned`（需要你）；按過的是常態，不塗漆（The Usual Stays Unpainted Rule）。只有確認之後
  // Berth 自己出錯的那一種是 `blocked`。
  const failed = card.status === 'confirmed' && card.result_type === 'Refusal'
  const fill =
    card.status === 'proposed'
      ? SIGNAL_FILL.assigned
      : failed
        ? SIGNAL_FILL.blocked
        : 'bg-deck text-ink border-2 border-rule'
  return (
    <span className={`label px-1.5 py-0.5 ${fill}`}>
      {failed
        ? t('assistant.proposal.status.failed')
        : t(`assistant.proposal.status.${card.status}`)}
    </span>
  )
}

function Preview({ type, preview }: { type: string; preview: Record<string, unknown> }) {
  const { t } = useTranslation()
  if (!Object.hasOwn(PREVIEWS, type)) {
    return <p className="text-xs text-ink-dim">{t('assistant.cards.unknown')}</p>
  }
  // 依 `type` 取出的那一格與 `preview` 的形狀，TypeScript 對不起來（相關聯的聯集）；`type` 是後端照同一份
  // 登記寫的（同 `ResultCard`）。畫到一半丟錯的由外層的 ErrorBoundary 接住。
  const View = PREVIEWS[type as ProposalPreviewType] as ComponentType<{ preview: unknown }>
  return <View preview={preview} />
}

function IndexerAdditionView({ preview }: { preview: IndexerAddition }) {
  const { t } = useTranslation()
  return (
    <div className="grid gap-2">
      <p className="text-sm text-ink">
        {t('assistant.proposal.indexer.what', { name: preview.name })}
      </p>
      <dl className="grid gap-1.5 bg-hull px-3 py-2">
        <Line term={t('assistant.proposal.indexer.url')}>
          {preview.url || t('assistant.proposal.indexer.noUrl')}
        </Line>
        <Line term={t('assistant.proposal.indexer.prowlarr')}>
          {preview.prowlarr} <Dot /> {t(`assistant.proposal.indexer.origin.${preview.origin}`)}
        </Line>
        {preview.description && (
          <Line term={t('assistant.proposal.indexer.description')}>{preview.description}</Line>
        )}
      </dl>
      <p className="text-xs text-ink-dim">{t('assistant.proposal.indexer.then')}</p>
    </div>
  )
}

function DownloadsDeletionView({ preview }: { preview: DownloadsDeletion }) {
  const { t, i18n } = useTranslation()
  const title = (i18n.language === 'en' ? preview.title_en : preview.title) || preview.media
  return (
    <div className="grid gap-2">
      <p className="text-sm text-ink">{t('assistant.proposal.downloads.what', { title })}</p>
      <p className="text-xs text-ink-dim">{t('assistant.proposal.downloads.keeps')}</p>
      <ul className="grid gap-2">
        {preview.jobs.map((job) => (
          <li key={job.hash} className="grid gap-1 bg-hull px-3 py-2">
            <p className="value text-xs wrap-anywhere text-ink">{job.name}</p>
            {job.files.length === 0 ? (
              <p className="text-xs text-ink-dim">{t('assistant.proposal.downloads.noFiles')}</p>
            ) : (
              <ul aria-label={t('assistant.proposal.downloads.files', { name: job.name })}>
                {job.files.map((file) => (
                  <li key={file} className="value text-xs wrap-anywhere text-ink-dim">
                    {file}
                  </li>
                ))}
              </ul>
            )}
            <p className="value text-xs text-ink-dim">
              {t('assistant.proposal.downloads.count', { count: job.files.length })}
              {job.missing > 0 && (
                <>
                  {' '}
                  <Dot /> {t('assistant.proposal.downloads.missing', { count: job.missing })}
                </>
              )}
              {job.bytes > 0 && (
                <>
                  {' '}
                  <Dot /> {formatSize(job.bytes, i18n.language)}
                </>
              )}
            </p>
            {job.bytes > 0 && (
              <p className="text-xs text-ink">
                {job.reclaimable > 0
                  ? t('assistant.proposal.downloads.frees', {
                      size: formatSize(job.reclaimable, i18n.language),
                    })
                  : t('assistant.proposal.downloads.freesNothing')}
              </p>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}

function Line({ term, children }: { term: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-0.5 sm:grid-cols-[6rem_minmax(0,1fr)] sm:gap-2">
      <dt className="label text-ink-dim">{term}</dt>
      <dd className="value text-xs wrap-anywhere text-ink">{children}</dd>
    </div>
  )
}

/** 按過之後怎麼了：做了什麼（後端回報的，不是按鈕的回聲）、為什麼沒做成，或拒絕了。 */
function Outcome({ card }: { card: ProposalCard }) {
  const { t, i18n } = useTranslation()
  const result = card.result ?? {}
  if (card.status === 'rejected') return <>{t('assistant.proposal.outcome.rejected')}</>
  if (card.result_type === 'Refusal') {
    const reason = typeof result.reason === 'string' ? result.reason : ''
    return (
      <>
        {card.status === 'expired'
          ? t('assistant.proposal.outcome.expired')
          : t('assistant.proposal.outcome.failed')}{' '}
        {lapseText(t, reason)}
      </>
    )
  }
  if (card.result_type === 'IndexerAdded') {
    return <>{t('assistant.proposal.outcome.indexerAdded', { name: String(result.name ?? '') })}</>
  }
  if (card.result_type === 'DownloadsDeleted' && Array.isArray(result.jobs)) {
    const jobs = result.jobs as {
      hash: string
      name: string
      sources: number
      freed: number
      refused: string
    }[]
    return (
      <ul className="grid gap-1">
        {jobs.map((job) => (
          <li key={job.hash} className="wrap-anywhere">
            {job.refused
              ? t('assistant.proposal.outcome.jobRefused', { name: job.name, reason: job.refused })
              : t('assistant.proposal.outcome.jobDeleted', {
                  count: job.sources,
                  size: formatSize(job.freed, i18n.language),
                })}
          </li>
        ))}
      </ul>
    )
  }
  return <>{t('assistant.proposal.outcome.done')}</>
}

/** 失效的理由有人話的那幾種；其餘照原樣印理由碼（機器字串）。 */
const LAPSES = {
  not_allowed: 'assistant.proposal.lapse.not_allowed',
  unknown_tool: 'assistant.proposal.lapse.unknown_tool',
  invalid_input: 'assistant.proposal.lapse.invalid_input',
  internal_error: 'assistant.proposal.lapse.internal_error',
  site_present: 'assistant.proposal.lapse.site_present',
  site_rejected: 'assistant.proposal.lapse.site_rejected',
  prowlarr_unreachable: 'assistant.proposal.lapse.prowlarr_unreachable',
  nothing_to_delete: 'assistant.proposal.lapse.nothing_to_delete',
  job_gone: 'assistant.proposal.lapse.job_gone',
} as const

function lapseText(t: TFunction, reason: string): string {
  return Object.hasOwn(LAPSES, reason) ? t(LAPSES[reason as keyof typeof LAPSES]) : reason
}

type ProposalTool = keyof typeof TITLES

function knownTool(tool: string): ProposalTool | null {
  return Object.hasOwn(TITLES, tool) ? (tool as ProposalTool) : null
}
