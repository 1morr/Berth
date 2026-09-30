import { useState, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import type { TFunction } from 'i18next'

import type {
  IndexerConnectInput,
  IndexerKind,
  IndexerSetup,
  InterfaceLoginRefusal,
  SetupStatus,
} from '../api/setup'
import {
  STICKY_ACTION,
  CopyLine,
  Field,
  GhostButton,
  Notice,
  PasswordField,
  PrimaryButton,
} from '../components/controls'
import { Cutaway, CutawayRow } from '../components/Cutaway'
import { StepLine } from '../components/StepLine'
import { AddedSites, AddSites, type ApplyIndexersInput, type SiteControls } from './IndexerSites'
import { pointsAtBerth } from './loopback'
import { LoopbackHint, ServiceChoice, type ChoiceControls } from './ServiceChoice'
import { useChoiceDraft } from './choiceDraft'
import { STEP } from './navigation'
import { VERSION_FLOOR, connected } from './signals'
import { StepFrame } from './StepFrame'

export type { ApplyIndexersInput, SiteControls } from './IndexerSites'

/**
 * 頁 4：Prowlarr 與索引站（plan §9.3，M4 票 15 併成一頁、票 09 改成先測再加）。
 *
 * 頁首是二選一（`ServiceChoice`）。套件內 Prowlarr：API key 讀自唯讀掛載，連上之後是「已加入」與
 * 「加站」兩段（`IndexerSites`）：先測、通過的勾起來加入，加入之後試搜、不要的就地移除。既有：Prowlarr
 * 位址 + key，或任意 Torznab 端點 + key（`ExistingIndexer`，選「既有」時的表單）；Berth 用你已經有的站，
 * 試搜照樣可用。整頁可以「之後再說」，連選都還沒選也可以。
 *
 * **資料與動作全部從 props 進來**：精靈跑完之後設定頁接手（票 06i），重用 `IndexerActions`。
 */
export function IndexerStep({
  status,
  indexers,
  indexersFailed,
  owner,
  applying,
  connecting,
  loginRefusal,
  onApply,
  onConnect,
  onSkip,
  choice,
  sites,
  note,
  nav,
}: {
  status: SetupStatus
  /** 選之前也讀得到：後端還沒選時不去連 Prowlarr（`indexer.read_indexer_status`）。 */
  indexers: IndexerSetup | undefined
  indexersFailed: boolean
  /** 擁有者的名字：沿用 Jellyfin 帳密時的帳號，取消勾選時預填它。 */
  owner: string
  applying: boolean
  connecting: boolean
  /** 沿用 Jellyfin 帳密而 Jellyfin 那一關沒過：什麼都沒寫。 */
  loginRefusal: InterfaceLoginRefusal | null
  onApply: (input: ApplyIndexersInput) => Promise<IndexerSetup>
  onConnect: (input: IndexerConnectInput) => void
  onSkip: () => void
  choice: ChoiceControls
  /** 測試、試搜與移除（`IndexerSites`）。 */
  sites: SiteControls
  /** 回頭看的說明（`RevisitNote`），這一頁做完了才有。 */
  note?: ReactNode
  /** 上一個 / 下一個泊位（`BerthNav`）。 */
  nav?: ReactNode
}) {
  const { t } = useTranslation()
  const service = status.services.find((row) => row.kind === 'prowlarr')
  const choiceDraft = useChoiceDraft()
  // 標題與 lede 跟著畫面上選著的那一格：換另一格還在確認時就說那一格的事（票 15 critique）。
  const switching = choiceDraft.draft !== null && choiceDraft.draft !== service?.origin
  const origin = choiceDraft.draft ?? service?.origin
  const ready = connected(service) && !switching
  const bundled = Boolean(indexers && indexers.origin === 'bundled' && indexers.reachable)
  const hasResults = Boolean(indexers && indexers.steps.length > 0)

  return (
    <StepFrame
      cutaway={
        indexers ? <IndexerCutaway indexers={indexers} bundled={bundled} /> : <span aria-hidden />
      }
    >
      <h2 className="text-lg font-semibold text-ink">{t('indexer.title')}</h2>
      <p className="mt-2 max-w-prose text-sm text-ink-dim">
        {t(`indexer.lede.${origin ?? 'choose'}`)}
      </p>
      {note}

      <ServiceChoice
        kind="prowlarr"
        status={status}
        {...choice}
        {...choiceDraft}
        switchWarning={hasResults ? t('choice.switchWarning.prowlarr') : undefined}
        existingForm={
          indexers && (
            <ExistingIndexer indexers={indexers} connecting={connecting} onConnect={onConnect} />
          )
        }
      />

      {ready && indexers && bundled && (
        <>
          {indexers.sites.length > 0 && <AddedSites indexers={indexers} controls={sites} />}
          <AddSites
            indexers={indexers}
            owner={owner}
            applying={applying}
            loginRefusal={loginRefusal}
            controls={sites}
            onApply={onApply}
            onSkip={onSkip}
            sticky={status.current_step <= STEP.indexer}
          />
        </>
      )}
      {/* 既有的站是使用者自己的，Berth 不加、不移除（brief §16.4）。 */}
      {ready && indexers && !bundled && <AddedSites indexers={indexers} controls={sites} />}
      {indexersFailed && <p className="mt-6 text-sm text-ink-dim">{t('indexer.unreachable')}</p>}

      {/* 選之前、或既有那一頁，「之後再說」在這裡；套件內的在「加入」旁邊。 */}
      {!(ready && bundled) && (
        <div className="mt-6">
          <GhostButton type="button" busy={applying || connecting} onClick={onSkip}>
            {t('indexer.skip')}
          </GhostButton>
        </div>
      )}

      {nav}
    </StepFrame>
  )
}

/**
 * 這個泊位能做的事：套件內是已加入 + 加站，既有是填位址與 key + 已加入（只試搜）。
 * 精靈與設定的索引站那一頁共用這一塊（票 06i）；設定頁不給 `onSkip`——那裡不是第一次，
 * 沒有「之後再說」——也不給 `owner`：介面登入在它自己的那一區改（M4 票 07）。
 */
export function IndexerActions({
  indexers,
  owner,
  applying,
  connecting,
  onApply,
  onConnect,
  onSkip,
  sites,
}: {
  indexers: IndexerSetup
  /** 精靈給：套件內 Prowlarr 的介面登入跟著「加入」一起送，未設過時帳號預填它。 */
  owner?: string
  applying: boolean
  connecting: boolean
  onApply: (input: ApplyIndexersInput) => Promise<IndexerSetup>
  onConnect: (input: IndexerConnectInput) => void
  /** 「之後再說」。只有精靈給。 */
  onSkip?: () => void
  sites: SiteControls
}) {
  const bundled = indexers.origin === 'bundled' && indexers.reachable
  const connected = indexers.steps.some(
    (row) => row.step === indexers.kind && (row.status === 'ok' || row.status === 'skipped'),
  )

  if (bundled) {
    return (
      <>
        {indexers.sites.length > 0 && <AddedSites indexers={indexers} controls={sites} />}
        <AddSites
          indexers={indexers}
          owner={owner}
          applying={applying}
          loginRefusal={null}
          controls={sites}
          onApply={onApply}
          onSkip={onSkip}
        />
      </>
    )
  }

  return (
    <>
      {/* 套件內的那台連不上：說清楚，然後照樣給表單——他總得有辦法往下走。 */}
      {indexers.origin === 'bundled' && <Unreachable indexers={indexers} />}
      <ExistingIndexer
        indexers={indexers}
        connecting={connecting}
        onConnect={onConnect}
        onSkip={onSkip}
      />
      {/* 既有的站是使用者自己的，Berth 不加、不移除（brief §16.4）。 */}
      {connected && <AddedSites indexers={indexers} controls={sites} />}
    </>
  )
}

/** 剖面：這個泊位接上的是哪一種索引站、加了幾站。 */
function IndexerCutaway({ indexers, bundled }: { indexers: IndexerSetup; bundled: boolean }) {
  const { t } = useTranslation()

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
      {indexers.kind === 'prowlarr' && (
        <CutawayRow
          term={t('indexer.cutaway.added')}
          value={String(indexers.sites.length)}
          muted={indexers.sites.length === 0}
        />
      )}
    </Cutaway>
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
  /** 設定頁不給；精靈的「之後再說」在頁尾。 */
  onSkip?: () => void
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
          hint={
            <>
              {t(`indexer.existing.hint.${kind}`)}
              {pointsAtBerth(baseUrl) && <LoopbackHint />}
            </>
          }
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
          {onSkip && (
            <GhostButton type="button" busy={connecting} onClick={onSkip}>
              {t('indexer.skip')}
            </GhostButton>
          )}
        </div>
      </form>

      {row && (
        <ol className="mt-4 grid gap-3" data-testid="sites">
          <StepLine
            label={t(`indexer.kind.${kind}`)}
            endpoint={kind === 'prowlarr' ? 'GET /api/v1/indexer' : '?t=caps'}
            row={row}
            // 照上一次測試的理由與測過的位址（不是欄位裡正在改的那一個）說補法（M4 票 17）。
            fix={existingFix(t, indexers)}
          />
        </ol>
      )}
    </section>
  )
}

/** 既有索引站測不過時的補法：太舊就升級，位址指到 Berth 自己就說 localhost，其餘是一般的那一句。 */
function existingFix(t: TFunction, indexers: IndexerSetup): string {
  if (indexers.reason === 'version_unsupported') {
    // 「至少要 X，這一台是 Y」：版本在那一條纜繩的實測值上（`indexer.outdated_step`）。
    const version = indexers.steps.find((row) => row.step === 'prowlarr')?.detail ?? ''
    return t('connection.fix.outdated', { floor: VERSION_FLOOR.prowlarr, version })
  }
  if (pointsAtBerth(indexers.base_url)) return t('connect.loopback')
  return t('indexer.existing.fix')
}

/** 連不上套件內的 Prowlarr 時，畫面仍然要說得出下一步。 */
function Unreachable({ indexers }: { indexers: IndexerSetup }) {
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
    </div>
  )
}
