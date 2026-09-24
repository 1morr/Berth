import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import {
  issuesQueryOptions,
  parseIssueRefusal,
  reconcileQueryOptions,
  startReconcile,
  type ReconcileRun,
  type ReconcileSideReport,
} from '../api/issues'
import { GhostButton, Notice } from '../components/controls'
import { Dot } from '../components/Dot'
import { whenText } from '../components/queueText'

/**
 * 待處理頁抬頭下面那一條（`.scratch/m2/issues-shape.md`，M2 票 05）。
 *
 * 一顆「立刻對帳」，按下之後**同一條橫幅**就地展開四方的進度（使用者 2026-09-22 拍板）：
 * 不跳頁、不開面板。跑完收成一行摘要。
 *
 * **問不到的那一方用文字說出來**，不是安靜地少一列（brief §16.2）：畫面要分得出「都好好的」
 * 與「根本沒比」——後者的下一步是去修那台服務或那一行 volume，前者沒有下一步。
 */
export function ReconcileBanner() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [failed, setFailed] = useState<string | null>(null)
  // 跑的時候才輪詢（`reconcileQueryOptions` 的 `refetchInterval`）：對帳一天一輪，
  // 平常每秒問一次是在問一個不會變的答案。
  const state = useQuery(reconcileQueryOptions())
  const current = state.data?.current ?? null
  const last = state.data?.last ?? null

  const start = useMutation({
    mutationFn: startReconcile,
    onMutate: () => setFailed(null),
    onSuccess: (run) => {
      // 立刻把它畫成「跑的時候」，不等下一次輪詢——按下去要馬上看得到反應。
      queryClient.setQueryData(reconcileQueryOptions().queryKey, { current: run, last })
    },
    onError: (error) => {
      const said = parseIssueRefusal(error)
      setFailed(said ? t(`issues.refusal.${said.reason}`) : t('reconcile.failed'))
      void queryClient.invalidateQueries({ queryKey: reconcileQueryOptions().queryKey })
    },
  })

  const running = current !== null
  // **一輪跑完就重問清單一次**：那一輪開出來的 Issue 要出現在下面。
  //
  // 掛在 `useEffect` 而不是寫在 render 裡：render 期間 invalidate 會讓 refetch → 重繪 →
  // 條件仍然成立 → 再 invalidate，一直打 `/issues`。認的是「`last` 換了一輪」而不是
  // 「剛剛按過」——每日 04:00 那一輪沒有人按，它開出來的東西一樣要出現。
  const seen = useRef<number | null>(null)
  const finished = last?.id ?? null
  useEffect(() => {
    if (finished === null || seen.current === finished) return
    seen.current = finished
    void queryClient.invalidateQueries({ queryKey: issuesQueryOptions().queryKey })
  }, [finished, queryClient])

  return (
    <div className="grid gap-2">
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
        <p className="value text-xs text-ink-dim">
          {last ? <Summary run={last} /> : t('reconcile.neverRun')}
        </p>
        {/* **送出中不用 `disabled`**（M1.5 票 05 實跑抓到）：停用的鍵接不住焦點，
            鍵盤使用者會掉回 `body`。 */}
        <GhostButton
          type="button"
          aria-disabled={running || start.isPending}
          onClick={() => {
            if (running || start.isPending) return
            start.mutate()
          }}
        >
          {running || start.isPending ? t('reconcile.running') : t('reconcile.start')}
        </GhostButton>
      </div>

      {failed !== null && (
        <Notice signal="blocked" label={t('common.failed')}>
          {failed}
        </Notice>
      )}

      {/* 跑的時候逐方填進來；跑完之後留著上一輪的四方，那是「它問到了嗎」的答案。 */}
      <Sides run={current ?? last} live={running} />
    </div>
  )
}

function Summary({ run }: { run: ReconcileRun }) {
  const { t, i18n } = useTranslation()
  return (
    <>
      {/* 行內的 `Dot` 前後空白要自己給，JSX 換行會吞掉它（同 `QueueRow`）。 */}
      {t('reconcile.lastRun', { time: whenText(run.started_at, i18n.language) })} <Dot />{' '}
      {t('reconcile.opened', { count: run.opened })} <Dot />{' '}
      {t('reconcile.updated', { count: run.updated })}
    </>
  )
}

/**
 * 四方各一列。
 *
 * `aria-live="polite"`：跑的時候這幾列一個一個長出來，而按下按鈕的人可能正在用螢幕閱讀器。
 */
function Sides({ run, live }: { run: ReconcileRun | null; live: boolean }) {
  const { t } = useTranslation()
  if (run === null || run.sides.length === 0) return null

  return (
    <ul
      className="grid gap-px border-2 border-rule bg-rule"
      aria-label={t('reconcile.sides')}
      aria-live={live ? 'polite' : 'off'}
    >
      {run.sides.map((side) => (
        <li key={side.side}>
          <Side side={side} />
        </li>
      ))}
    </ul>
  )
}

function Side({ side }: { side: ReconcileSideReport }) {
  const { t } = useTranslation()
  const asked = side.unavailable === ''

  return (
    <div className="grid gap-1 bg-well px-3 py-2 sm:grid-cols-[8rem_minmax(0,1fr)] sm:gap-3">
      <p className="label text-ink-dim">{t(`reconcile.side.${side.side}`)}</p>
      <div className="grid gap-1">
        {asked ? (
          <p className="value text-xs text-ink">
            {t('reconcile.counted', { count: side.counted })}
          </p>
        ) : (
          // **不是 0 筆，是沒問到。** 兩者的下一步不同，所以它們長得不一樣。
          <p className="text-xs text-blocked-ink">
            <span className="label">{t('reconcile.unavailable')}</span>
            <Dot />
            <span className="value">{side.unavailable}</span>
          </p>
        )}
        {side.skipped.map((line) => (
          <p key={line} className="value text-xs text-ink-dim">
            {t('reconcile.skipped', { value: line })}
          </p>
        ))}
      </div>
    </div>
  )
}
