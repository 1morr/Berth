import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'

import type { IndexerConnectInput, IndexerKind, IndexerSetup, TmdbSetup } from '../api/setup'
import {
  STICKY_ACTION,
  Checkbox,
  CopyLine,
  Field,
  GhostButton,
  Notice,
  PrimaryButton,
} from '../components/controls'
import { SIGNAL_FILL } from '../components/signal'
import { Cutaway, CutawayRow } from './Cutaway'
import { StepLine } from '../components/StepLine'

/**
 * 泊位 3：來源（plan §9.3 第 5–6 步）。同一個泊位的兩條纜繩——索引站與 TMDB。
 *
 * 套件內 Prowlarr：勾十個公開站，一站一條纜繩。**逐站的成敗是 Prowlarr 自己連過那個站的結果**：
 * 十個裡有幾個連不上是常態，失敗的變紅，其餘照樣繫上（brief §20.7）。
 * 既有：Prowlarr 位址 + key，或任意 Torznab 端點 + key。
 */
export function SourceStep({
  indexers,
  tmdb,
  applying,
  connecting,
  testingTmdb,
  onApply,
  onConnect,
  onSkipIndexers,
  onTestTmdb,
  onSkipTmdb,
}: {
  indexers: IndexerSetup
  tmdb: TmdbSetup
  applying: boolean
  connecting: boolean
  testingTmdb: boolean
  onApply: (selected: string[]) => void
  onConnect: (input: IndexerConnectInput) => void
  onSkipIndexers: () => void
  onTestTmdb: (apiKey: string) => void
  onSkipTmdb: () => void
}) {
  const { t } = useTranslation()
  const bundled = indexers.origin === 'bundled' && indexers.reachable

  return (
    <div className="grid flex-1 gap-px bg-rule lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
      <div className="min-w-0 bg-hull p-6">
        <div className="lg:sticky lg:top-6">
          <SourceCutaway indexers={indexers} tmdb={tmdb} bundled={bundled} />
        </div>
      </div>

      <div className="min-w-0 bg-hull p-6">
        <h2 className="text-lg font-semibold text-ink">{t('source.title')}</h2>
        <p className="mt-2 max-w-prose text-sm text-ink-dim">{t('source.lede')}</p>

        {bundled ? (
          <DefaultIndexers
            indexers={indexers}
            applying={applying}
            onApply={onApply}
            onSkip={onSkipIndexers}
          />
        ) : (
          <>
            {/* 套件內的那台連不上：說清楚，然後照樣給表單——他總得有辦法往下走。 */}
            {indexers.origin === 'bundled' && <Unreachable indexers={indexers} />}
            <ExistingIndexer
              indexers={indexers}
              connecting={connecting}
              onConnect={onConnect}
              onSkip={onSkipIndexers}
            />
          </>
        )}

        <Tmdb tmdb={tmdb} testing={testingTmdb} onTest={onTestTmdb} onSkip={onSkipTmdb} />
      </div>
    </div>
  )
}

/** 剖面：這個泊位會接上哪一種來源、TMDB 的憑證從哪裡來。 */
function SourceCutaway({
  indexers,
  tmdb,
  bundled,
}: {
  indexers: IndexerSetup
  tmdb: TmdbSetup
  bundled: boolean
}) {
  const { t } = useTranslation()
  const added = indexers.options.filter((row) => row.present).length

  return (
    <div className="grid gap-6">
      <Cutaway title={t('source.cutaway.indexers')}>
        <CutawayRow
          term={t('source.cutaway.kind')}
          value={t(bundled ? 'source.cutaway.bundled' : `source.kind.${indexers.kind}`)}
        />
        <CutawayRow term={t('connect.field.baseUrl')} value={indexers.base_url || '—'} />
        <CutawayRow
          term={t('connect.field.apiKey')}
          value={t(indexers.api_key_present ? 'jellyfin.cutaway.held' : 'jellyfin.cutaway.absent')}
          muted={!indexers.api_key_present}
        />
        {bundled && (
          <CutawayRow
            term={t('source.cutaway.added')}
            value={`${added} / ${indexers.options.length}`}
            muted={added === 0}
          />
        )}
      </Cutaway>

      <Cutaway title={t('source.cutaway.tmdb')}>
        <CutawayRow
          term={t('source.cutaway.credential')}
          value={t(
            tmdb.using_project_credential ? 'source.tmdb.builtIn' : 'source.tmdb.overridden',
          )}
        />
        <CutawayRow term={t('source.cutaway.endpoint')} value="GET /3/configuration" />
      </Cutaway>
    </div>
  )
}

