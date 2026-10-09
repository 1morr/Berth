import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { ChoiceInput, ChoiceRefusal, SetupStatus } from '../api/setup'
import { GhostButton } from '../components/controls'
import { RequestFailed } from '../components/RequestFailed'
import { detailLabel } from '../components/services'
import { SIGNAL_FILL } from '../components/signal'
import { ExistingForm, Fix } from '../setup/ServiceChoice'
import { STATE_LABEL, reasonLabel, signalOf, testTarget } from '../setup/signals'

/**
 * 設定頁的 Jellyfin 連線（M4 票 78，`.scratch/m4/settings-cleanup-shape.md`）：一張唯讀的摘要，不是精靈的
 * 二選一。擁有者成立之後來源換不了（擁有者與每個人的登入都是那一台上的帳號，M4 票 18），所以不畫一組
 * 選不了的卡片，只說現在接的是哪一台、還好嗎。
 *
 * 套件內的位址是 compose 固定的，沒有可改的東西；既有的多一顆「改位址」，打開精靈同一張表單
 * （`ExistingForm`，Jellyfin 只有位址一格——API key 是 Berth 自己換來的，換它在「管理員登入」那一區）。
 * 紅燈照精靈的補法說（`Fix`）、可以重新測試。
 */
export function JellyfinConnection({
  status,
  choosing,
  retesting,
  refusal,
  requestError,
  onChoose,
  onRetest,
}: {
  status: SetupStatus
  choosing: boolean
  retesting: boolean
  refusal: ChoiceRefusal | null
  requestError: unknown
  /** `done`：存下來了才叫——被拒或沒送到時表單留著。 */
  onChoose: (input: ChoiceInput, done: () => void) => void
  onRetest: (restart: boolean) => void
}) {
  const { t } = useTranslation()
  const [editing, setEditing] = useState(false)
  // 表單改了一格還沒測：上一次的拒絕說的是舊值（同精靈，M4 票 21）。
  const [edited, setEdited] = useState(false)
  // 表單收起之後焦點回到「改位址」（DESIGN〈The Focus Follows The Confirm Rule〉）：那顆鍵要等表單卸下
  // 才重新掛上，所以記一筆，由它的 ref 接手（同精靈的 `refocusEdit`）。
  const [refocus, setRefocus] = useState(false)
  const service = status.services.find((row) => row.kind === 'jellyfin')
  if (!service) return null

  const existing = service.origin === 'existing'
  const testing = choosing || retesting
  const failed = service.state === 'failed' || service.state === 'timeout'
  const signal = testing ? 'working' : signalOf(service)
  const version =
    service.detail && detailLabel('jellyfin', service.reason) === 'detail.version'
      ? service.detail
      : ''

  function close() {
    setEditing(false)
    setEdited(false)
    setRefocus(true)
  }

  return (
    <div className="grid gap-4">
      <div className="min-w-0 border-2 border-rule bg-well">
        <dl className="grid grid-cols-1 gap-x-4 gap-y-3 px-4 py-3 sm:grid-cols-[8rem_minmax(0,1fr)] sm:gap-y-2">
          <Row label={t('settings.connection.jellyfin.source')}>
            <span className="text-sm text-ink">
              {t(existing ? 'choice.existing.title' : 'choice.bundled.title')}
            </span>
          </Row>
          <Row label={t('settings.connection.jellyfin.address')}>
            <span className="value text-sm wrap-anywhere text-ink">
              {testTarget(status, 'jellyfin')}
            </span>
          </Row>
          <Row label={t('settings.connection.jellyfin.version')}>
            <span className="value text-sm text-ink">{version || '—'}</span>
          </Row>
          <Row label={t('settings.connection.jellyfin.state')}>
            {/* 結果由這一格說（WCAG 4.1.3）：重新測試或存完之後換掉的就是它。 */}
            <span role="status" className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span className={`label px-2 py-1.5 ${SIGNAL_FILL[signal]}`}>
                {testing
                  ? t('connection.testing')
                  : service.state
                    ? t(STATE_LABEL[service.state])
                    : t('connection.untested')}
              </span>
              {service.reason && !testing && (
                <span className="text-sm text-ink">
                  {t(reasonLabel('jellyfin', service.reason, service.state))}
                </span>
              )}
            </span>
          </Row>
          {service.state === 'waiting' && (
            // 還在啟動：等了多久、上限多少（同精靈測試那一條的倒數；重測由 `ServiceConnection` 照精靈的節奏打）。
            <Row label={t('connection.waitingLabel')}>
              <span className="value text-sm text-ink">
                {t('connection.waiting', {
                  waited: service.waited_seconds,
                  window: status.window_seconds,
                })}
              </span>
              <span className="mt-1 block text-xs text-ink-dim">{t('connection.waitingHint')}</span>
            </Row>
          )}
        </dl>

        {/* 框線跨整張卡，行寬另外收：`max-w-prose` 放在帶框線的那一層會把線一起截短。 */}
        <div className="border-t-2 border-rule px-4 py-3">
          <p className="max-w-prose text-xs text-ink-dim">
            {t(
              existing
                ? 'settings.connection.jellyfin.whyExisting'
                : 'settings.connection.jellyfin.whyBundled',
            )}
          </p>
        </div>

        {failed && !testing && <Fix kind="jellyfin" status={status} service={service} />}

        {(failed || (existing && !editing)) && (
          <div className="flex flex-wrap gap-3 border-t-2 border-rule px-4 py-3">
            {failed && (
              <GhostButton type="button" busy={retesting} onClick={() => onRetest(true)}>
                {retesting ? t('connection.retesting') : t('connection.retest')}
              </GhostButton>
            )}
            {existing && !editing && (
              <GhostButton
                ref={(element: HTMLButtonElement | null) => {
                  if (!element || !refocus) return
                  element.focus()
                  setRefocus(false)
                }}
                type="button"
                onClick={() => setEditing(true)}
              >
                {t('connection.editAddress')}
              </GhostButton>
            )}
          </div>
        )}
      </div>

      {editing && (
        <div className="grid gap-3">
          <ExistingForm
            kind="jellyfin"
            status={status}
            service={edited ? undefined : service}
            initialUrl={service.base_url}
            inUse={service.state === 'ok'}
            choosing={choosing}
            refusal={edited ? null : refusal}
            focusFirst
            onEdit={() => setEdited(true)}
            onSubmit={(input) => {
              setEdited(false)
              onChoose(input, close)
            }}
          />
          <div>
            <GhostButton type="button" onClick={close}>
              {t('common.cancel')}
            </GhostButton>
          </div>
        </div>
      )}

      {requestError !== null && requestError !== undefined && (
        <RequestFailed error={requestError} ownerPending={!status.owner} />
      )}
    </div>
  )
}

/** 摘要的一列。窄版疊成兩行、列與列之間拉開；寬版兩欄對齊（每一對包一層，`sm:contents` 交回外層格線）。 */
function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-1 sm:contents">
      <dt className="label self-center text-ink-dim">{label}</dt>
      <dd className="min-w-0 self-center">{children}</dd>
    </div>
  )
}
