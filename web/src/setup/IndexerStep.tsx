import { useId, useState, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type {
  IndexerConnectInput,
  IndexerKind,
  IndexerSetup,
  SiteSearch,
  TrialSearchResult,
} from '../api/setup'
import {
  STICKY_ACTION,
  Checkbox,
  ConfirmAction,
  CopyLine,
  Field,
  GhostButton,
  Notice,
  PasswordField,
  PrimaryButton,
} from '../components/controls'
import { SIGNAL_FILL } from '../components/signal'
import { Cutaway, CutawayRow } from '../components/Cutaway'
import { StepLine } from '../components/StepLine'
import { useFocusAfterRemoval } from '../components/useFocusAfterRemoval'
import { languageName } from './languageName'

/**
 * 泊位 4：索引站（plan §9.3 第 6 步）。票 06e 從「來源」拆出來，TMDB 是下一個泊位。
 *
 * 套件內 Prowlarr：勾預設公開站，一站一條纜繩。**逐站的成敗是 Prowlarr 自己連過那個站的結果**：
 * 幾個連不上是常態，失敗的變紅，其餘照樣繫上（brief §20.7）。加完之後**試搜**，不要的就地移除——
 * Prowlarr 只搜得到已經加進來的站，所以流程是「加入 → 試搜 → 移除」，不是加入前試搜。
 * 既有：Prowlarr 位址 + key，或任意 Torznab 端點 + key；接上之後同樣可以試搜，但不移除別人的站。
 *
 * **資料與動作全部從 props 進來**：精靈跑完之後設定頁接手（票 06i），重用這裡的區塊。
 */
export function IndexerStep({
  indexers,
  applying,
  connecting,
  onApply,
  onConnect,
  onSkip,
  trial,
  note,
  nav,
  redetect,
}: {
  indexers: IndexerSetup
  applying: boolean
  connecting: boolean
  onApply: (selected: string[]) => void
  onConnect: (input: IndexerConnectInput) => void
  onSkip: () => void
  /** 試搜與移除（`TrialSearch` 的 props，少了站的清單——那由這一頁從 `indexers` 導出）。 */
  trial: Omit<TrialSearchProps, 'sites'>
  /** 回頭看的說明（`RevisitNote`），這一頁做完了才有。 */
  note?: ReactNode
  /** 上一個 / 下一個泊位（`BerthNav`）。 */
  nav?: ReactNode
  /** 套件內的 Prowlarr 連不上時的「重新偵測這個服務」（票 06d）。 */
  redetect?: ReactNode
}) {
  const { t } = useTranslation()
  const bundled = indexers.origin === 'bundled' && indexers.reachable
  const connected = indexers.steps.some(
    (row) => row.step === indexers.kind && (row.status === 'ok' || row.status === 'skipped'),
  )

  return (
    <div className="grid flex-1 gap-px bg-rule lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
      <div className="min-w-0 bg-hull p-6">
        <div className="lg:sticky lg:top-6">
          <IndexerCutaway indexers={indexers} bundled={bundled} />
        </div>
      </div>

      <div className="min-w-0 bg-hull p-6">
        <h2 className="text-lg font-semibold text-ink">{t('indexer.title')}</h2>
        <p className="mt-2 max-w-prose text-sm text-ink-dim">{t('indexer.lede')}</p>
        {note}

        {bundled ? (
          <>
            <DefaultIndexers
              indexers={indexers}
              applying={applying}
              onApply={onApply}
              onSkip={onSkip}
            />
            {indexers.options.some((row) => row.present) && (
              <TrialSearch {...trial} sites={presentSites(indexers)} />
            )}
          </>
        ) : (
          <>
            {/* 套件內的那台連不上：說清楚，然後照樣給表單——他總得有辦法往下走。 */}
            {indexers.origin === 'bundled' && (
              <Unreachable indexers={indexers} redetect={redetect} />
            )}
            <ExistingIndexer
              indexers={indexers}
              connecting={connecting}
              onConnect={onConnect}
              onSkip={onSkip}
            />
            {/* 既有的站是使用者自己的，Berth 不移除（brief §16.4），所以不給 `onRemove`。 */}
            {connected && <TrialSearch {...trial} sites={[]} onRemove={undefined} />}
          </>
        )}

        {nav}
      </div>
    </div>
  )
}

/** 試搜清單上的一站：套件內是加進來的預設站（有 id、可以移除）。 */
export interface TrialSite {
  indexerId: number
  name: string
  language: string
}

function presentSites(indexers: IndexerSetup): TrialSite[] {
  return indexers.options.flatMap((row) =>
    row.present && row.indexer_id !== null
      ? [{ indexerId: row.indexer_id, name: row.name, language: row.language }]
      : [],
  )
}

/** 剖面：這個泊位接上的是哪一種索引站、加了幾站。 */
function IndexerCutaway({ indexers, bundled }: { indexers: IndexerSetup; bundled: boolean }) {
  const { t } = useTranslation()
  const added = indexers.options.filter((row) => row.present).length

  return (
    <Cutaway title={t('indexer.cutaway.title')}>
      <CutawayRow
        term={t('indexer.cutaway.kind')}
        value={t(bundled ? 'indexer.cutaway.bundled' : `indexer.kind.${indexers.kind}`)}
      />
      <CutawayRow term={t('connect.field.baseUrl')} value={indexers.base_url || '—'} />
      <CutawayRow
        term={t('connect.field.apiKey')}
        value={t(indexers.api_key_present ? 'jellyfin.cutaway.held' : 'jellyfin.cutaway.absent')}
        muted={!indexers.api_key_present}
      />
      {bundled && (
        <CutawayRow
          term={t('indexer.cutaway.added')}
          value={`${added} / ${indexers.options.length}`}
          muted={added === 0}
        />
      )}
    </Cutaway>
  )
}

/** 套件內 Prowlarr：預設公開站，預設全勾（plan §9.3 第 6 步）。 */
export function DefaultIndexers({
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
  const { t, i18n } = useTranslation()
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
        <h3 className="label text-ink-dim">{t('indexer.defaults.title')}</h3>
        {indexers.skipped && (
          <span
            data-testid="indexers-deferred"
            className={`label px-2 py-1.5 ${SIGNAL_FILL.neutral}`}
          >
            {t('indexer.deferred')}
          </span>
        )}
      </div>
      <p className="mt-2 max-w-prose text-sm text-ink-dim">{t('indexer.defaults.lede')}</p>

      <fieldset className="mt-4 border-2 border-rule bg-well px-4 py-4">
        <legend className="label px-2 text-ink-dim">{t('indexer.defaults.pick')}</legend>
        <div className="grid gap-4 sm:grid-cols-2">
          {indexers.options.map((option) => (
            <Checkbox
              key={option.definition_name}
              label={option.name}
              // 語言照 UI 語言說名字；說明是定義自帶的英文原文，不翻（同 Tags）。
              hint={[
                languageName(option.language, i18n.language),
                option.privacy && option.privacy !== 'public'
                  ? t('indexer.defaults.semiPrivate')
                  : '',
                option.description,
              ]
                .filter(Boolean)
                .join(' · ')}
              checked={!unticked.has(option.definition_name)}
              onChange={(ticked) => toggle(option.definition_name, ticked)}
            />
          ))}
        </div>
      </fieldset>

      <div className={`mt-6 grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] ${STICKY_ACTION}`}>
        <PrimaryButton
          type="button"
          busy={applying}
          disabled={selected.length === 0}
          onClick={() => onApply(selected)}
        >
          {applying
            ? t('indexer.defaults.applying')
            : t('indexer.defaults.apply', { sites: selected.length })}
        </PrimaryButton>
        <GhostButton type="button" busy={applying} onClick={onSkip}>
          {t('indexer.skip')}
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
                fix={t('indexer.defaults.fix')}
                commands={[`${indexers.base_url}/#/indexers`]}
              >
                <p className="mt-3 text-xs text-ink-dim">{t('indexer.defaults.retryHint')}</p>
              </StepLine>
            ))}
          {/* 「同一組帳密」那一條也是這一輪做的事，成敗要看得到（brief §16.3）。 */}
          {login && (
            <StepLine
              label={t('indexer.defaults.login')}
              endpoint="PUT /api/v1/config/host"
              row={login}
              fix={t('indexer.defaults.loginFix')}
              commands={[`${indexers.base_url}/#/settings/general`]}
            />
          )}
        </ol>
      )}
    </section>
  )
}

