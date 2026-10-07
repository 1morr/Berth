import { useId, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { IndexerSetup, SiteCheck } from '../api/setup'
import { STICKY_ACTION, GhostButton, PrimaryButton } from '../components/controls'
import { ExpandHint } from '../components/ExpandHint'
import { RequestFailed } from '../components/RequestFailed'
import { SIGNAL_FILL } from '../components/signal'
import { TechnicalDetails } from '../components/TechnicalDetails'
import { formatList } from '../i18n/list'
import { GAP } from './indexerGaps'
import { useSiteChecks, withChecks } from './siteChecks'

/**
 * 套件內頁 4 的主鍵（M4 票 44，審計 E-5）：「測試推薦站，加入通過的」一次做完，結果逐站列在下面。
 *
 * 原本是測 → 勾 → 加三個動作；套件內的使用者沒有理由不要已經通過測試的推薦站。**Prowlarr 已經有站時
 * 不給這顆鍵**（重跑、重裝保留設定）：後端也只碰還沒加入的推薦站，不會重複加。逐站的清單與其他公開站
 * 收在下面的「進階」（`AdvancedSites`）。
 *
 * 結果照後端記下的結論畫（`IndexerSetup.checks`），重新整理之後還在。三種分開說：加進去了、測過而加不進去
 * （Prowlarr 加之前自己再連一次，那一次沒連上；審計實測 Internet Archive）、測試就沒過。
 */
export function RecommendedSites({
  indexers,
  running,
  held,
  sticky,
  onRun,
  onSkip,
}: {
  indexers: IndexerSetup
  running: boolean
  /**
   * 別的寫入還在飛：介面登入（M4 票 40，Prowlarr 設完會自行重啟，加站撞上它）或「進階」的「加入」。
   * 等它回來才按得下去。
   */
  held: boolean
  /** 主鍵固定在窄版底部；精靈裡這一頁走過了就不固定（同 `AddSites`）。 */
  sticky: boolean
  onRun: () => Promise<IndexerSetup>
  onSkip: () => void
}) {
  const { t } = useTranslation()
  const titleId = useId()
  // 「進階」的逐站清單記著同一份測試結論：主鍵跑完，那裡也要看得到哪幾站沒過、為什麼。
  const [, setChecks] = useSiteChecks(indexers)
  // 請求本身沒走完（Berth 停著、5xx）：說出來，不是按下去什麼都沒發生。
  const [failed, setFailed] = useState<unknown>(null)
  const recommended = indexers.candidates.filter((row) => row.recommended)
  const offered = indexers.sites.length === 0 && recommended.length > 0

  function run() {
    setFailed(null)
    onRun().then(
      (next) => setChecks((was) => withChecks(was, next.checks)),
      (error: unknown) => setFailed(error),
    )
  }

  return (
    <section
      id={GAP.sites.target}
      // 頁 4 前進鍵位置的「還差」把焦點送到這裡（M4 票 27）。
      tabIndex={-1}
      aria-labelledby={titleId}
      className="mt-10 border-t-2 border-rule pt-6"
      data-testid="recommended-sites"
    >
      <div className="flex flex-wrap items-center gap-3">
        <h3 id={titleId} className="label text-ink-dim">
          {t('indexer.quick.title')}
        </h3>
        {indexers.skipped && (
          <span
            data-testid="indexers-deferred"
            className={`label px-2 py-1.5 ${SIGNAL_FILL.neutral}`}
          >
            {t('indexer.deferred')}
          </span>
        )}
      </div>
      {offered && (
        <p className="mt-2 max-w-prose text-sm text-ink-dim">
          {t('indexer.quick.lede', { count: recommended.length })}
        </p>
      )}

      <Outcome indexers={indexers} />
      {failed !== null && (
        <div className="mt-4">
          <RequestFailed error={failed} lead={t('indexer.quick.requestFailed')} />
        </div>
      )}

      <div
        className={`mt-6 grid gap-3 ${offered ? 'sm:grid-cols-[minmax(0,1fr)_auto]' : 'justify-start'} ${
          sticky && offered ? STICKY_ACTION : ''
        }`}
      >
        {offered && (
          <PrimaryButton type="button" busy={running} disabled={held} onClick={run}>
            {running ? t('indexer.quick.running') : t('indexer.quick.run')}
          </PrimaryButton>
        )}
        <GhostButton type="button" busy={running} disabled={held} onClick={onSkip}>
          {t('indexer.skip')}
        </GhostButton>
      </div>
    </section>
  )
}

/**
 * 上一次加站的結論，逐站一列：加進去的併成一行站名（它們也在「已加入」），沒加進去的各一列、一句理由、
 * 原文收進技術細節。**只有摘要那一句是 live 區**：一次跑完不該連念九句（同 `CheckSummary`）。
 */
function Outcome({ indexers }: { indexers: IndexerSetup }) {
  const { t, i18n } = useTranslation()
  const names = new Map<string, string>([
    ...indexers.candidates.map((row) => [row.definition_name, row.name] as const),
    ...indexers.sites.map((row) => [row.definition_name, row.name] as const),
  ])
  const nameOf = (row: SiteCheck) => names.get(row.definition_name) ?? row.definition_name
  // 已經在的站重驗一次（「加入」那一條路的 `skipped`）是測試那一支：不是這一次加進去的。
  const added = indexers.checks.filter((row) => row.passed && row.stage === 'add')
  const addFailed = indexers.checks.filter((row) => !row.passed && row.stage === 'add')
  const testFailed = indexers.checks.filter((row) => !row.passed && row.stage === 'test')
  if (indexers.checks.length === 0) return null

  return (
    <div className="mt-4 grid gap-3" data-testid="one-key-outcome">
      <p aria-live="polite" className="text-sm text-ink">
        {[
          t('indexer.quick.added', { count: added.length }),
          addFailed.length > 0 ? t('indexer.quick.addFailed', { count: addFailed.length }) : '',
          testFailed.length > 0 ? t('indexer.quick.testFailed', { count: testFailed.length }) : '',
        ]
          .filter(Boolean)
          .join(' · ')}
      </p>
      {added.length > 0 && (
        <p className="text-sm text-ink-dim">
          {/* 不塗漆：加進去是常態（The Usual Stays Unpainted Rule），沒加進去的才是要看的。 */}
          <span className={`label mr-3 px-2 py-1 ${SIGNAL_FILL.neutral}`}>
            {t('indexer.quick.state.added')}
          </span>
          {formatList(added.map(nameOf), i18n.language)}
        </p>
      )}
      {addFailed.length > 0 && (
        <OutcomeRows
          note={t('indexer.quick.addFailedNote')}
          rows={addFailed}
          label={t('indexer.quick.state.addFailed')}
          nameOf={nameOf}
          testId="add-failed"
        />
      )}
      {testFailed.length > 0 && (
        <OutcomeRows
          rows={testFailed}
          label={t('indexer.quick.state.testFailed')}
          nameOf={nameOf}
          testId="test-failed"
        />
      )}
    </div>
  )
}

function OutcomeRows({
  rows,
  label,
  note,
  nameOf,
  testId,
}: {
  rows: SiteCheck[]
  label: string
  note?: ReactNode
  nameOf: (row: SiteCheck) => string
  testId: string
}) {
  const { t } = useTranslation()

  return (
    <div className="grid gap-2" data-testid={testId}>
      {note && <p className="max-w-prose text-sm text-ink">{note}</p>}
      <ul className="grid gap-3">
        {rows.map((row) => (
          // 沒加進去的線變重，不變紅（The Heavier Line Rule）：一站沒加進去不擋這一頁。
          <li key={row.definition_name} className="border-2 border-rule-strong px-4 py-3">
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <span className="text-sm font-semibold text-ink">{nameOf(row)}</span>
              <span className={`label px-2 py-1 ${SIGNAL_FILL.neutral}`}>{label}</span>
            </div>
            <p className="mt-2 max-w-prose text-sm text-ink">
              {t(`indexer.failure.${row.reason ?? 'other'}`)}
            </p>
            <TechnicalDetails lines={[row.detail]} />
          </li>
        ))}
      </ul>
    </div>
  )
}

/**
 * 「進階」：逐站測試與勾選、其他公開站（M4 票 44 從頁面上收進來）。預設收起——套件內多半一顆主鍵就夠，
 * 要挑站或加推薦清單以外的站才展開。
 */
export function AdvancedSites({ children }: { children: ReactNode }) {
  const { t } = useTranslation()

  return (
    <details className="group mt-8 border-t-2 border-rule pt-4" data-testid="advanced-sites">
      <summary className="flex cursor-pointer items-baseline gap-3 py-2 marker:content-none">
        <span className="label text-ink">{t('indexer.quick.advanced')}</span>
        <ExpandHint className="ml-auto" />
      </summary>
      {children}
    </details>
  )
}
