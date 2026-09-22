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
import { ConfirmAction, GhostButton, Notice } from '../components/controls'
import { Dot } from '../components/Dot'

/**
 * 待處理清單上的一列（`.scratch/m2/issues-shape.md`，M2 票 05）。
 *
 * **一列一件事**：一個型別色塊、一句話、一組按得下去的動作。排法與票 06 的 `/review` 一致，
 * 但**這一票不抽共用元件**（使用者 2026-09-22 拍板）——票 06 做 `/review` 時手上有兩個真實
 * 案例，那時候再把共用的那一列抽成 `QueueRow`。用一個案例猜介面會猜錯。
 *
 * **按鈕照後端給的 `actions` 畫**，前端不重算一份規則：按得了什麼要看型別**與**這一筆的資料
 * （指不到帳本的按不了重新鏈接，沒有 Job 的按不了「連 complete 一起刪」）。那個判斷在
 * `services/issues._actions`，只有一份。
 *
 * **失敗的時候這一列留著**：後端做不到就不會把它記成 `resolved`，所以清單上它還在，旁邊多
 * 一句為什麼。畫面說修好了而媒體庫沒變，是這一票最糟的結果。
 */
export function IssueRow({ issue }: { issue: Issue }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [refusal, setRefusal] = useState<string | null>(null)

  const act = useMutation({
    mutationFn: (action: IssueAction | 'ignore') =>
      action === 'ignore' ? ignoreIssue(issue.id) : resolveIssue(issue.id, action),
    onMutate: () => setRefusal(null),
    onSuccess: () => {
      // 決定過的那一件從清單上消失（`GET /issues` 只回 `open`），而對帳的摘要數字不變——
      // 它說的是「那一輪發現了什麼」，不是「現在還剩幾件」。
      void queryClient.invalidateQueries({ queryKey: issuesQueryOptions().queryKey })
    },
    onError: (error) => {
      const said = parseIssueRefusal(error)
      setRefusal(said ? refusalText(t, said.reason, said.detail) : t('issues.failed'))
      // 另一個分頁先按了、或那一顆已經不適用：重問一次，清單才說得出現在的樣子。
      void queryClient.invalidateQueries({ queryKey: issuesQueryOptions().queryKey })
    },
  })

  const busy = act.isPending
  const name = fileName(issue.path) || issue.subject

  return (
    <article className="grid gap-2 border-2 border-rule bg-well px-4 py-3">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        {/* **中性色塊**：型別是**分類**不是狀態（The Role Is Not A State Rule）——這一頁每一列
            都是 `open`，塗紅不區分任何東西，而紅色只代表阻擋（The One Meaning Rule）。
            不看顏色也讀得出來靠的是那幾個模板字，不是漆。 */}
        <span className="label bg-deck px-2 py-1.5 text-ink">
          {t(`issues.typeLabel.${issue.type}`)}
        </span>
        <h2 className="value min-w-0 wrap-anywhere text-ink">{name}</h2>
      </div>

      <p className="text-sm text-ink-dim">
        {t(`issues.type.${issue.type}`)}
        <Dot />
        <span className="value text-xs">
          {t('issues.detectedAt', { value: whenText(issue.detected_at) })}
        </span>
      </p>

      <Details issue={issue} />

      {refusal !== null && (
        <Notice signal="blocked" label={t('common.failed')}>
          {refusal}
        </Notice>
      )}

      <div className="flex flex-wrap items-start gap-2">
        {issue.actions.map((action) =>
          action === 'delete_complete' ? (
            // **單位是整筆下載，不是那一個檔案**（brief §9.2），所以它要二次確認並說清楚
            // 後果。就地確認而不是票 04 的四旗標對話框：那四個旗標是這一顆自己寫死的。
            <ConfirmAction
              key={action}
              label={t('issues.action.delete_complete')}
              confirmLabel={t('issues.confirmDeleteAction')}
              warning={t('issues.confirmDelete')}
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
          ),
        )}
        {/* 忽略永遠在：一件按不了任何一顆的 Issue 仍然要能從清單上收掉。 */}
        <GhostButton type="button" disabled={busy} onClick={() => act.mutate('ignore')}>
          {busy ? t('issues.working') : t('issues.action.ignore')}
        </GhostButton>
      </div>
    </article>
  )
}

/**
 * 完整路徑與來源。
 *
 * 掃視的時候只看得到檔名——路徑會把一列撐成三行，而這一頁的工作是「決定」不是「讀路徑」。
 * 要修的時候才需要它們，所以放在 `<details>` 裡。
 */
function Details({ issue }: { issue: Issue }) {
  const { t } = useTranslation()
  const source = typeof issue.detail.source === 'string' ? issue.detail.source : ''

  return (
    <details className="group">
      <summary className="label w-fit cursor-pointer text-ink-dim hover:text-ink">
        {t('common.expand')}
      </summary>
      <dl className="mt-2 grid gap-1 border-2 border-rule bg-hull px-3 py-2">
        <Line term={t('issues.target')} value={issue.path} />
        {source !== '' && <Line term={t('issues.source')} value={source} />}
        {issue.job_hash !== '' && <Line term={t('issues.job')} value={issue.job_hash} />}
      </dl>
    </details>
  )
}

/** 一格：欄名走 `.label`，值走 `.value`——路徑與 hash 是機器字串（The Machine String Rule）。 */
function Line({ term, value }: { term: string; value: string }) {
  return (
    <div className="grid gap-0.5 sm:grid-cols-[10rem_minmax(0,1fr)] sm:gap-2">
      <dt className="label text-ink-dim">{term}</dt>
      <dd className="value min-w-0 wrap-anywhere text-xs text-ink">{value}</dd>
    </div>
  )
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

/** `/a/b/c.mkv` → `c.mkv`。路徑是 POSIX 的（帳本記的那一串，`models/ledger.py`）。 */
function fileName(path: string) {
  const parts = path.split(/[\\/]/)
  return parts[parts.length - 1] ?? ''
}

function whenText(value: string) {
  const at = new Date(value)
  return Number.isNaN(at.getTime()) ? value : at.toLocaleString()
}