export interface TrialSearchProps {
  /** 套件內加進來的站。空的時候（既有路徑）清單就是試搜回來的那幾站。 */
  sites: TrialSite[]
  result?: TrialSearchResult
  searching: boolean
  /** 請求本身沒走完（Berth 後端）。逐站的失敗在 `result` 裡。 */
  failed: boolean
  onSearch: (query: string) => void
  /** 正在移除哪一站。 */
  removing?: number | null
  removeFailed?: boolean
  /** 移除一站。只有套件內給：既有的站是使用者自己的（brief §16.4）。 */
  onRemove?: (indexerId: number) => void
}

/**
 * 加入之後試搜（票 06e）：逐站列出搜到幾筆與前三筆標題，不要的就地移除。
 *
 * 查詢框預設空白：空白是一個真的問題——兩種協定都回各站最新的發佈（brief §20.7），
 * 證明那一站回得出東西，不必先想一個標題。TMDB 在下一個泊位，這時候還拿不到趨勢。
 *
 * 移除成功之後那一列連同觸發鍵一起消失，焦點落在接替那個位置的那一列，另有一行 `sr-only` 說結果
 * （DESIGN.md 的 The Focus Takes The Next Row Rule）。
 */
export function TrialSearch({
  sites,
  result,
  searching,
  failed,
  onSearch,
  removing = null,
  removeFailed = false,
  onRemove,
}: TrialSearchProps) {
  const { t, i18n } = useTranslation()
  const [query, setQuery] = useState('')
  const titleId = useId()
  const frame = useFocusAfterRemoval()
  // 最後按下確認移除的那一站。它從清單上消失了，就是移除成了——畫面上已經沒有東西說「成了」。
  const [removed, setRemoved] = useState<string | null>(null)
  const found = new Map(result?.sites.map((row) => [siteKey(row), row]))
  const rows =
    sites.length > 0
      ? sites.map((site) => ({
          key: String(site.indexerId),
          name: site.name,
          language: languageName(site.language, i18n.language),
          indexerId: site.indexerId as number | null,
        }))
      : (result?.sites ?? []).map((row) => ({
          key: siteKey(row),
          name: row.name,
          language: '',
          indexerId: null,
        }))

  const gone = removed !== null && !rows.some((row) => row.name === removed)

  function submit(event: FormEvent) {
    event.preventDefault()
    onSearch(query.trim())
  }

  return (
    <section
      ref={frame}
      tabIndex={-1}
      className="mt-10 border-t-2 border-rule pt-6"
      aria-labelledby={titleId}
    >
      <h3 id={titleId} className="label text-ink-dim">
        {t('indexer.trial.title')}
      </h3>
      <p className="mt-2 max-w-prose text-sm text-ink-dim">{t('indexer.trial.lede')}</p>

      <form
        onSubmit={submit}
        noValidate
        className="mt-4 grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end"
      >
        <Field
          label={t('indexer.trial.field')}
          type="search"
          value={query}
          placeholder={t('indexer.trial.placeholder')}
          onChange={(event) => setQuery(event.target.value)}
        />
        <GhostButton type="submit" busy={searching}>
          {searching ? t('indexer.trial.searching') : t('indexer.trial.search')}
        </GhostButton>
      </form>

      {failed && (
        <div className="mt-4">
          <Notice signal="blocked" label={t('common.failed')}>
            {t('indexer.trial.failed')}
          </Notice>
        </div>
      )}
      {result?.error && (
        <p role="alert" className="value mt-4 max-w-prose wrap-anywhere text-xs text-blocked-ink">
          {result.error}
        </p>
      )}
      <p aria-live="polite" className="sr-only">
        {gone ? t('indexer.remove.done', { name: removed }) : ''}
      </p>
      {removeFailed && (
        <div className="mt-4">
          <Notice signal="blocked" label={t('common.failed')}>
            {t('indexer.remove.failed')}
          </Notice>
        </div>
      )}

      {rows.length > 0 && (
        <ul
          aria-live="polite"
          aria-busy={searching}
          className="mt-4 grid gap-3"
          data-testid="trial"
        >
          {rows.map((row) => (
            <TrialRow
              key={row.key}
              name={row.name}
              language={row.language}
              site={found.get(row.key)}
              searched={result !== undefined}
              removing={row.indexerId !== null && removing === row.indexerId}
              onRemove={
                onRemove && row.indexerId !== null
                  ? () => {
                      setRemoved(row.name)
                      onRemove(row.indexerId as number)
                    }
                  : undefined
              }
            />
          ))}
        </ul>
      )}
    </section>
  )
}

