import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import {
  ignoreIssue,
  issuesQueryOptions,
  parseIssueRefusal,
  resolveIssue,
  type Issue,
  type IssueAction,
} from '../api/issues'
import { reviewQueryOptions } from '../api/review'
import { ConfirmAction, GhostButton } from '../components/controls'
import { DetailLine, QueueRow } from '../components/QueueRow'
import { JobLink } from '../jobs/JobLink'
import { formatJellyfinEpisode } from '../components/episodes'
import { fileName, whenText } from '../components/queueText'
import { formatSize } from '../media/searchResult'
import { WorkPicker } from './WorkPicker'

/**
 * 待處理清單上的一列（`.scratch/m2/issues-shape.md`，M2 票 05）。
 *
 * **一列一件事**：一個型別色塊、一句話、一組按得下去的動作。骨架是 `QueueRow`（票 06 抽出來的，
 * 那時手上有這一列與 `AuditRow` 兩個真實案例）。M3 票 05 起只在 `/issues`：`/review` 不再列 Issue，
 * 只帶一個數字（它的佇列裡的 `issues_open`）。
 *
 * **按鈕照後端給的 `actions` 畫**，前端不重算一份規則：按得了什麼要看型別**與**這一筆的資料
 * （指不到帳本的按不了重新鏈接，沒有 Job 的按不了「連 complete 一起刪」）。那個判斷在
 * `services/issues._actions`，只有一份。
 *
 * **失敗的時候這一列留著**：後端做不到就不會把它記成 `resolved`，所以清單上它還在，旁邊多
 * 一句為什麼。畫面說修好了而媒體庫沒變，是這一票最糟的結果。
 */
export function IssueRow({
  issue,
  onDone,
}: {
  issue: Issue
  /** 按成之後那一列會從清單上消失，這一句給看不見畫面的人（`/issues` 的 `aria-live`）。 */
  onDone: (said: string) => void
}) {
  const { t, i18n } = useTranslation()
  const queryClient = useQueryClient()
  const [refusal, setRefusal] = useState<string | null>(null)

  // `/review` 原位那一行「另有 N 件待處理」數的是同一份，按完兩份都要重問。
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: issuesQueryOptions().queryKey })
    void queryClient.invalidateQueries({ queryKey: reviewQueryOptions().queryKey })
  }
  const act = useMutation({
    mutationFn: ({ action, media = '' }: { action: IssueAction | 'ignore'; media?: string }) =>
      action === 'ignore' ? ignoreIssue(issue.id) : resolveIssue(issue.id, action, media),
    onMutate: () => setRefusal(null),
    // 決定過的那一件從清單上消失（兩份都只列 `open`），而對帳的摘要數字不變——
    // 它說的是「那一輪發現了什麼」，不是「現在還剩幾件」。
    onSuccess: () => {
      onDone(t('issues.done'))
      refresh()
      // 修好的是媒體庫裡的檔案：Media 詳情的入庫狀態跟著變，那一份 5 分鐘內不重抓（M3 票 06）。
      void queryClient.invalidateQueries({ queryKey: ['media'] })
    },
    onError: (error) => {
      const said = parseIssueRefusal(error)
      setRefusal(said ? refusalText(t, said.reason, said.detail) : t('issues.failed'))
      // 另一個分頁先按了、或那一顆已經不適用：重問一次，清單才說得出現在的樣子。
      refresh()
    },
  })

  const busy = act.isPending
  const source = text(issue.detail.source)
  // 沒有路徑的那幾種（無主 torrent、帳本為空）以 torrent 的名字認，最後才退回冪等鍵。
  // TVDB 那一種以 Route 的名字認：它的路徑是 Route 的目標，檔名那一段只是一個 slug。
  const name = text(issue.detail.route) || text(issue.detail.name)

  return (
    <QueueRow
      label={t(`issues.typeLabel.${issue.type}`)}
      title={
        issue.type === 'library_uses_tvdb'
          ? name || issue.subject
          : fileName(issue.path) || name || issue.subject
      }
      sentence={t(`issues.type.${issue.type}`)}
      when={t('issues.detectedAt', { value: whenText(issue.detected_at, i18n.language) })}
      refusal={refusal}
      details={
        // 完整路徑與來源。掃視的時候只看得到檔名——路徑會把一列撐成三行，而這一頁的工作
        // 是「決定」不是「讀路徑」。
        <>
          {issue.path !== '' && (
            <DetailLine term={t(PATH_TERM[issue.type] ?? 'issues.target')}>{issue.path}</DetailLine>
          )}
          {source !== '' && <DetailLine term={t('issues.source')}>{source}</DetailLine>}
          {issue.job_hash !== '' && (
            <DetailLine term={t('issues.job')}>
              {/* 無主的 torrent 在這一格放的是那個 torrent 的 hash——它定義上沒有 Job，連過去一定是空的。 */}
              {issue.type === 'unknown_torrent' ? (
                issue.job_hash
              ) : (
                <JobLink hash={issue.job_hash}>{issue.job_hash}</JobLink>
              )}
            </DetailLine>
          )}
          <Measured issue={issue} />
        </>
      }
    >
      {issue.actions.map((action) => {
        const confirm = CONFIRM[action]
        if (confirm === 'work') {
          return (
            <WorkPicker
              key={action}
              label={t(`issues.action.${action}`)}
              initialQuery={issue.query}
              pending={busy}
              pendingLabel={t('issues.working')}
              onPick={(media) => act.mutate({ action, media })}
            />
          )
        }
        return confirm !== null ? (
          <ConfirmAction
            key={action}
            label={t(`issues.action.${action}`)}
            confirmLabel={t(confirm.action)}
            warning={t(confirm.warning)}
            pending={busy}
            pendingLabel={t('issues.working')}
            onConfirm={() => act.mutate({ action })}
          />
        ) : (
          <GhostButton
            key={action}
            type="button"
            busy={busy}
            onClick={() => act.mutate({ action })}
          >
            {busy ? t('issues.working') : t(`issues.action.${action}`)}
          </GhostButton>
        )
      })}
      {/* 忽略永遠在：一件按不了任何一顆的 Issue 仍然要能從清單上收掉。 */}
      <GhostButton type="button" busy={busy} onClick={() => act.mutate({ action: 'ignore' })}>
        {busy ? t('issues.working') : t('issues.action.ignore')}
      </GhostButton>
    </QueueRow>
  )
}

