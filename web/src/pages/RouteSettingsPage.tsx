import { useState } from 'react'
import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { healthQueryOptions } from '../api/health'
import {
  recheckRoute,
  routeRefusalOf,
  routesQueryOptions,
  updateRoute,
  type ManagedRoute,
} from '../api/routes'
import type { Profile, RouteView } from '../api/schemas'
import { Checkbox, Field, GhostButton, Notice, PrimaryButton } from '../components/controls'
import { Dot } from '../components/Dot'
import { ProfilePicker } from '../components/ProfilePicker'
import { RouteCheckList } from '../components/RouteCheckList'
import { RouteDelete } from '../components/RouteDelete'
import { RouteIdentity } from '../components/RouteIdentity'
import { SettingsTabs } from '../components/SettingsTabs'
import { AddRoute } from '../settings/AddRoute'

/**
 * Route 設定頁 `/settings/routes`（票 14、`.scratch/m1/route-settings-shape.md`）。只有 admin 進得來。
 *
 * 每條 Route 一列，形狀與健康頁的 Route 列相同——同一件事不該有兩種畫法。**綠燈收起，紅燈或
 * 停用的就地展開**（使用者拍板）：需要人的那幾條不必再按一下才看得到斷在哪裡。
 */
export function RouteSettingsPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const routes = useQuery(routesQueryOptions)

  if (routes.isPending) {
    return <p className="px-6 py-8 text-sm text-ink-dim">{t('health.checking')}</p>
  }

  if (!routes.data) {
    return (
      <div className="px-6 py-8">
        <Notice signal="blocked" label={t('common.failed')}>
          {t('health.unreachable')}
        </Notice>
      </div>
    )
  }

  return (
    <div className="mx-auto w-full max-w-3xl px-6 py-8">
      <SettingsTabs />
      <h2 className="value mt-6 text-lg font-semibold text-ink">{t('routeSettings.title')}</h2>
      <p className="mt-2 max-w-prose text-sm text-ink-dim">{t('routeSettings.lede')}</p>

      {routes.data.length === 0 ? (
        <p className="mt-6 max-w-prose text-sm text-ink-dim">{t('routeSettings.empty')}</p>
      ) : (
        <ul className="mt-6 grid gap-3">
          {routes.data.map((row) => (
            <li key={row.route.id} className="min-w-0">
              <RouteRow row={row} />
            </li>
          ))}
        </ul>
      )}

      <AddRoute routes={routes.data} onCreated={() => refreshRoutes(queryClient)} />
    </div>
  )
}

/**
 * 一條 Route 改動之後，畫著它的每一處都要重問：這一頁、健康頁的 Route 區塊、媒體庫的切換列
 * （名稱與啟用都顯示在那裡）。檢查結果不論成敗都已經寫進去了，所以失敗時也要重問。
 */
function refreshRoutes(queryClient: QueryClient) {
  // `void`：畫面不必等重抓完才解除按鈕，回傳的 promise 是刻意不等的。
  void queryClient.invalidateQueries({ queryKey: routesQueryOptions.queryKey })
  void queryClient.invalidateQueries({ queryKey: healthQueryOptions.queryKey })
  void queryClient.invalidateQueries({ queryKey: ['inventory'] })
}

/**
 * 一條 Route。用原生 `<details>`：鍵盤與螢幕閱讀器的行為比自己管 state 好（票 05 的決定）。
 * `<summary>` 是 flex，三角形會被吃掉，所以展開與否由模板字自己說出來。
 */
function RouteRow({ row }: { row: ManagedRoute }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { route } = row
  const attention = route.health === 'failed' || !route.enabled

  return (
    <details
      open={attention}
      className={`group min-w-0 border-2 bg-well ${attention ? 'border-rule-strong' : 'border-rule'}`}
    >
      <summary className="flex cursor-pointer flex-wrap items-center gap-x-3 gap-y-2 px-4 py-3">
        <RouteIdentity route={route} />
        <span className="value min-w-0 grow break-words text-xs text-ink-dim">
          {route.target_path}
        </span>
        <span className="flex flex-wrap items-center gap-x-2 text-xs text-ink-dim">
          <span className="value">{t('routeSettings.usage.jobs', { count: row.jobs })}</span>
          <Dot />
          <span className="value">
            {t('routeSettings.usage.files', { count: row.ledger_entries })}
          </span>
        </span>
        <span className="label shrink-0 text-ink-dim group-open:hidden">
          {t('routeSettings.manage')}
        </span>
        <span className="label hidden shrink-0 text-ink-dim group-open:inline">
          {t('routeSettings.collapse')}
        </span>
      </summary>
      <div className="grid gap-6 border-t-2 border-rule px-4 py-4">
        <RouteEditor route={route} />
        <RouteChecks route={route} />
        <RouteDelete route={route} usage={row} onDeleted={() => refreshRoutes(queryClient)} />
      </div>
    </details>
  )
}