/** 試搜結果以 id 對回清單上的那一站；單一 Torznab 端點沒有 id，整個算一站。 */
function siteKey(row: SiteSearch): string {
  return row.indexer_id !== null ? String(row.indexer_id) : row.name
}

function TrialRow({
  name,
  language,
  site,
  searched,
  removing,
  onRemove,
}: {
  name: string
  language: string
  site: SiteSearch | undefined
  /** 按過試搜了。沒按過的站說「還沒試搜」，按過卻沒有這一站的結果是它剛加進來。 */
  searched: boolean
  removing: boolean
  onRemove?: () => void
}) {
  const { t } = useTranslation()
  const signal = !site
    ? 'neutral'
    : site.error
      ? 'blocked'
      : site.count > 0
        ? 'secured'
        : 'assigned'

  return (
    // `<article tabIndex={-1}>`：一站被移除之後焦點落在接替那個位置的這一格（`useFocusAfterRemoval`）。
    <li>
      <article
        tabIndex={-1}
        aria-label={name}
        className="grid gap-3 border-2 border-rule px-4 py-3 sm:grid-cols-[minmax(0,1fr)_auto]"
      >
        <div className="min-w-0">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span className="text-sm font-semibold text-ink">{name}</span>
            {language && <span className="text-xs text-ink-dim">{language}</span>}
            <span className={`label px-2 py-1 ${SIGNAL_FILL[signal]}`}>
              {!site
                ? t(searched ? 'indexer.trial.notAsked' : 'indexer.trial.pending')
                : site.error
                  ? t('common.failed')
                  : t('indexer.trial.count', { count: site.count })}
            </span>
          </div>
          {site?.error && (
            <p role="alert" className="value mt-2 wrap-anywhere text-xs text-blocked-ink">
              {site.error}
            </p>
          )}
          {site && site.titles.length > 0 && (
            // 發佈名是原文：中日英混排、一百多字，整條換行不截斷（票 08 §8 同一條）。
            <ul className="mt-2 grid gap-1">
              {site.titles.map((title) => (
                <li key={title} className="value wrap-anywhere text-xs text-ink-dim">
                  {title}
                </li>
              ))}
            </ul>
          )}
        </div>
        {onRemove && (
          <div className="sm:self-start">
            <ConfirmAction
              label={t('indexer.remove.label')}
              confirmLabel={t('indexer.remove.confirm')}
              warning={t('indexer.remove.warning', { name })}
              pending={removing}
              pendingLabel={t('indexer.remove.pending')}
              onConfirm={onRemove}
            />
          </div>
        )}
      </article>
    </li>
  )
}

