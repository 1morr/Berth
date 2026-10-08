import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useId } from 'react'
import { useTranslation } from 'react-i18next'

import {
  issuesQueryOptions,
  ledgerGapQueryOptions,
  parseIssueRefusal,
  rebuildLedger,
  type RebuildReport,
} from '../api/issues'
import { GhostButton, Notice } from '../components/controls'
import { TechnicalDetails } from '../components/TechnicalDetails'

/**
 * 「從媒體庫重建帳本」（M4 票 60，`.scratch/m4/ledger-rebuild-shape.md`）：待處理頁最上面與精靈完成頁共用。
 *
 * 重裝或 DB 遺失之後，媒體庫的檔案都在、帳本是空的。這一塊只在偵測到時出現：說有幾個、為什麼會這樣，
 * 一顆按鈕跑與 `berth rebuild-ledger` 同一個命令，底下一行說後果（只加不刪、可以重按、配不上的不猜）。
 * 按完就地換成結果；結果留到離開頁面，提示本身在重新偵測到 0 時就不畫了。
 *
 * 偵測失敗時什麼都不畫：這是一個提示，不是這一頁的主角，問不到時不該擋住底下的清單。
 */
export function LedgerGapNotice({
  heading: Heading = 'h2',
  className = '',
}: {
  /** 待處理頁的 h1 之下是 h2；精靈完成頁那一步自己的標題就是 h2，所以在那裡是 h3。 */
  heading?: 'h2' | 'h3'
  className?: string
}) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const headingId = useId()
  const gap = useQuery(ledgerGapQueryOptions())

  const rebuild = useMutation({
    mutationFn: rebuildLedger,
    onSuccess: () => {
      // 清單（配不上的那幾件）、偵測本身（鍵在 `['issues']` 底下）與作品頁的檔案清單都換了。
      void queryClient.invalidateQueries({ queryKey: issuesQueryOptions().queryKey })
      void queryClient.invalidateQueries({ queryKey: ['media'] })
    },
  })

  const unknown = gap.data?.unknown ?? 0
  if (unknown === 0 && rebuild.isIdle) return null

  const refusal = rebuild.isError ? parseIssueRefusal(rebuild.error) : null

  return (
    <section
      aria-labelledby={headingId}
      className={`grid gap-3 border-2 border-rule-strong bg-well px-4 py-3 ${className}`}
    >
      <Heading id={headingId} className="label text-ink">
        {t('ledgerGap.title')}
      </Heading>

      {!rebuild.isSuccess && (
        <>
          <p className="max-w-prose text-sm text-ink">{t('ledgerGap.found', { count: unknown })}</p>
          <div>
            <GhostButton type="button" busy={rebuild.isPending} onClick={() => rebuild.mutate()}>
              {rebuild.isPending ? t('ledgerGap.running') : t('ledgerGap.start')}
            </GhostButton>
          </div>
          <p className="max-w-prose text-xs text-ink-dim">{t('ledgerGap.effect')}</p>
        </>
      )}

      {rebuild.isError && (
        <Notice signal="blocked" label={t('common.failed')}>
          {refusal ? t(`issues.refusal.${refusal.reason}`) : t('ledgerGap.failed')}
        </Notice>
      )}

      {/* live region 要一直在才唸得到後來長進去的結果；空的時候 `absolute`，不佔 grid 的一格與間距
          （`hidden` 會把它拿出無障礙樹）。 */}
      <div aria-live="polite" className="empty:absolute">
        {rebuild.data && <Outcome report={rebuild.data} />}
      </div>
    </section>
  )
}

/** 找回幾個、幾個變成非受管檔案；有地方讀不到時另說一句，原文收進技術細節。 */
function Outcome({ report }: { report: RebuildReport }) {
  const { t } = useTranslation()
  const unmatched = Object.values(report.unmatched).reduce((sum, count) => sum + (count ?? 0), 0)
  const unread = [...report.skipped, ...report.unread_complete]

  return (
    <div className="grid gap-1 text-sm text-ink">
      {report.claimed > 0 && <p>{t('ledgerGap.claimed', { count: report.claimed })}</p>}
      {unmatched > 0 && <p>{t('ledgerGap.unmatched', { count: unmatched })}</p>}
      {report.undecided > 0 && <p>{t('ledgerGap.undecided', { count: report.undecided })}</p>}
      {/* 有地方讀不到時說不出「每一個都認得」：那一句由下面的 `unread` 說。 */}
      {report.claimed === 0 && unmatched === 0 && report.undecided === 0 && unread.length === 0 && (
        <p>{t('ledgerGap.nothing')}</p>
      )}
      {unread.length > 0 && (
        <>
          <p className="max-w-prose text-xs text-ink-dim">{t('ledgerGap.unread')}</p>
          <TechnicalDetails lines={unread} />
        </>
      )}
    </div>
  )
}