/** 套件內 Prowlarr：十個預設公開站，預設全勾（plan §9.3 第 5 步）。 */
function DefaultIndexers({
  indexers,
  applying,
  onApply,
  onSkip,
}: {
  indexers: IndexerSetup
  applying: boolean
  onApply: (selected: string[]) => void
  onSkip: () => void
}) {
  const { t } = useTranslation()
  const [unticked, setUnticked] = useState<ReadonlySet<string>>(new Set())
  const selected = indexers.options
    .map((row) => row.definition_name)
    .filter((name) => !unticked.has(name))
  const byStep = new Map(indexers.steps.map((row) => [row.step, row]))
  //: 與後端的 `PROWLARR_LOGIN_STEP` 同一個字串——那一條不是站，不能混進站的清單裡。
  const login = byStep.get('prowlarr_login')

  function toggle(name: string, ticked: boolean) {
    setUnticked((was) => {
      const next = new Set(was)
      if (ticked) next.delete(name)
      else next.add(name)
      return next
    })
  }

  return (
    <section className="mt-6">
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="label text-ink-dim">{t('source.indexers.title')}</h3>
        {indexers.skipped && (
          <span
            data-testid="indexers-deferred"
            className={`label px-2 py-1.5 ${SIGNAL_FILL.neutral}`}
          >
            {t('source.deferred')}
          </span>
        )}
      </div>
      <p className="mt-2 max-w-prose text-sm text-ink-dim">{t('source.indexers.lede')}</p>

      <fieldset className="mt-4 border-2 border-rule bg-well px-4 py-4">
        <legend className="label px-2 text-ink-dim">{t('source.indexers.pick')}</legend>
        <div className="grid gap-3 sm:grid-cols-2">
          {indexers.options.map((option) => (
            <Checkbox
              key={option.definition_name}
              label={option.name}
              hint={
                option.privacy && option.privacy !== 'public'
                  ? t('source.indexers.semiPrivate')
                  : undefined
              }
              checked={!unticked.has(option.definition_name)}
              onChange={(ticked) => toggle(option.definition_name, ticked)}
            />
          ))}
        </div>
      </fieldset>

      <div className={`mt-6 grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] ${STICKY_ACTION}`}>
        <PrimaryButton
          type="button"
          disabled={applying || selected.length === 0}
          onClick={() => onApply(selected)}
        >
          {applying
            ? t('source.indexers.applying')
            : t('source.indexers.apply', { sites: selected.length })}
        </PrimaryButton>
        <GhostButton type="button" disabled={applying} onClick={onSkip}>
          {t('source.skip')}
        </GhostButton>
      </div>

      {indexers.steps.length > 0 && (
        <ol aria-live="polite" aria-busy={applying} className="mt-6 grid gap-3" data-testid="sites">
          {indexers.options
            .filter((option) => byStep.has(option.definition_name))
            .map((option) => (
              <StepLine
                key={option.definition_name}
                label={option.name}
                endpoint={option.definition_name}
                row={byStep.get(option.definition_name)}
                fix={t('source.indexers.fix')}
                commands={[`${indexers.base_url}/#/indexers`]}
              >
                <p className="mt-3 text-xs text-ink-dim">{t('source.indexers.retryHint')}</p>
              </StepLine>
            ))}
          {/* 「同一組帳密」那一條也是這一輪做的事，成敗要看得到（brief §16.3）。 */}
          {login && (
            <StepLine
              label={t('source.indexers.login')}
              endpoint="PUT /api/v1/config/host"
              row={login}
              fix={t('source.indexers.loginFix')}
              commands={[`${indexers.base_url}/#/settings/general`]}
            />
          )}
        </ol>
      )}
    </section>
  )
}

