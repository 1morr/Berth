import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { healthDetailQueryOptions } from '../api/health'
import { testTmdb, tmdbSetupQueryOptions } from '../api/setup'
import { Notice } from '../components/controls'
import { SettingsFrame } from '../settings/SettingsFrame'
import { TmdbKey } from '../setup/TmdbStep'

/**
 * 設定 → TMDB（票 06i）。重貼 key 並測試：精靈第 7 步的 `TmdbKey` 與同一支 `POST /setup/tmdb/test`。
 * TMDB 不在 compose 裡，沒有健康卡；那一條纜繩的結果就是它的狀態。
 */
export function TmdbSettingsPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const tmdb = useQuery(tmdbSetupQueryOptions)

  const test = useMutation({
    mutationFn: testTmdb,
    onSuccess: (next) => {
      queryClient.setQueryData(tmdbSetupQueryOptions.queryKey, next)
      // 探索頁與詳情頁的「憑證缺失」是用舊 key 問出來的；健康頁的 TMDB 那一格讀 `tmdb_verified`。
      for (const queryKey of [['discover'], ['media'], healthDetailQueryOptions.queryKey]) {
        void queryClient.invalidateQueries({ queryKey })
      }
    },
  })

  return (
    <SettingsFrame title={t('settings.tmdbPage.title')} lede={t('settings.tmdbPage.lede')}>
      {tmdb.data ? (
        // `TmdbKey` 在精靈裡接在標題下面，從 `mt-6` 開起；這裡收掉那一段外距。
        <div className="[&>:first-child]:mt-0">
          <TmdbKey tmdb={tmdb.data} testing={test.isPending} onTest={(key) => test.mutate(key)} />
        </div>
      ) : tmdb.isError ? (
        <Notice signal="blocked" label={t('common.failed')}>
          {t('tmdbStep.unreachable')}
        </Notice>
      ) : (
        <p className="text-sm text-ink-dim">{t('health.checking')}</p>
      )}
      {/* 舊的那一把驗過、新的測不過：後端不存，`verified` 仍是 true（`verify_tmdb`）。
          紅燈那一條說的是這一次，這一句說的是現在實際在用哪一把。 */}
      {test.data?.verified && test.data.steps.some((row) => row.status === 'failed') && (
        <Notice signal="blocked" label={t('common.failed')}>
          {t('settings.tmdbPage.kept')}
        </Notice>
      )}
      {test.isError && (
        <Notice signal="blocked" label={t('common.failed')}>
          {t('settings.tmdbPage.failed')}
        </Notice>
      )}
    </SettingsFrame>
  )
}
