import { useTranslation } from 'react-i18next'

import { ConfirmAction, GhostButton, Notice } from '../components/controls'
import { RequestFailed } from '../components/RequestFailed'
import { SettingsSection } from './SettingsFrame'

/**
 * 「不用 Prowlarr」（M4 票 61，審計 E3；`.scratch/m4/prowlarr-optional-shape.md`）。與精靈頁 4 的「之後再說」
 * 是同一個狀態（`POST /setup/indexers/skip`），可逆。
 *
 * 還在用時是頁尾的一區：先說後果，按下去就地確認才生效——它會讓作品頁的搜尋停下來。不是紅色：沒有東西
 * 壞了，也不是刪除（The One Meaning Rule）。
 */
export function IndexerSetAside({
  pending,
  error,
  onSetAside,
}: {
  pending: boolean
  error: unknown
  onSetAside: () => void
}) {
  const { t } = useTranslation()

  return (
    <SettingsSection
      id="settings-indexer-set-aside"
      title={t('settings.indexerPage.setAside.title')}
      lede={t('settings.indexerPage.setAside.lede')}
    >
      <div className="grid gap-3">
        <ConfirmAction
          label={t('settings.indexerPage.setAside.action')}
          confirmLabel={t('settings.indexerPage.setAside.confirm')}
          warning={t('settings.indexerPage.setAside.warning')}
          pending={pending}
          pendingLabel={t('settings.indexerPage.usage.pending')}
          onConfirm={onSetAside}
        />
        {error !== null && error !== undefined && (
          <RequestFailed error={error} lead={t('settings.indexerPage.usage.failed')} />
        )}
      </div>
    </SettingsSection>
  )
}

/**
 * 不用時整頁只剩這一塊：說這代表什麼、Berth 沒動什麼，加一顆改回來的鍵。健康卡、連線、站與介面登入都不畫
 * ——它們在這個狀態下只會是一排讀不到的紅字（shape 時使用者拍板）。
 */
export function IndexerUnused({
  pending,
  error,
  onResume,
}: {
  pending: boolean
  error: unknown
  onResume: () => void
}) {
  const { t } = useTranslation()

  return (
    <SettingsSection id="settings-indexer-unused" title={t('settings.indexerPage.unused.title')}>
      <div className="grid gap-3">
        <Notice signal="neutral" label={t('health.state.unused')}>
          {t('settings.indexerPage.unused.body')}
        </Notice>
        <div>
          <GhostButton type="button" busy={pending} onClick={onResume}>
            {pending
              ? t('settings.indexerPage.usage.pending')
              : t('settings.indexerPage.unused.resume')}
          </GhostButton>
        </div>
        {error !== null && error !== undefined && (
          <RequestFailed error={error} lead={t('settings.indexerPage.usage.failed')} />
        )}
      </div>
    </SettingsSection>
  )
}
