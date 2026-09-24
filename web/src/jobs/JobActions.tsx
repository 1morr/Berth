import { useMutation, useQueryClient, type UseMutationResult } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { reimportJob, retryJob, refusalOf, type Job } from '../api/jobs'
import { replanJob } from '../api/plans'
import { GhostButton } from '../components/controls'
import { JobDelete } from './JobDelete'

/**
 * 一筆 Job 的動作：重新規劃、重試、重新入庫、刪除範圍（brief §13、M2 票 12）。
 *
 * **只住在詳情頁**（`.scratch/m2/job-detail-shape.md`，使用者拍板）：`/jobs` 的展開區只剩狀態與時間線
 * 摘要，一筆 Job 的動作只有一個家。哪一顆出現由後端的旗標決定（`retryable`、`replannable`、
 * `reimportable`），前端不重算規則——`replannable` 已經依按的人算過（停在審核的那一筆只有 admin，
 * M3 票 04）；重新入庫與刪除另外只給 admin——**前端隱藏不是安全機制**，擋住的那一條在門禁上
 * （`api/gate.py` 的 `ADMIN_ROUTES`）。
 *
 * 刪除排在最後、自己一整行：它是這一塊裡唯一不可回復的動作，確認區就地展開在身分帶正下方，
 * 展開時畫面上方就是這一筆的名字。它是票 04 的那一個元件，Media 詳情的版本清單掛的也是它。
 */
export function JobActions({ job, isAdmin }: { job: Job; isAdmin: boolean }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const onSuccess = async () => {
    await queryClient.invalidateQueries({ queryKey: ['jobs'] })
  }
  const retry = useMutation({ mutationFn: () => retryJob(job.hash), onSuccess })
  const replan = useMutation({ mutationFn: () => replanJob(job.hash), onSuccess })
  const reimport = useMutation({ mutationFn: () => reimportJob(job.hash), onSuccess })

  // 同一個端點、兩種重試（plan §3.1）：送單失敗是「再送一次」，入庫失敗是「從沒鏈接的那幾個
  // 接著做」。按鈕上的字要說得出是哪一種，按下去之前才知道會發生什麼。
  const importRetry = job.state === 'import_failed'
  const state = t(`jobs.state.${job.state}`)

  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-start gap-2">
        {job.replannable && (
          <Action
            run={replan}
            idle={t('jobs.plan.replan')}
            busy={t('jobs.plan.replanning')}
            off={t('jobs.plan.replanOff')}
          />
        )}
        {job.retryable && (
          <Action
            run={retry}
            idle={importRetry ? t('jobs.retryImport') : t('jobs.retry')}
            busy={importRetry ? t('jobs.retryingImport') : t('jobs.retrying')}
            off={t('jobs.retryOff')}
          />
        )}
        {/* 重新入庫會動媒體庫，只有 admin（M2 票 10）。以 complete 裡那一包為來源，torrent 不在了
            也按得了——那正是它存在的理由（brief §9.3）。 */}
        {job.reimportable && isAdmin && (
          <Action
            run={reimport}
            idle={t('jobs.reimport')}
            busy={t('jobs.reimporting')}
            off={t('jobs.reimportOff')}
          />
        )}
      </div>
      {/* 確認區在寬版上不拉滿整頁：四個勾與它們的後果是一段要讀的說明，不是一張表。 */}
      {isAdmin && (
        <div className="max-w-3xl">
          <JobDelete hash={job.hash} />
        </div>
      )}
      {/* 成功時畫面上動的只有狀態色塊，看不見畫面的人得知道發生了什麼。 */}
      <p aria-live="polite" className="sr-only">
        {retry.isSuccess ? t('jobs.retried', { state }) : ''}
        {replan.isSuccess ? t('jobs.plan.replanned', { state }) : ''}
        {reimport.isSuccess ? t('jobs.reimported', { state }) : ''}
      </p>
    </div>
  )
}

/**
 * 一顆次要動作按鈕，加上它失敗時那一句話。
 *
 * 重試、重新規劃與重新入庫的形狀一模一樣，所以它們是同一個元件：**按鈕永遠按得下去，只換文字**
 * （票 02b；送出中按了不再送，M3 票 06），失敗時說的是那個封閉集合的理由而不是一句通用的話（PRODUCT 原則 4），
 * 認不得的理由才落回 `off`。
 */
function Action({
  run,
  idle,
  busy,
  off,
}: {
  run: UseMutationResult<Job, Error, void, unknown>
  idle: string
  busy: string
  off: string
}) {
  const { t } = useTranslation()
  const refusal = refusalOf(run.error)

  return (
    <div className="grid justify-items-start gap-2">
      <GhostButton type="button" busy={run.isPending} onClick={() => run.mutate()}>
        {run.isPending ? busy : idle}
      </GhostButton>
      {run.isError && (
        <p role="alert" className="max-w-prose text-xs text-blocked-ink">
          {refusal ? t(`jobs.refusal.${refusal.reason}`) : off}
        </p>
      )}
    </div>
  )
}