/** 既有：Prowlarr 位址 + key，或任意 Torznab 端點 + key。兩者都有「測試」。 */
export function ExistingIndexer({
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
      <h3 className="label text-ink-dim">{t('indexer.existing.title')}</h3>
      <p className="mt-2 max-w-prose text-sm text-ink-dim">{t('indexer.existing.lede')}</p>

      {/* 兩種接法是同一件事的兩個形狀，所以用一組 radio 而不是分頁——沒有 Radix，也不必有。 */}
      <fieldset className="mt-4 border-2 border-rule bg-well px-4 py-3">
        <legend className="label px-2 text-ink-dim">{t('indexer.existing.kind')}</legend>
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
              {t(`indexer.kind.${option}`)}
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
          hint={t(`indexer.existing.hint.${kind}`)}
          onChange={(event) => setBaseUrl(event.target.value)}
        />
        <PasswordField
          label={t('connect.field.apiKey')}
          value={apiKey}
          autoComplete="off"
          onChange={(event) => setApiKey(event.target.value)}
        />
        <div className={`grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] ${STICKY_ACTION}`}>
          <PrimaryButton type="submit" busy={connecting}>
            {connecting ? t('indexer.existing.testing') : t('indexer.existing.test')}
          </PrimaryButton>
          <GhostButton type="button" busy={connecting} onClick={onSkip}>
            {t('indexer.skip')}
          </GhostButton>
        </div>
      </form>

      {row && (
        <ol className="mt-4 grid gap-3" data-testid="sites">
          <StepLine
            label={t(`indexer.kind.${kind}`)}
            endpoint={kind === 'prowlarr' ? 'GET /api/v1/indexer' : '?t=caps'}
            row={row}
            fix={t('indexer.existing.fix')}
          />
        </ol>
      )}
    </section>
  )
}

/** 連不上套件內的 Prowlarr 時，畫面仍然要說得出下一步。 */
function Unreachable({ indexers, redetect }: { indexers: IndexerSetup; redetect?: ReactNode }) {
  const { t } = useTranslation()

  return (
    <div className="mt-6 grid gap-4">
      <Notice signal="blocked" label={t('common.failed')}>
        {t('indexer.unreachable')}
      </Notice>
      {indexers.error && (
        <p role="alert" className="value max-w-prose wrap-anywhere text-xs text-blocked-ink">
          {indexers.error}
        </p>
      )}
      <div className="grid grid-cols-1 gap-px">
        <CopyLine command="docker compose ps prowlarr" />
        <CopyLine command="docker compose logs --tail 50 prowlarr" />
      </div>
      {redetect && <div>{redetect}</div>}
    </div>
  )
}
