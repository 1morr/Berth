import { useMutation } from '@tanstack/react-query'
import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'

import { routeRefusalOf, type RouteUsage } from '../api/routes'
import type { RouteView } from '../api/schemas'
import { ConfirmAction, GhostButton, Notice } from './controls'

/**
 * 這條 Route 剛剛怎麼了。說出來的是頁面那一層（票 14a）：刪掉的那一列連同這個元件一起卸載，
 * 放在這裡的訊息播不出來。
 */
export type RouteChange = 'deleted' | 'disabled'

/** 「N 筆下載」「M 個入庫檔案」兩段，刪不得的說明與 409 的拒絕都嵌它們。 */
function usageCounts(t: TFunction, usage: RouteUsage) {
  return {
    jobs: t('routeSettings.usage.jobs', { count: usage.jobs }),
    files: t('routeSettings.usage.files', { count: usage.ledger_entries }),
  }
}

/**
 * 刪除一條 Route：明確、要二次確認的動作（票 14）。Route 設定頁與精靈泊位 3 共用。
 *
 * **打哪一支由呼叫端注入**（票 14a）：設定頁是 `/routes/{id}`（永遠只有 admin），精靈是
 * `/setup/routes/{id}`（跟著精靈的門禁）。兩支是同一個命令、同一種拒絕。
 *
 * **被引用就不給刪除鍵**：按下去才被拒絕是一個沒有必要的死胡同，所以設定頁知道引用數時直接說
 * 「刪不得、為什麼」，還啟用著就把出路（停用）做成旁邊的一顆鍵。精靈不給 `onDisable`：它不知道引用數
 * （`RouteOut` 不帶），停用是設定頁的事。清單之後才有人送單（競態）時，由後端的 409 `route_in_use`
 * 帶著數字說同一件事。
 */
export function RouteDelete({
  route,
  usage,
  onDelete,
  onDisable,
  onChanged,
}: {
  route: RouteView
  usage?: RouteUsage & { in_use: boolean }
  onDelete: () => Promise<void>
  /** 停用這一條。只有設定頁給；呼叫端決定送什麼（存下來的名稱）。 */
  onDisable?: () => Promise<unknown>
  onChanged: (change: RouteChange) => void
}) {
  const { t } = useTranslation()
  const remove = useMutation({ mutationFn: onDelete, onSuccess: () => onChanged('deleted') })
  const disable = useMutation({
    // `?.`：hook 不能放在條件裡，而 `onDisable` 是選填的；按鈕只在它存在時才畫。
    mutationFn: async () => {
      await onDisable?.()
    },
    onSuccess: () => onChanged('disabled'),
  })
  const refusal = routeRefusalOf(remove.error)

  if (usage?.in_use) {
    const counts = usageCounts(t, usage)
    return (
      <div className="grid gap-3 sm:max-w-md">
        <p className="max-w-prose text-xs text-ink-dim">
          {route.enabled
            ? t('routeSettings.delete.inUse', counts)
            : t('routeSettings.delete.inUseDisabled', counts)}
        </p>
        {route.enabled && onDisable && (
          <div>
            <GhostButton type="button" busy={disable.isPending} onClick={() => disable.mutate()}>
              {disable.isPending
                ? t('routeSettings.disable.pending')
                : t('routeSettings.disable.label')}
            </GhostButton>
          </div>
        )}
        {disable.isError && (
          <Notice signal="blocked" label={t('common.failed')}>
            {t('routeSettings.disable.failed')}
          </Notice>
        )}
      </div>
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
          {refusal?.reason !== 'route_in_use'
            ? t('routeSettings.delete.failed')
            : refusal.usage
              ? t('routeSettings.delete.refused', usageCounts(t, refusal.usage))
              : t('routeSettings.delete.refusedUncounted')}
        </Notice>
      )}
    </div>
  )
}
