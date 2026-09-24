import { useState } from 'react'
import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { healthQueryOptions } from '../api/health'
import {
  deleteRoute,
  recheckRoute,
  routeRefusalOf,
  routesQueryOptions,
  updateRoute,
  type ManagedRoute,
} from '../api/routes'
import type { RouteView } from '../api/schemas'
import {
  PAGE_TITLE,
  Checkbox,
  Field,
  GhostButton,
  Notice,
  PrimaryButton,
} from '../components/controls'
import { Dot } from '../components/Dot'
import { RouteCheckList } from '../components/RouteCheckList'
import { RouteDelete, type RouteChange } from '../components/RouteDelete'
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
  // 刪掉的那一列連同它自己的訊息一起卸載，所以「已刪除」「已停用」由頁面這一層說（票 14a）。
  const [announcement, setAnnouncement] = useState('')

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

  function changed(route: RouteView, change: RouteChange) {
    setAnnouncement(
      change === 'deleted'
        ? t('routeSettings.delete.done', { name: route.name })
        : t('routeSettings.disable.done', { name: route.name }),
    )
    refreshRoutes(queryClient)
  }

  return (
    <div className="mx-auto w-full max-w-3xl px-6 py-8">
      <SettingsTabs />
      <h1 className={`mt-6 ${PAGE_TITLE}`}>{t('routeSettings.title')}</h1>
      <p className="mt-2 max-w-prose text-sm text-ink-dim">{t('routeSettings.lede')}</p>
      {/* 先在畫面上、內容再換：`aria-live` 區塊要在變化之前就存在，螢幕閱讀器才念得到。 */}
      <p aria-live="polite" className="mt-2 max-w-prose text-sm text-ink">
        {announcement}
      </p>

      {routes.data.length === 0 ? (
        <p className="mt-6 max-w-prose text-sm text-ink-dim">{t('routeSettings.empty')}</p>
      ) : (
        <ul className="mt-6 grid gap-3">
          {routes.data.map((row) => (
            <li key={row.route.id} className="min-w-0">
              <RouteRow row={row} onChanged={(change) => changed(row.route, change)} />
            </li>
          ))}
        </ul>
      )}

      <AddRoute onCreated={() => refreshRoutes(queryClient)} />
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
function RouteRow({
  row,
  onChanged,
}: {
  row: ManagedRoute
  onChanged: (change: RouteChange) => void
}) {
  const { t } = useTranslation()
  const { route } = row
  const attention = route.health === 'failed' || !route.enabled

  return (
    <details
      open={attention}
      className={`group min-w-0 border-2 bg-well ${attention ? 'border-rule-strong' : 'border-rule'}`}
    >
      <summary className="flex cursor-pointer flex-wrap items-center gap-x-3 gap-y-2 px-4 py-3">
        <RouteIdentity route={route} />
        <span className="value min-w-0 grow wrap-anywhere text-xs text-ink-dim">
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
        <RouteDelete
          route={route}
          usage={row}
          onDelete={() => deleteRoute(route.id)}
          // 送的是**存下來的**名稱：上面表單裡還沒存的編輯不該跟著這一顆出去（票 14a）。
          onDisable={() => updateRoute(route.id, { name: route.name, enabled: false })}
          onChanged={onChanged}
        />
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
        <GhostButton type="button" busy={recheck.isPending} onClick={() => recheck.mutate()}>
          {recheck.isPending ? t('routeSettings.rechecking') : t('routeSettings.recheck')}
        </GhostButton>
      </div>
      {/* 全綠時重跑一次，纜繩列一個字都不會變：沒有這一句就沒有回饋（票 14a）。 */}
      <p aria-live="polite" className="text-xs text-ink-dim">
        {recheck.isSuccess ? t('routeSettings.rechecked') : ''}
      </p>
      {recheck.isError && (
        <Notice signal="blocked" label={t('common.failed')}>
          {t('routeSettings.recheckFailed')}
        </Notice>
      )}
    </div>
  )
}

/**
 * 名稱與啟用（使用者拍板：建立之後只改得了這兩個）。
 *
 * 儲存一定重跑五條纜繩（票 14）。**從停用到啟用而檢查是紅的**，後端回 409 `route_unhealthy`：
 * 名稱照樣存下，勾選框退回停用，並指向下面紅的那一條——那一條就是這一列展開著的原因。
 */
function RouteEditor({ route }: { route: RouteView }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [name, setName] = useState(route.name)
  const [enabled, setEnabled] = useState(route.enabled)
  const [blank, setBlank] = useState(false)
  // 存下來的啟用狀態從別處變了（下面的一鍵停用、另一個分頁）：勾選框跟著它走，否則下一次儲存
  // 會把它打開回去（票 14a）。在 render 裡對齊而不是 effect：React 文件「prop 變了時調整 state」。
  const [savedEnabled, setSavedEnabled] = useState(route.enabled)
  if (savedEnabled !== route.enabled) {
    setSavedEnabled(route.enabled)
    setEnabled(route.enabled)
  }

  const save = useMutation({
    mutationFn: () => updateRoute(route.id, { name: name.trim(), enabled }),
    onError: () => setEnabled(route.enabled),
    onSettled: () => refreshRoutes(queryClient),
  })
  const refusal = routeRefusalOf(save.error)
  // 兩個欄位都回到存下來的值就沒有東西要存了。這一顆與空白名稱那一條（票 02b「按鈕永遠按得下去，
  // 說不行的是欄位自己」）不同級：那是填錯，這是沒東西可做——而按下去的代價是真的跑一輪五條纜繩
  // （建分類、寫探測檔）。設定表單存到沒動過就變灰是通行慣例（GitHub repo settings、Linear）。
  const dirty = name.trim() !== route.name || enabled !== route.enabled

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
        <Checkbox
          label={t('routeSettings.edit.enabled')}
          hint={t('routeSettings.edit.enabledHint')}
          checked={enabled}
          onChange={setEnabled}
        />
      </div>
      <p className="max-w-prose text-xs text-ink-dim">{t('routeSettings.edit.identity')}</p>

      <div className="grid gap-3 sm:max-w-xs">
        <PrimaryButton type="submit" busy={save.isPending} disabled={!dirty}>
          {save.isPending ? t('routeSettings.edit.saving') : t('routeSettings.edit.save')}
        </PrimaryButton>
        {/* 按下去會做的事要先說出來：五條纜繩會重跑一次（票 03 第 1 條）。 */}
        <p className="max-w-prose text-xs text-ink-dim">{t('routeSettings.edit.saveRechecks')}</p>
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