/**
 * 五條纜繩與「重新檢查」。只是診斷：不動啟用（管理員可能是故意停用它的），紅燈修好之後要用它，
 * 在上面明確地勾啟用再儲存一次。開頁不自動檢查——那一輪會建分類、寫探測檔（票 10 的決定）。
 */
function RouteChecks({ route }: { route: RouteView }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const recheck = useMutation({
    mutationFn: () => recheckRoute(route.id),
    onSettled: () => refreshRoutes(queryClient),
  })

  return (
    <div className="grid gap-3">
      <RouteCheckList route={route} busy={recheck.isPending} />
      <div>
        <GhostButton type="button" disabled={recheck.isPending} onClick={() => recheck.mutate()}>
          {recheck.isPending ? t('routeSettings.rechecking') : t('routeSettings.recheck')}
        </GhostButton>
      </div>
      {recheck.isError && (
        <Notice signal="blocked" label={t('common.failed')}>
          {t('routeSettings.recheckFailed')}
        </Notice>
      )}
    </div>
  )
}

/**
 * 名稱、profile、啟用（使用者拍板：建立之後只改得了這三個）。
 *
 * 儲存一定重跑五條纜繩（票 14）。**從停用到啟用而檢查是紅的**，後端回 409 `route_unhealthy`：
 * 名稱與 profile 照樣存下，勾選框退回停用，並指向下面紅的那一條——那一條就是這一列展開著的原因。
 */
function RouteEditor({ route }: { route: RouteView }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [name, setName] = useState(route.name)
  const [profile, setProfile] = useState<Profile>(route.profile)
  const [enabled, setEnabled] = useState(route.enabled)
  const [blank, setBlank] = useState(false)

  const save = useMutation({
    mutationFn: () => updateRoute(route.id, { name: name.trim(), profile, enabled }),
    onError: () => setEnabled(route.enabled),
    onSettled: () => refreshRoutes(queryClient),
  })
  const refusal = routeRefusalOf(save.error)

  return (
    <form
      noValidate
      className="grid gap-4"
      onSubmit={(event) => {
        event.preventDefault()
        // 空白的名稱不打 API：說不行的是欄位自己（票 02b 的規則），按鈕永遠按得下去。
        if (!name.trim()) {
          setBlank(true)
          return
        }
        setBlank(false)
        save.mutate()
      }}
    >
      <div className="grid gap-4 sm:max-w-md">
        <Field
          label={t('routeSettings.edit.name')}
          value={name}
          onChange={(event) => setName(event.target.value)}
          error={blank ? t('routeSettings.edit.nameRequired') : undefined}
        />
        {route.collection_type === 'tvshows' && (
          <ProfilePicker group={`profile-route-${route.id}`} value={profile} onPick={setProfile} />
        )}
        <Checkbox
          label={t('routeSettings.edit.enabled')}
          hint={t('routeSettings.edit.enabledHint')}
          checked={enabled}
          onChange={setEnabled}
        />
      </div>
      <p className="max-w-prose text-xs text-ink-dim">{t('routeSettings.edit.identity')}</p>

      <div className="grid gap-3 sm:max-w-xs">
        <PrimaryButton type="submit" disabled={save.isPending}>
          {save.isPending ? t('routeSettings.edit.saving') : t('routeSettings.edit.save')}
        </PrimaryButton>
      </div>
      <p aria-live="polite" className="text-xs text-ink-dim">
        {save.isSuccess ? t('routeSettings.edit.saved') : ''}
      </p>

      {save.isError && (
        <Notice signal="blocked" label={t('common.failed')}>
          {refusal?.reason === 'route_unhealthy'
            ? t('routeSettings.edit.unhealthy')
            : t('routeSettings.edit.failed')}
        </Notice>
      )}
    </form>
  )
}
