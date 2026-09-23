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
import { fileName, whenText } from '../components/queueText'
import { formatSize } from '../media/searchResult'

/**
 * 待處理清單上的一列（`.scratch/m2/issues-shape.md`，M2 票 05）。
 *
 * **一列一件事**：一個型別色塊、一句話、一組按得下去的動作。骨架是 `QueueRow`（票 06 抽出來的，
 * 那時手上有這一列與 `AuditRow` 兩個真實案例）；`/issues` 與 `/review` 畫的是同一個元件。
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
  heading = 'h2',
  onDone,
}: {
  issue: Issue
  heading?: 'h2' | 'h3'
  /** 按成之後那一列會從清單上消失，這一句給看不見畫面的人（`/review` 的 `aria-live`）。 */
  onDone?: (said: string) => void
}) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [refusal, setRefusal] = useState<string | null>(null)

  // 同一件事住在兩份清單上（`/issues` 與 `/review`），按完兩份都要重問，另一頁才不會還列著它。
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: issuesQueryOptions().queryKey })
    void queryClient.invalidateQueries({ queryKey: reviewQueryOptions().queryKey })
  }
  const act = useMutation({
    mutationFn: (action: IssueAction | 'ignore') =>
      action === 'ignore' ? ignoreIssue(issue.id) : resolveIssue(issue.id, action),
    onMutate: () => setRefusal(null),
    // 決定過的那一件從清單上消失（兩份都只列 `open`），而對帳的摘要數字不變——
    // 它說的是「那一輪發現了什麼」，不是「現在還剩幾件」。
    onSuccess: () => {
      onDone?.(t('issues.done'))
      refresh()
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
      heading={heading}
      sentence={t(`issues.type.${issue.type}`)}
      when={t('issues.detectedAt', { value: whenText(issue.detected_at) })}
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
            <DetailLine term={t('issues.job')}>{issue.job_hash}</DetailLine>
          )}
          <Measured issue={issue} />
        </>
      }
    >
      {issue.actions.map((action) => {
        const confirm = CONFIRM[action]
        return confirm !== null ? (
          <ConfirmAction
            key={action}
            label={t(`issues.action.${action}`)}
            confirmLabel={t(confirm.action)}
            warning={t(confirm.warning)}
            pending={busy}
            pendingLabel={t('issues.working')}
            onConfirm={() => act.mutate(action)}
          />
        ) : (
          <GhostButton
            key={action}
            type="button"
            disabled={busy}
            onClick={() => act.mutate(action)}
          >
            {busy ? t('issues.working') : t(`issues.action.${action}`)}
          </GhostButton>
        )
      })}
      {/* 忽略永遠在：一件按不了任何一顆的 Issue 仍然要能從清單上收掉。 */}
      <GhostButton type="button" disabled={busy} onClick={() => act.mutate('ignore')}>
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
} as const satisfies Record<IssueAction, { warning: string; action: string } | null>

/** 路徑那一欄叫什麼。沒列的是媒體庫裡的路徑（帳本的目標、Route 的目標）。 */
const PATH_TERM: Partial<Record<Issue['type'], 'issues.completePath' | 'issues.measuredPath'>> = {
  orphan_complete: 'issues.completePath',
  low_disk_space: 'issues.measuredPath',
}

/**
 * 健康檢查那兩種的實測值與下一步（M2 票 09c）。它們沒有 Berth 按得了的修法，所以列上要說得出
 * 去哪裡修、修好之後會怎樣（PRODUCT 原則 4）——只剩一顆「忽略」的列不能只有一句型別。
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

function text(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

/** `relink_failed` 的原文是 errno 與「哪兩個掛載」（plan §8.6），所以它接在那一句後面。 */
function refusalText(
  t: (key: string) => string,
  reason: Parameters<typeof String>[0] & string,
  detail: string,
) {
  const said = t(`issues.refusal.${reason}`)
  return detail === '' ? said : `${said} ${detail}`
}