/**
 * 會刪掉磁碟上東西的那幾顆（後端的 `ACTION_DELETES`）要就地二次確認，並說清楚刪的是什麼。
 * **總表**：後端加一顆而這裡沒回答它要不要確認，`tsc` 會紅。
 *
 * - 「連 complete 一起刪」的**單位是整筆下載**（brief §9.2）。就地確認而不是票 04 的四旗標
 *   對話框：那四個旗標是這一顆自己寫死的。
 * - 「刪除這個目錄」刪的是 complete 底下一整棵，後端按下去那一刻會再確認它仍然沒有主。
 * - 「以硬鏈接取代」會讓媒體庫那一份複製品消失——一樣大，但它可能是別人改過的版本。
 *
 * `'work'` 是認領類的兩顆（後端的 `NEEDS_MEDIA`，M2 票 10）：按下去先選作品，選好之後的主動作
 * 本身就是第二次確認。它們一個位元組都不刪。
 */
const CONFIRM = {
  relink: null,
  forget: null,
  delete_complete: { warning: 'issues.confirmDelete', action: 'issues.confirmDeleteAction' },
  mark_sourceless: null,
  replace_with_link: { warning: 'issues.confirmReplace', action: 'issues.confirmReplaceAction' },
  delete_orphan: { warning: 'issues.confirmDeleteOrphan', action: 'issues.confirmDeleteAction' },
  replan: null,
  relook: null,
  rescan: null,
  // 管線那三種一顆都不刪東西：兩顆「承認」讓那一筆下載結束，磁碟與 qBittorrent 都不動。
  recheck: null,
  accept_loss: null,
  retry: null,
  resubmit: null,
  accept_removal: null,
  adopt: 'work',
  claim_torrent: 'work',
  // 認領進帳本只多一列帳本，配不上就是拒絕，什麼都不寫。
  claim_file: null,
} as const satisfies Record<IssueAction, { warning: string; action: string } | 'work' | null>

/** 路徑那一欄叫什麼。沒列的是媒體庫裡的路徑（帳本的目標、Route 的目標）。 */
const PATH_TERM: Partial<Record<Issue['type'], 'issues.completePath' | 'issues.measuredPath'>> = {
  orphan_complete: 'issues.completePath',
  low_disk_space: 'issues.measuredPath',
}

/**
 * 健康檢查那兩種與回驗不符（M2 票 09c、M3 票 17）的實測值與下一步。它們的修法不在 Berth 裡，
 * 所以列上要說得出去哪裡修、修好之後會怎樣（PRODUCT 原則 4）——不能只有一句型別。
 */
