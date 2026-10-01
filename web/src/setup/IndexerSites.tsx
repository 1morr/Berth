import { useId, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'

import { formatList } from '../i18n/list'

import type {
  IndexerCandidate,
  IndexerSetup,
  IndexerSite,
  SiteCheck,
  SiteFailure,
  SiteSearch,
  TrialSearchResult,
} from '../api/setup'
import {
  STICKY_ACTION,
  ConfirmAction,
  Field,
  GhostButton,
  Notice,
  PrimaryButton,
  TEXT_LINK,
} from '../components/controls'
import { SIGNAL_FILL, type Signal } from '../components/signal'
import { TechnicalDetails } from '../components/TechnicalDetails'
import { useFocusAfterRemoval } from '../components/useFocusAfterRemoval'
import { languageName } from './languageName'
import { prowlarrWeb } from './serviceWeb'
import { hostOf } from './signals'
import { GAP } from './indexerGaps'

/**
 * 頁 4 與設定頁的索引站那一半（M4 票 09，`.scratch/m4/indexer-berth-shape.md`）：
 *
 * - **已加入**（`AddedSites`）：Prowlarr 裡的每一站，一列一顆「搜尋」，段頭一顆「搜尋全部」；
 *   Berth 加得回去的站可以就地移除。既有 Prowlarr 沒有移除：那是它自己介面上的事。
 * - **加站**（`AddSites`，套件內與既有的 Prowlarr，M4 票 20）：推薦的九站與其他公開站，**先測再勾**——
 *   `indexer/test` 測還沒加入的定義，什麼都不建立（brief §20.7），通過的才勾得起來。沒通過的是中性的一列：紅色只代表阻擋，
 *   而一站沒通過不擋這一頁。
 *
 * 結果長在它那一列（shape 時使用者拍板），**進頁不送任何測試**：測試與搜尋都由人按。
 */

/** 這一半用得到的動作。頁面（精靈、設定頁）接上同一批 `setup/indexers/*`。 */
export interface SiteControls {
  onTest: (names: string[]) => Promise<SiteCheck[]>
  /** `indexerId` 是那一列的「搜尋」；`null` 是全部。 */
  onSearch: (query: string, indexerId: number | null) => Promise<TrialSearchResult>
  /** 正在移除哪一站。 */
  removing: number | null
  removeFailed: boolean
  onRemove: (indexerId: number) => void
}

/** 一站在畫面上的測試狀態：還沒測、測試中，或測過的結論。 */
type CheckState = 'testing' | SiteCheck

// --- 已加入 ---

/** 已加入清單的一列。既有 Torznab 端點整個算一站、沒有 id。 */
interface AddedRow {
  key: string
  name: string
  language: string
  indexerId: number | null
  removable: boolean
  /** 在 Prowlarr 停用的站：搜尋不會問它（`indexer.search_indexers` 只問啟用中的）。 */
  enabled: boolean
}

export function AddedSites({
  indexers,
  controls,
}: {
  indexers: IndexerSetup
  controls: SiteControls
}) {
  const { t, i18n } = useTranslation()
  const titleId = useId()
  const frame = useFocusAfterRemoval()
  const [query, setQuery] = useState('')
  // 按過搜尋的每一站：搜尋中、或它的結果。
  const [found, setFound] = useState<ReadonlyMap<string, 'searching' | SiteSearch>>(new Map())
  const [failed, setFailed] = useState(false)
  const [listError, setListError] = useState('')
  const [announce, setAnnounce] = useState('')
  // 最後按下確認移除的那一站。它從清單上消失了，就是移除成了——畫面上已經沒有東西說「成了」。
  const [removed, setRemoved] = useState<string | null>(null)
  const bundled = indexers.origin === 'bundled'
  const webUrl = prowlarrWeb(indexers)
  const rows: AddedRow[] =
    indexers.kind === 'torznab'
      ? [
          {
            key: 'endpoint',
            name: hostOf(indexers.base_url),
            language: '',
            indexerId: null,
            removable: false,
            enabled: true,
          },
        ]
      : indexers.sites.map((site: IndexerSite) => ({
          key: String(site.indexer_id),
          name: site.name,
          language: languageName(site.language, i18n.language),
          indexerId: site.indexer_id,
          removable: site.removable,
          enabled: site.enabled,
        }))
  const gone = removed !== null && !rows.some((row) => row.name === removed)
  const searchable = rows.filter((row) => row.enabled)
  const searchingAll =
    searchable.length > 0 && searchable.every((row) => found.get(row.key) === 'searching')

  async function search(targets: AddedRow[], indexerId: number | null) {
    setFailed(false)
    setListError('')
    setAnnounce('')
    setFound((was) => new Map([...was, ...targets.map((row) => [row.key, 'searching'] as const)]))
    try {
      const result = await controls.onSearch(query.trim(), indexerId)
      setListError(result.error)
      setFound((was) => {
        const next = new Map(was)
        for (const row of targets) {
          // Torznab 端點整個算一站：回來的那一站就是它。
          const site =
            row.indexerId === null
              ? result.sites[0]
              : result.sites.find((each) => each.indexer_id === row.indexerId)
          if (site) next.set(row.key, site)
          else next.delete(row.key)
        }
        return next
      })
      setAnnounce(
        t('indexer.added.done', { count: result.sites.filter((site) => site.count > 0).length }),
      )
    } catch {
      setFailed(true)
      setFound((was) => {
        const next = new Map(was)
        for (const row of targets) next.delete(row.key)
        return next
      })
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    void search(searchable, null)
  }

  return (
    <section
      ref={frame}
      tabIndex={-1}
      aria-labelledby={titleId}
      className="mt-6"
      data-testid="added"
    >
      <h3 id={titleId} className="label flex flex-wrap items-baseline gap-x-3 text-ink-dim">
        {t('indexer.added.title')}
        <span className="value text-xs">{t('indexer.added.sites', { count: rows.length })}</span>
      </h3>
      <p className="mt-2 max-w-prose text-sm text-ink-dim">
        {bundled ? t('indexer.added.lede') : t('indexer.added.existingLede')}{' '}
        {!bundled && webUrl && (
          <a
            href={`${webUrl}/#/indexers`}
            target="_blank"
            rel="noreferrer noopener"
            className={TEXT_LINK}
          >
            {t('indexer.add.openProwlarr')}
          </a>
        )}
      </p>

      {rows.length > 0 ? (
        <form
          onSubmit={submit}
          noValidate
          className="mt-4 grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end"
        >
          <Field
            label={t('indexer.added.field')}
            type="search"
            value={query}
            placeholder={t('indexer.added.placeholder')}
            onChange={(event) => setQuery(event.target.value)}
          />
          <GhostButton type="submit" busy={searchingAll}>
            {searchingAll ? t('indexer.added.searching') : t('indexer.added.searchAll')}
          </GhostButton>
        </form>
      ) : (
        <p className="mt-4 text-sm text-ink">{t('indexer.added.none')}</p>
      )}

      {failed && (
        <div className="mt-4">
          <Notice signal="blocked" label={t('common.failed')}>
            {t('indexer.added.failed')}
          </Notice>
        </div>
      )}
      {listError && (
        <div className="mt-4">
          <Notice signal="blocked" label={t('common.failed')}>
            {t('indexer.added.listFailed')}
          </Notice>
          <TechnicalDetails lines={[listError]} />
        </div>
      )}
      <p aria-live="polite" className="sr-only">
        {gone ? t('indexer.remove.done', { name: removed }) : announce}
      </p>
      {controls.removeFailed && (
        <div className="mt-4">
          <Notice signal="blocked" label={t('common.failed')}>
            {t('indexer.remove.failed')}
          </Notice>
        </div>
      )}

      {rows.length > 0 && (
        <ul className="mt-4 grid gap-3" data-testid="trial">
          {rows.map((row) => (
            <AddedSiteRow
              key={row.key}
              row={row}
              site={found.get(row.key)}
              // 使用者自己在 Prowlarr 加的私站：套件內也不移除，說一句為什麼。
              unremovable={bundled && !row.removable}
              removing={row.indexerId !== null && controls.removing === row.indexerId}
              onSearch={() => void search([row], row.indexerId)}
              onRemove={
                bundled && row.removable && row.indexerId !== null
                  ? () => {
                      setRemoved(row.name)
                      controls.onRemove(row.indexerId as number)
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

function AddedSiteRow({
  row,
  site,
  unremovable,
  removing,
  onSearch,
  onRemove,
}: {
  row: AddedRow
  site: 'searching' | SiteSearch | undefined
  /** 套件內卻不能從 Berth 移除（要帳號的站）：說一句為什麼。 */
  unremovable: boolean
  removing: boolean
  onSearch: () => void
  onRemove?: () => void
}) {
  const { t } = useTranslation()
  const searching = site === 'searching'
  const result = site === 'searching' ? undefined : site

  return (
    // `<article tabIndex={-1}>`：一站被移除之後焦點落在接替那個位置的這一格（`useFocusAfterRemoval`）。
    <li>
      <article
        tabIndex={-1}
        aria-label={row.name}
        className={`grid gap-3 border-2 px-4 py-3 sm:grid-cols-[minmax(0,1fr)_auto] ${
          result?.error ? 'border-rule-strong' : 'border-rule'
        }`}
      >
        <div className="min-w-0">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span className="text-sm font-semibold text-ink">{row.name}</span>
            {row.language && <span className="text-xs text-ink-dim">{row.language}</span>}
            <span className={`label px-2 py-1 ${SIGNAL_FILL[searching ? 'working' : 'neutral']}`}>
              {!row.enabled
                ? t('indexer.added.disabled')
                : searching
                  ? t('indexer.added.searching')
                  : !result
                    ? t('indexer.added.pending')
                    : result.error
                      ? t('indexer.added.searchFailed')
                      : t('indexer.added.count', { count: result.count })}
            </span>
          </div>
          {unremovable && <p className="mt-1 text-xs text-ink-dim">{t('indexer.added.keeps')}</p>}
          {result?.error && <TechnicalDetails lines={[result.error]} />}
          {result && result.titles.length > 0 && (
            // 發佈名是原文：中日英混排、一百多字，整條換行不截斷（票 08 §8 同一條）。
            <ul className="mt-2 grid gap-1">
              {result.titles.map((title) => (
                <li key={title} className="value wrap-anywhere text-xs text-ink-dim">
                  {title}
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="flex flex-wrap gap-2 sm:self-start">
          {row.enabled && (
            <GhostButton
              type="button"
              busy={searching}
              aria-label={t('indexer.added.searchOne', { name: row.name })}
              onClick={onSearch}
            >
              {searching ? t('indexer.added.searching') : t('indexer.added.search')}
            </GhostButton>
          )}
          {onRemove && (
            <ConfirmAction
              label={t('indexer.remove.label')}
              confirmLabel={t('indexer.remove.confirm')}
              warning={t('indexer.remove.warning', { name: row.name })}
              pending={removing}
              pendingLabel={t('indexer.remove.pending')}
              onConfirm={onRemove}
            />
          )}
        </div>
      </article>
    </li>
  )
}

// --- 加站 ---

/**
 * Prowlarr 的加站：推薦的站、其他公開站、沒通過的摘要與「加入」。套件內與既有的 Prowlarr 都有（M4 票 20）；
 * 既有的那一台在按鈕旁說出會加進哪一台、加哪幾站，移除交給它自己的介面。
 *
 * **勾選的起點是空的**（M4 票 09）：一站都不預勾，測試通過才勾得起來。加入之後那幾站搬去「已加入」，
 * 這裡只剩還沒加的——主鈕數的也只有它們。**介面登入不在這裡**（M4 票 20）：加站不該被登入欄擋住，
 * 套件內那一台的登入是精靈上自己的一區。
 */
export function AddSites({
  indexers,
  applying,
  controls,
  onApply,
  onSkip,
  sticky = true,
}: {
  indexers: IndexerSetup
  /**
   * 主鈕固定在窄版底部。精靈裡這一頁走過了（底部導覽有下一個）就不固定：兩條 sticky 會疊在
   * 同一個位置（票 08 的 code-review）。沒有東西可按時本來就不固定。
   */
  sticky?: boolean
  applying: boolean
  controls: Pick<SiteControls, 'onTest'>
  onApply: (indexers: string[]) => Promise<IndexerSetup>
  /** 「之後再說」。只有精靈給。 */
  onSkip?: () => void
}) {
  const { t, i18n } = useTranslation()
  const titleId = useId()
  // 起點是上一次「加入」的結論（回頭看時沒通過的那幾站仍說得出為什麼）；之後疊上這一頁按的測試。
  const [checks, setChecks] = useState<ReadonlyMap<string, CheckState>>(
    () => new Map(indexers.checks.map((row) => [row.definition_name, row])),
  )
  const [ticked, setTicked] = useState<ReadonlySet<string>>(new Set())
  const [requestFailed, setRequestFailed] = useState(false)
  const candidates = indexers.candidates
  const passed = (name: string) => {
    const state = checks.get(name)
    return state !== undefined && state !== 'testing' && state.passed
  }
  const chosen = candidates.filter(
    (row) => ticked.has(row.definition_name) && passed(row.definition_name),
  )
  const selected = chosen.map((row) => row.definition_name)
  const recommended = candidates.filter((row) => row.recommended)
  const others = candidates.filter((row) => !row.recommended)
  const existing = indexers.origin === 'existing'
  const webUrl = prowlarrWeb(indexers)

  async function test(names: string[]) {
    if (names.length === 0) return
    setRequestFailed(false)
    const before = checks
    setChecks((was) => new Map([...was, ...names.map((name) => [name, 'testing'] as const)]))
    try {
      const answers = await controls.onTest(names)
      setChecks(
        (was) => new Map([...was, ...answers.map((row) => [row.definition_name, row] as const)]),
      )
    } catch {
      setRequestFailed(true)
      setChecks((was) => {
        const next = new Map(was)
        for (const name of names) {
          const earlier = before.get(name)
          if (earlier === undefined) next.delete(name)
          else next.set(name, earlier)
        }
        return next
      })
    }
  }

  function toggle(name: string, value: boolean) {
    setTicked((was) => {
      const next = new Set(was)
      if (value) next.add(name)
      else next.delete(name)
      return next
    })
  }

  function apply() {
    onApply(selected).then(
      (next) => {
        // 加進去的搬去「已加入」；加不進去的（Prowlarr 加之前自己又連了一次）回到沒通過、理由同一套。
        setChecks(
          (was) =>
            new Map([
              ...was,
              ...next.checks
                .filter((row) => selected.includes(row.definition_name))
                .map((row) => [row.definition_name, row] as const),
            ]),
        )
        setTicked(new Set())
      },
      () => undefined,
    )
  }

  const untestedRecommended = recommended
    .map((row) => row.definition_name)
    .filter((name) => {
      const state = checks.get(name)
      return state === undefined || (state !== 'testing' && !state.passed)
    })
  const testingAny = recommended.some((row) => checks.get(row.definition_name) === 'testing')

  return (
    <section
      id={GAP.sites.target}
      // 頁 4 前進鍵位置的「還差」把焦點送到這裡（M4 票 27）。
      tabIndex={-1}
      aria-labelledby={titleId}
      className="mt-10 border-t-2 border-rule pt-6"
    >
      <div className="flex flex-wrap items-center gap-3">
        <h3 id={titleId} className="label text-ink-dim">
          {t('indexer.add.title')}
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
      <p className="mt-2 max-w-prose text-sm text-ink-dim">
        {t(existing ? 'indexer.add.ledeExisting' : 'indexer.add.lede')}
      </p>

      <CheckSummary candidates={candidates} checks={checks} requestFailed={requestFailed} />

      {recommended.length > 0 && (
        <div className="mt-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h4 className="label text-ink-dim">{t('indexer.add.recommended')}</h4>
            <GhostButton
              type="button"
              busy={testingAny}
              disabled={untestedRecommended.length === 0}
              onClick={() => void test(untestedRecommended)}
            >
              {testingAny ? t('indexer.add.testing') : t('indexer.add.testAll')}
            </GhostButton>
          </div>
          <ul className="mt-3 grid gap-3" data-testid="recommended">
            {recommended.map((row) => (
              <CandidateRow
                key={row.definition_name}
                candidate={row}
                check={checks.get(row.definition_name)}
                ticked={ticked.has(row.definition_name)}
                onTick={(value) => toggle(row.definition_name, value)}
                onTest={() => void test([row.definition_name])}
              />
            ))}
          </ul>
        </div>
      )}

      {others.length > 0 && (
        <OtherSites
          others={others}
          checks={checks}
          ticked={ticked}
          onTick={toggle}
          onTest={(name) => void test([name])}
        />
      )}

      {/* 主鈕貼著站清單（M4 票 20）：勾完就在手邊，不隔著別的區塊。 */}
      {existing && chosen.length > 0 && (
        <p className="mt-6 max-w-prose text-sm text-ink" data-testid="adds-into">
          {t('indexer.add.intoYours', {
            host: hostOf(indexers.base_url),
            names: formatList(
              chosen.map((row) => row.name),
              i18n.language,
            ),
            count: chosen.length,
          })}
        </p>
      )}
      <div
        className={`mt-6 grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] ${
          sticky && selected.length > 0 ? STICKY_ACTION : ''
        }`}
      >
        <PrimaryButton
          type="button"
          busy={applying}
          disabled={selected.length === 0}
          onClick={apply}
        >
          {applying
            ? t('indexer.add.applying')
            : selected.length > 0
              ? t('indexer.add.apply', { count: selected.length })
              : t('indexer.add.applyNone')}
        </PrimaryButton>
        {onSkip && (
          <GhostButton type="button" busy={applying} onClick={onSkip}>
            {t('indexer.skip')}
          </GhostButton>
        )}
      </div>

      <p className="mt-6 max-w-prose text-sm text-ink-dim">
        {t('indexer.add.privateSites')}{' '}
        {webUrl && (
          <a
            href={`${webUrl}/#/indexers`}
            target="_blank"
            rel="noreferrer noopener"
            className={TEXT_LINK}
          >
            {t('indexer.add.openProwlarr')}
          </a>
        )}
      </p>
    </section>
  )
}

/** 摘要裡理由的順序：最常見、最說得出下一步的在前。 */
const FAILURE_ORDER: readonly SiteFailure[] = ['cloudflare', 'no_results', 'unreachable', 'other']

/**
 * 沒通過的摘要（票 15 critique 的 P1）：一條 `assigned`（等你決定：換一站、之後再測）加各理由的站數。
 * **整段只有這一個 live 區**，每一列的理由不另外宣告——一次「測試全部」回來不該連念九句。
 */
function CheckSummary({
  candidates,
  checks,
  requestFailed,
}: {
  candidates: IndexerCandidate[]
  checks: ReadonlyMap<string, CheckState>
  /** 測試的請求本身沒送到（Berth 後端）：說在同一個 live 區裡，不另開一個 `alert`。 */
  requestFailed: boolean
}) {
  const { t } = useTranslation()
  const settled = candidates.flatMap((row) => {
    const state = checks.get(row.definition_name)
    return state === undefined || state === 'testing' ? [] : [state]
  })
  const failed = settled.filter((row) => !row.passed)
  const passedCount = settled.length - failed.length
  const reasons = FAILURE_ORDER.flatMap((reason) => {
    const count = failed.filter((row) => (row.reason ?? 'other') === reason).length
    return count > 0 ? [[reason, count] as const] : []
  })

  return (
    <div aria-live="polite" className="mt-4 grid gap-2" data-testid="check-summary">
      {requestFailed && (
        // 請求沒送到就是擋住了：這一頁的測試在後端回來之前一站都做不了。
        <p className="flex flex-wrap items-center gap-x-3 gap-y-2 text-sm text-ink">
          <span className={`label px-2 py-1.5 ${SIGNAL_FILL.blocked}`}>{t('common.failed')}</span>
          <span>{t('indexer.add.requestFailed')}</span>
        </p>
      )}
      {settled.length > 0 && (
        <p className="flex flex-wrap items-center gap-x-3 gap-y-2 text-sm text-ink">
          {failed.length > 0 && (
            <span className={`label px-2 py-1.5 ${SIGNAL_FILL.assigned}`}>
              {t('indexer.summary.failed', { count: failed.length })}
            </span>
          )}
          <span>
            {[
              ...reasons.map(([reason, count]) => t(`indexer.summary.reason.${reason}`, { count })),
              passedCount > 0 ? t('indexer.summary.passed', { count: passedCount }) : '',
            ]
              .filter(Boolean)
              .join(' · ')}
          </span>
          {failed.length > 0 && (
            <span className="text-xs text-ink-dim">{t('indexer.summary.hint')}</span>
          )}
        </p>
      )}
    </div>
  )
}

/** 其他公開站：輸入名稱或選語言才列出來（shape 時使用者拍板），不讓八十幾列佔掉整頁。 */
function OtherSites({
  others,
  checks,
  ticked,
  onTick,
  onTest,
}: {
  others: IndexerCandidate[]
  checks: ReadonlyMap<string, CheckState>
  ticked: ReadonlySet<string>
  onTick: (name: string, value: boolean) => void
  onTest: (name: string) => void
}) {
  const { t, i18n } = useTranslation()
  const [filter, setFilter] = useState('')
  const [language, setLanguage] = useState('')
  const selectId = useId()
  const languages = [...new Set(others.map((row) => row.language).filter(Boolean))]
    .map((code) => ({ code, name: languageName(code, i18n.language) }))
    .sort((a, b) => a.name.localeCompare(b.name, i18n.language))
  const needle = filter.trim().toLocaleLowerCase()
  const active = needle !== '' || language !== ''
  const matches = active
    ? others.filter(
        (row) =>
          (language === '' || row.language === language) &&
          (needle === '' ||
            row.name.toLocaleLowerCase().includes(needle) ||
            row.definition_name.toLocaleLowerCase().includes(needle)),
      )
    : []

  return (
    <div className="mt-8">
      <h4 className="label flex flex-wrap items-baseline gap-x-3 text-ink-dim">
        {t('indexer.add.others')}
        <span className="value text-xs">{others.length}</span>
      </h4>
      <p className="mt-2 max-w-prose text-sm text-ink-dim">{t('indexer.add.othersLede')}</p>
      <div className="mt-3 grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,14rem)] sm:items-end">
        <Field
          label={t('indexer.add.filter')}
          type="search"
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
        />
        <p className="grid gap-2">
          <label htmlFor={selectId} className="label text-ink-dim">
            {t('indexer.add.language')}
          </label>
          <select
            id={selectId}
            value={language}
            onChange={(event) => setLanguage(event.target.value)}
            className="value w-full border-2 border-rule-strong bg-hull px-3 py-2.5 text-sm text-ink focus:border-ink"
          >
            <option value="">{t('indexer.add.anyLanguage')}</option>
            {languages.map((row) => (
              <option key={row.code} value={row.code}>
                {row.name}
              </option>
            ))}
          </select>
        </p>
      </div>
      {active && (
        <>
          <p className="mt-3 text-xs text-ink-dim">
            {matches.length > 0
              ? t('indexer.add.matches', { count: matches.length })
              : t('indexer.add.noMatch')}
          </p>
          {matches.length > 0 && (
            <ul className="mt-3 grid gap-3" data-testid="others">
              {matches.map((row) => (
                <CandidateRow
                  key={row.definition_name}
                  candidate={row}
                  check={checks.get(row.definition_name)}
                  ticked={ticked.has(row.definition_name)}
                  onTick={(value) => onTick(row.definition_name, value)}
                  onTest={() => onTest(row.definition_name)}
                />
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  )
}

/** 加站清單的一列：勾選（通過才勾得起來）、站名、語言、說明、狀態塊、「測試」。 */
function CandidateRow({
  candidate,
  check,
  ticked,
  onTick,
  onTest,
}: {
  candidate: IndexerCandidate
  check: CheckState | undefined
  ticked: boolean
  onTick: (value: boolean) => void
  onTest: () => void
}) {
  const { t, i18n } = useTranslation()
  const id = useId()
  const testing = check === 'testing'
  const result = check === 'testing' ? undefined : check
  const passed = result?.passed ?? false
  const signal: Signal = testing ? 'working' : passed ? 'secured' : 'neutral'
  const state = testing
    ? t('indexer.check.testing')
    : !result
      ? t('indexer.check.untested')
      : result.passed
        ? t('indexer.check.passed')
        : t('indexer.check.failed')

  return (
    // 沒通過的那一列線變重，不變紅（The Heavier Line Rule）：它要人看一眼，但不擋這一頁。
    <li
      className={`grid gap-3 border-2 px-4 py-3 sm:grid-cols-[minmax(0,1fr)_auto] ${
        result && !result.passed ? 'border-rule-strong' : 'border-rule'
      }`}
    >
      <div className="flex min-w-0 items-start gap-3">
        <input
          id={id}
          type="checkbox"
          // 沒測過或沒通過就勾不起來（M4 票 09）。說明念得到為什麼。
          disabled={!passed}
          checked={passed && ticked}
          aria-describedby={`${id}-hint`}
          onChange={(event) => onTick(event.target.checked)}
          className="mt-0.5 size-4 shrink-0 accent-[var(--color-assigned)] disabled:cursor-not-allowed"
        />
        <div className="min-w-0">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <label htmlFor={id} className="text-sm font-semibold text-ink">
              {candidate.name}
            </label>
            {candidate.language && (
              <span className="text-xs text-ink-dim">
                {languageName(candidate.language, i18n.language)}
              </span>
            )}
            <span className={`label px-2 py-1 ${SIGNAL_FILL[signal]}`}>{state}</span>
          </div>
          <p id={`${id}-hint`} className="mt-1 text-xs text-ink-dim">
            {[
              candidate.privacy && candidate.privacy !== 'public'
                ? t('indexer.add.semiPrivate')
                : '',
              // 說明是定義自帶的英文原文，不翻（同 Tags）。
              candidate.description,
              // 測過而沒通過的，理由在下面那一句；還沒測的才說要先測。
              result ? '' : t('indexer.add.testFirst'),
            ]
              .filter(Boolean)
              .join(' · ')}
          </p>
          {result && !result.passed && (
            <>
              <p className="mt-2 max-w-prose text-sm text-ink">
                {t(`indexer.failure.${result.reason ?? 'other'}`)}
              </p>
              <TechnicalDetails lines={[result.detail]} />
            </>
          )}
        </div>
      </div>
      <div className="sm:self-start">
        <GhostButton
          type="button"
          busy={testing}
          aria-label={t('indexer.add.testOne', { name: candidate.name })}
          onClick={onTest}
        >
          {testing ? t('indexer.add.testing') : t('indexer.add.test')}
        </GhostButton>
      </div>
    </li>
  )
}
