import { useMutation } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { deleteRoute, routeRefusalOf, type ManagedRoute } from '../api/routes'
import type { RouteView } from '../api/schemas'
import { ConfirmAction, Notice } from './controls'

/**
 * 刪除一條 Route：明確、要二次確認的動作（票 14）。Route 設定頁與精靈泊位 4 共用。
 *
 * **被引用就不給刪除鍵**：按下去才被拒絕是一個沒有必要的死胡同，所以設定頁知道引用數時直接說
 * 「刪不得、為什麼、出路是停用」。刪不刪得的判定只在後端一份（`in_use`）。精靈那一邊不知道
 * （`RouteOut` 不帶），清單之後才有人送單也可能（競態）——那兩種由後端的 409 `route_in_use` 說同一件事。
 */
export function RouteDelete({
  route,
  usage,
  onDeleted,
}: {
  route: RouteView
  usage?: Pick<ManagedRoute, 'in_use' | 'jobs' | 'ledger_entries'>
  onDeleted: () => void
}) {
  const { t } = useTranslation()
  const remove = useMutation({ mutationFn: () => deleteRoute(route.id), onSuccess: onDeleted })
  const refusal = routeRefusalOf(remove.error)

  if (usage?.in_use) {
    return (
      <p className="max-w-prose text-xs text-ink-dim">
        {t('routeSettings.delete.inUse', {
          jobs: t('routeSettings.usage.jobs', { count: usage.jobs }),
          files: t('routeSettings.usage.files', { count: usage.ledger_entries }),
        })}
      </p>
    )
  }

  return (
    <div className="grid gap-3 sm:max-w-md">
      <ConfirmAction
        label={t('routeSettings.delete.label')}
        confirmLabel={t('routeSettings.delete.confirm')}
        warning={t('routeSettings.delete.warning')}
        pending={remove.isPending}
        pendingLabel={t('routeSettings.delete.pending')}
        onConfirm={() => remove.mutate()}
      />
      {remove.isError && (
        <Notice signal="blocked" label={t('common.failed')}>
          {refusal?.reason === 'route_in_use'
            ? t('routeSettings.delete.refused')
            : t('routeSettings.delete.failed')}
        </Notice>
      )}
    </div>
  )
}