function Measured({ issue }: { issue: Issue }) {
  const { t, i18n } = useTranslation()
  if (issue.type === 'library_uses_tvdb') {
    const fetchers = Array.isArray(issue.detail.fetchers) ? issue.detail.fetchers.map(text) : []
    return (
      <>
        <DetailLine term={t('issues.library')}>{text(issue.detail.library)}</DetailLine>
        <DetailLine term={t('issues.fetchers')}>{fetchers.join(', ')}</DetailLine>
        <DetailLine term={t('issues.next')}>{t('issues.nextTvdb')}</DetailLine>
      </>
    )
  }
  if (issue.type === 'unmanaged_library_file' && isClaimMiss(issue.detail.reason)) {
    // `rebuild-ledger` 開的那幾件帶著理由（`ClaimMiss`）；對帳開的沒有，那時不畫這一行。
    return (
      <DetailLine term={t('issues.unclaimedBecause')}>
        {t(`issues.claimMiss.${issue.detail.reason}`)}
      </DetailLine>
    )
  }
  if (issue.type === 'jellyfin_item_mismatch') {
    // Jellyfin 回驗（M3 票 17）：兩邊各自認成什麼，並排著讓人一眼看出差在哪。修法在 Jellyfin 裡，
    // 所以下一步也寫在列上。
    const differs = Array.isArray(issue.detail.differs)
      ? issue.detail.differs.filter(isDiffer).map((what) => t(`issues.differsWhat.${what}`))
      : []
    const reads = (value: unknown) => {
      const side = record(value)
      const episode = formatJellyfinEpisode({
        season: numeric(side.season),
        episode_start: numeric(side.episode_start),
        episode_end: numeric(side.episode_end),
      })
      const tmdb = text(side.tmdb)
      return [episode, tmdb === '' ? t('issues.noTmdb') : `TMDB ${tmdb}`]
        .filter(Boolean)
        .join(' · ')
    }
    return (
      <>
        <DetailLine term={t('issues.differs')}>{differs.join(t('issues.differsJoin'))}</DetailLine>
        <DetailLine term={t('issues.ledgerReads')}>{reads(issue.detail.ledger)}</DetailLine>
        <DetailLine term={t('issues.jellyfinReads')}>{reads(issue.detail.jellyfin)}</DetailLine>
        <DetailLine term={t('issues.next')}>{t('issues.nextMismatch')}</DetailLine>
      </>
    )
  }
  if (issue.type === 'low_disk_space') {
    const size = (value: unknown) =>
      typeof value === 'number' ? formatSize(value, i18n.language) : ''
    return (
      <>
        <DetailLine term={t('issues.free')}>{size(issue.detail.free)}</DetailLine>
        <DetailLine term={t('issues.minFree')}>{size(issue.detail.min_free)}</DetailLine>
        <DetailLine term={t('issues.next')}>{t('issues.nextDisk')}</DetailLine>
      </>
    )
  }
  return null
}

/** 配不上帳本的四種理由（後端的 `ClaimMiss`）。`unclaimable` 拒絕的 `detail` 也是它。 */
const CLAIM_MISSES = ['outside_routes', 'no_source', 'unknown_work', 'not_berth_naming'] as const

function isClaimMiss(value: unknown): value is (typeof CLAIM_MISSES)[number] {
  return CLAIM_MISSES.some((miss) => miss === value)
}

/** 回驗比的三件事（後端 `resolver.disagreement` 的 `differs`）。 */
const DIFFERS = ['season', 'episode', 'tmdb'] as const

function isDiffer(value: unknown): value is (typeof DIFFERS)[number] {
  return DIFFERS.some((what) => what === value)
}

function text(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

function numeric(value: unknown): number | null {
  return typeof value === 'number' ? value : null
}

function record(value: unknown): Record<string, unknown> {
  return typeof value === 'object' && value !== null ? { ...value } : {}
}

/** `relink_failed` 的原文是 errno 與「哪兩個掛載」（plan §8.6），所以它接在那一句後面。 */
function refusalText(
  t: (key: string) => string,
  reason: Parameters<typeof String>[0] & string,
  detail: string,
) {
  const said = t(`issues.refusal.${reason}`)
  // 配不上帳本的那一種，原文是 `ClaimMiss` 的值：換成說得出下一步的那一句。
  if (reason === 'unclaimable' && isClaimMiss(detail))
    return `${said} ${t(`issues.claimMiss.${detail}`)}`
  return detail === '' ? said : `${said} ${detail}`
}