/** 既有：Prowlarr 位址 + key，或任意 Torznab 端點 + key。兩者都有「測試」。 */
function ExistingIndexer({
  indexers,
  connecting,
  onConnect,
  onSkip,
}: {
  indexers: IndexerSetup
  connecting: boolean
  onConnect: (input: IndexerConnectInput) => void
  onSkip: () => void
}) {
  const { t } = useTranslation()
  const [kind, setKind] = useState<IndexerKind>(indexers.kind)
  const [baseUrl, setBaseUrl] = useState(indexers.base_url)
  const [apiKey, setApiKey] = useState('')
  const row = indexers.steps.find((step) => step.step === kind)

  function submit(event: FormEvent) {
    event.preventDefault()
    if (!baseUrl.trim()) return
    onConnect({ kind, base_url: baseUrl.trim(), api_key: apiKey.trim() })
  }

  return (
    <section className="mt-6">
      <h3 className="label text-ink-dim">{t('source.existing.title')}</h3>
      <p className="mt-2 max-w-prose text-sm text-ink-dim">{t('source.existing.lede')}</p>

      {/* 兩種接法是同一件事的兩個形狀，所以用一組 radio 而不是分頁——沒有 Radix，也不必有。 */}
      <fieldset className="mt-4 border-2 border-rule bg-well px-4 py-3">
        <legend className="label px-2 text-ink-dim">{t('source.existing.kind')}</legend>
        <div className="flex flex-wrap gap-x-6 gap-y-2">
          {(['prowlarr', 'torznab'] as const).map((option) => (
            <label key={option} className="flex items-center gap-2 text-sm text-ink">
              <input
                type="radio"
                name="indexer-kind"
                value={option}
                checked={kind === option}
                onChange={() => setKind(option)}
                className="size-4 accent-[var(--color-assigned)]"
              />
              {t(`source.kind.${option}`)}
            </label>
          ))}
        </div>
      </fieldset>

      <form onSubmit={submit} noValidate className="mt-4 grid gap-4">
        <Field
          label={t('connect.field.baseUrl')}
          value={baseUrl}
          inputMode="url"
          placeholder={
            kind === 'prowlarr'
              ? 'http://192.168.1.10:9696'
              : 'http://192.168.1.10:9117/api/v2.0/indexers/all/results/torznab/api'
          }
          hint={t(`source.existing.hint.${kind}`)}
          onChange={(event) => setBaseUrl(event.target.value)}
        />
        <Field
          label={t('connect.field.apiKey')}
          value={apiKey}
          autoComplete="off"
          onChange={(event) => setApiKey(event.target.value)}
        />
        <div className={`grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] ${STICKY_ACTION}`}>
          <PrimaryButton type="submit" disabled={connecting}>
            {connecting ? t('source.existing.testing') : t('source.existing.test')}
          </PrimaryButton>
          <GhostButton type="button" disabled={connecting} onClick={onSkip}>
            {t('source.skip')}
          </GhostButton>
        </div>
      </form>

      {row && (
        <ol className="mt-4 grid gap-3" data-testid="sites">
          <StepLine
            label={t(`source.kind.${kind}`)}
            endpoint={kind === 'prowlarr' ? 'GET /api/v1/indexer' : '?t=caps'}
            row={row}
            fix={t('source.existing.fix')}
          />
        </ol>
      )}
    </section>
  )
}

/** 第 6 步：內建專案級憑證，可覆寫，一顆「測試」（plan §9.3 第 6 步）。 */
function Tmdb({
  tmdb,
  testing,
  onTest,
  onSkip,
}: {
  tmdb: TmdbSetup
  testing: boolean
  onTest: (apiKey: string) => void
  onSkip: () => void
}) {
  const { t } = useTranslation()
  const [apiKey, setApiKey] = useState('')
  const row = tmdb.steps.find((step) => step.step === 'configuration')

  return (
    <section className="mt-10 border-t-2 border-rule pt-6">
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="label text-ink-dim">{t('source.tmdb.title')}</h3>
        {tmdb.skipped && (
          <span className={`label px-2 py-1.5 ${SIGNAL_FILL.neutral}`}>{t('source.deferred')}</span>
        )}
      </div>
      <p className="mt-2 max-w-prose text-sm text-ink-dim">{t('source.tmdb.lede')}</p>

      <form
        onSubmit={(event) => {
          event.preventDefault()
          onTest(apiKey)
        }}
        noValidate
        className="mt-4 grid gap-4"
      >
        <Field
          label={t('source.tmdb.field')}
          value={apiKey}
          autoComplete="off"
          placeholder={t('source.tmdb.placeholder')}
          hint={t('source.tmdb.hint')}
          onChange={(event) => setApiKey(event.target.value)}
        />
        <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto]">
          <PrimaryButton type="submit" disabled={testing}>
            {testing ? t('source.tmdb.testing') : t('source.tmdb.test')}
          </PrimaryButton>
          <GhostButton type="button" disabled={testing} onClick={onSkip}>
            {t('source.skip')}
          </GhostButton>
        </div>
      </form>

      {row && (
        <ol className="mt-4 grid gap-3" data-testid="tmdb">
          <StepLine
            label={t('source.tmdb.line')}
            endpoint="GET /3/configuration"
            row={row}
            fix={t('source.tmdb.fix')}
            commands={['https://www.themoviedb.org/settings/api']}
          />
        </ol>
      )}

      {!tmdb.using_project_credential && (
        <div className="mt-4">
          <Notice signal="secured" label={t('source.tmdb.ownKeyLabel')}>
            {t('source.tmdb.ownKey')}
          </Notice>
        </div>
      )}
    </section>
  )
}

/** 連不上套件內的 Prowlarr 時，畫面仍然要說得出下一步。 */
function Unreachable({ indexers }: { indexers: IndexerSetup }) {
  const { t } = useTranslation()

  return (
    <div className="mt-6 grid gap-4">
      <Notice signal="blocked" label={t('common.failed')}>
        {t('source.unreachable')}
      </Notice>
      {indexers.error && (
        <p role="alert" className="value max-w-prose break-words text-xs text-blocked-ink">
          {indexers.error}
        </p>
      )}
      <div className="grid grid-cols-1 gap-px">
        <CopyLine command="docker compose ps prowlarr" />
        <CopyLine command="docker compose logs --tail 50 prowlarr" />
      </div>
    </div>
  )
}
