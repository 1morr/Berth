import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { TmdbSetup } from '../api/setup'
import {
  STICKY_ACTION,
  CopyLine,
  Notice,
  PasswordField,
  PrimaryButton,
} from '../components/controls'
import { SIGNAL_FILL } from '../components/signal'
import { Cutaway, CutawayRow } from '../components/Cutaway'
import { StepLine } from '../components/StepLine'

/** 使用者去申請 key 的那一頁。連結與可複製的網址用的是同一個字串。 */
const TMDB_API_SETTINGS = 'https://www.themoviedb.org/settings/api'

/** 「key 沒打錯，那是連不出去嗎」——image 裡沒有 curl（README 的疑難排解），所以用 python。 */
const REACHABILITY_PROBE = `docker compose exec berth python -c "import socket; socket.create_connection(('api.themoviedb.org', 443), 5); print('reachable')"`

/**
 * 泊位 5：TMDB（plan §9.3 第 7 步）。票 06e 從「來源」拆出來，成為自己的泊位。
 *
 * **這一步是閘門**，所以沒有「之後再說」：測得過才走得到完成（票 02b）。第一次來的人手上還沒有
 * key，畫面因此要先說去哪裡拿，而不是只說「必填」。
 *
 * 資料與動作從 props 進來：精靈跑完之後設定頁接手重貼 key（票 06i），重用 `TmdbKey`。
 */
export function TmdbStep({
  tmdb,
  testing,
  onTest,
  note,
  nav,
}: {
  tmdb: TmdbSetup
  testing: boolean
  onTest: (apiKey: string) => void
  /** 回頭看的說明（`RevisitNote`），這一頁做完了才有。 */
  note?: ReactNode
  /** 上一個 / 下一個泊位（`BerthNav`）。 */
  nav?: ReactNode
}) {
  const { t } = useTranslation()

  return (
    <div className="grid flex-1 gap-px bg-rule lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
      <div className="min-w-0 bg-hull p-6">
        <div className="lg:sticky lg:top-6">
          <Cutaway title={t('tmdbStep.cutaway.title')}>
            <CutawayRow
              term={t('tmdbStep.cutaway.credential')}
              value={t(tmdb.api_key_present ? 'tmdbStep.held' : 'tmdbStep.absent')}
              muted={!tmdb.api_key_present}
            />
            <CutawayRow term={t('tmdbStep.cutaway.endpoint')} value="GET /3/configuration" />
          </Cutaway>
        </div>
      </div>

      <div className="min-w-0 bg-hull p-6">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-lg font-semibold text-ink">{t('tmdbStep.title')}</h2>
          <span
            data-testid="tmdb-required"
            className={`label px-2 py-1.5 ${tmdb.verified ? SIGNAL_FILL.secured : SIGNAL_FILL.assigned}`}
          >
            {t(tmdb.verified ? 'status.ok' : 'tmdbStep.required')}
          </span>
        </div>
        <p className="mt-2 max-w-prose text-sm text-ink-dim">{t('tmdbStep.lede')}</p>
        {note}

        <TmdbKey tmdb={tmdb} testing={testing} onTest={onTest} />
        {nav}
      </div>
    </div>
  )
}

/** 去哪裡拿、貼上、測試，與那一條纜繩的結果。 */
export function TmdbKey({
  tmdb,
  testing,
  onTest,
}: {
  tmdb: TmdbSetup
  testing: boolean
  onTest: (apiKey: string) => void
}) {
  const { t } = useTranslation()
  const [apiKey, setApiKey] = useState('')
  const [blank, setBlank] = useState(false)
  const row = tmdb.steps.find((step) => step.step === 'configuration')

  return (
    <section className="mt-6">
      {/* 還沒有 key 的人要先離開 Berth 一趟，所以連結與可複製的網址並存：NAS 使用者的
          瀏覽器多半不在那台機器上，只給連結等於沒給。 */}
      {!tmdb.verified && (
        <div className="grid gap-3">
          <Notice signal="assigned" label={t('tmdbStep.whereLabel')}>
            {t('tmdbStep.where')}
          </Notice>
          <div className="grid gap-3 sm:grid-cols-[auto_minmax(0,1fr)] sm:items-center">
            {/* 外框方塊的形狀出自 DESIGN.md 的 Navigation（`.label` + `border-2 border-rule`），
                不是新的元件；只有這一處用得到，所以不搬進 `components/controls.tsx`。 */}
            <a
              href={TMDB_API_SETTINGS}
              target="_blank"
              rel="noreferrer noopener"
              className="label border-2 border-rule px-4 py-2.5 text-center text-ink hover:border-rule-strong"
            >
              {t('tmdbStep.open')}
            </a>
            <CopyLine command={TMDB_API_SETTINGS} />
          </div>
        </div>
      )}

      <form
        onSubmit={(event) => {
          event.preventDefault()
          // 停用的按鈕讀起來像壞掉（票 11 的 critique），所以按得下去，說不行的是欄位自己。
          if (!apiKey.trim()) {
            setBlank(true)
            return
          }
          onTest(apiKey.trim())
        }}
        noValidate
        className="mt-4 grid gap-4"
      >
        <PasswordField
          label={t('tmdbStep.field')}
          value={apiKey}
          autoComplete="off"
          required
          placeholder={t('tmdbStep.placeholder')}
          hint={t('tmdbStep.hint')}
          error={blank ? t('tmdbStep.blank') : undefined}
          onChange={(event) => {
            setApiKey(event.target.value)
            setBlank(false)
          }}
        />
        <div className={`grid gap-3 ${STICKY_ACTION}`}>
          <PrimaryButton type="submit" busy={testing}>
            {testing ? t('tmdbStep.testing') : t('tmdbStep.test')}
          </PrimaryButton>
        </div>
      </form>

      {row && (
        <ol aria-live="polite" aria-busy={testing} className="mt-4 grid gap-3" data-testid="tmdb">
          <StepLine
            label={t('tmdbStep.line')}
            endpoint="GET /3/configuration"
            row={row}
            fix={t('tmdbStep.fix')}
            commands={[TMDB_API_SETTINGS, REACHABILITY_PROBE]}
          />
        </ol>
      )}
    </section>
  )
}
