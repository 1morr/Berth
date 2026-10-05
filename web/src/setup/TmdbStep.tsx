import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import type { TFunction } from 'i18next'

import type { SetupStep } from '../api/schemas'
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
import { StepFrame } from './StepFrame'
import { looksLikeTmdbKey } from './tmdbKey'

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
    <StepFrame
      cutaway={
        <Cutaway title={t('tmdbStep.cutaway.title')}>
          <CutawayRow
            term={t('tmdbStep.cutaway.credential')}
            value={t(credentialLabel(tmdb))}
            muted={!tmdb.api_key_present}
          />
          <CutawayRow term={t('tmdbStep.cutaway.endpoint')} value="GET /3/configuration" />
        </Cutaway>
      }
    >
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

      <TmdbKey tmdb={tmdb} testing={testing} onTest={onTest} inWizard />
      {nav}
    </StepFrame>
  )
}

/** 去哪裡拿、貼上、測試，與那一條纜繩的結果。 */
export function TmdbKey({
  tmdb,
  testing,
  onTest,
  inWizard = false,
}: {
  tmdb: TmdbSetup
  testing: boolean
  onTest: (apiKey: string) => void
  /** 精靈裡才說「進度存下來了，回來還在這一步」；設定頁沒有這回事（票 06h）。 */
  inWizard?: boolean
}) {
  const { t } = useTranslation()
  const [apiKey, setApiKey] = useState('')
  // 送出前就說得出的毛病：空的，或形狀不像 TMDB 的任何一種憑證（M4 票 31）。
  const [problem, setProblem] = useState<'tmdbStep.blank' | 'tmdbStep.shape' | null>(null)
  const row = tmdb.steps.find((step) => step.step === 'configuration')

  return (
    <section className="mt-6">
      {/* 還沒有 key 的人要先離開 Berth 一趟，所以連結與可複製的網址並存：NAS 使用者的
          瀏覽器多半不在那台機器上，只給連結等於沒給。 */}
      {!tmdb.verified && (
        <div className="grid gap-3">
          <Notice signal="assigned" label={t('tmdbStep.whereLabel')}>
            {inWizard
              ? t('tmdbStep.whereWizard', { where: t('tmdbStep.where') })
              : t('tmdbStep.where')}
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
            setProblem('tmdbStep.blank')
            return
          }
          if (!looksLikeTmdbKey(apiKey)) {
            setProblem('tmdbStep.shape')
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
          error={problem ? t(problem) : undefined}
          onChange={(event) => {
            setApiKey(event.target.value)
            setProblem(null)
          }}
        />
        <div className={`grid gap-3 ${STICKY_ACTION}`}>
          <PrimaryButton type="submit" busy={testing}>
            {testing ? t('tmdbStep.testing') : t('tmdbStep.test')}
          </PrimaryButton>
        </div>
      </form>

      {/* live region 常駐、結果放進去（票 06h 的 audit）：跟結果同一次掛上的話不會被念出來。 */}
      <ol
        aria-live="polite"
        aria-busy={testing}
        className={row ? 'mt-4 grid gap-3' : undefined}
        data-testid="tmdb"
      >
        {row && <StepLine {...lineOf(t, row)} row={row} />}
      </ol>
    </section>
  )
}

/**
 * 憑證那一格：存下來不等於驗過（M4 票 21）。原本測不過時右欄寫「已取得」，泊位卡卻是「失敗 · 待驗證」。
 */
function credentialLabel(
  tmdb: TmdbSetup,
): 'tmdbStep.held' | 'tmdbStep.heldUnverified' | 'tmdbStep.absent' {
  if (!tmdb.api_key_present) return 'tmdbStep.absent'
  return tmdb.verified ? 'tmdbStep.held' : 'tmdbStep.heldUnverified'
}

/**
 * 那一條纜繩：補法照失敗的代碼挑（M4 票 21）。401 是 key 不對——原本一律叫人去查網路；
 * 只有連不出去才給探測那一行。
 */
function lineOf(t: TFunction, row: SetupStep) {
  const base = { label: t('tmdbStep.line'), service: 'TMDB', endpoint: 'GET /3/configuration' }
  switch (row.failure) {
    case 'auth_rejected':
    case 'not_found':
      return { ...base, fix: t('tmdbStep.fixKey'), commands: [TMDB_API_SETTINGS] }
    case 'credential_missing':
      return base
    case 'not_deployed':
    case 'unreachable':
    case 'starting':
    case 'protocol_mismatch':
      return { ...base, fix: t('tmdbStep.fixNetwork'), commands: [REACHABILITY_PROBE] }
    default:
      return { ...base, fix: t('tmdbStep.fix'), commands: [TMDB_API_SETTINGS, REACHABILITY_PROBE] }
  }
}
