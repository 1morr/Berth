import { useId, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import {
  createRoute,
  libraryOptionsQueryOptions,
  routeRefusalOf,
  type LibraryOption,
  type ManagedRoute,
  type RouteRefusal,
} from '../api/routes'
import type { Profile, RouteView } from '../api/schemas'
import { Field, GhostButton, Notice, PrimaryButton } from '../components/controls'
import { ProfilePicker } from '../components/ProfilePicker'

/** 建立時會遇到的五種拒絕。查表而不是動態組 key——動態組過不了 `strictKeyChecks`（票 06）。 */
const CREATE_REFUSAL = {
  library_missing: 'routeSettings.add.refusal.library_missing',
  library_unsupported: 'routeSettings.add.refusal.library_unsupported',
  target_not_in_library: 'routeSettings.add.refusal.target_not_in_library',
  target_taken: 'routeSettings.add.refusal.target_taken',
  jellyfin_unreachable: 'routeSettings.add.refusal.jellyfin_unreachable',
  profile_unsupported: 'routeSettings.add.refusal.profile_unsupported',
} as const satisfies Partial<Record<RouteRefusal, string>>

/** 這個媒體庫還沒有 Route 的路徑。哪些被佔了由後端判定（`taken`），這裡只是把它們挑掉。 */
function freePaths(library: LibraryOption): string[] {
  return library.locations.filter((path) => !library.taken.includes(path))
}

/**
 * 「新增 Route」（票 14、`.scratch/m1/route-settings-shape.md` §3）：清單下方的一顆鍵，按下去就地展開。
 *
 * **按下去才向 Jellyfin 問**：這一頁多數時候是在看狀態。路徑一律用選的（brief §4.1）；已經有 Route
 * 的路徑列出來但選不了，並說是哪一條——同一個目標兩條 Route，帳本就認不出檔案是誰的。
 */
export function AddRoute({ routes, onCreated }: { routes: ManagedRoute[]; onCreated: () => void }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const [created, setCreated] = useState<RouteView | null>(null)

  return (
    <div className="mt-8 grid gap-3">
      {/* 先在畫面上、內容再換：`aria-live` 區塊要在變化之前就存在，螢幕閱讀器才念得到。 */}
      <p aria-live="polite" className="max-w-prose text-sm text-ink">
        {created
          ? t(created.enabled ? 'routeSettings.add.createdOk' : 'routeSettings.add.createdRed', {
              name: created.name,
            })
          : ''}
      </p>
      {open ? (
        <AddRouteForm
          routes={routes}
          onCancel={() => setOpen(false)}
          onCreated={(route) => {
            setCreated(route)
            setOpen(false)
            onCreated()
          }}
        />
      ) : (
        <div>
          <GhostButton
            type="button"
            onClick={() => {
              setCreated(null)
              setOpen(true)
            }}
          >
            {t('routeSettings.add.open')}
          </GhostButton>
        </div>
      )}
    </div>
  )
}

function AddRouteForm({
  routes,
  onCancel,
  onCreated,
}: {
  routes: ManagedRoute[]
  onCancel: () => void
  onCreated: (route: RouteView) => void
}) {
  const { t } = useTranslation()
  const formId = useId()
  // 掛上來才問：區塊收著的時候這個元件不存在，所以不會開頁就打 Jellyfin。
  const libraries = useQuery(libraryOptionsQueryOptions)
  const [libraryId, setLibraryId] = useState('')
  const [target, setTarget] = useState('')
  const [name, setName] = useState('')
  const [profile, setProfile] = useState<Profile>('standard')
  const [incomplete, setIncomplete] = useState(false)
  const [blank, setBlank] = useState(false)

  const create = useMutation({
    mutationFn: () =>
      createRoute({ library_id: libraryId, target_path: target, name: name.trim(), profile }),
    onSuccess: onCreated,
  })

  const library = libraries.data?.find((row) => row.item_id === libraryId)
  const refusal = routeRefusalOf(create.error)
  const reachFailure = routeRefusalOf(libraries.error)

  function pick(next: LibraryOption) {
    setLibraryId(next.item_id)
    const free = freePaths(next)
    // 只剩一條可選時直接選它（brief §4.3 的「自動選定」）。
    setTarget(free.length === 1 ? free[0] : '')
    // 名稱預填媒體庫名，但使用者打過的不蓋掉。
    setName((was) => (was === '' || was === library?.name ? next.name : was))
    setProfile('standard')
  }

  return (
    <section aria-labelledby={`${formId}-title`} className="border-2 border-rule bg-well">
      <h3
        id={`${formId}-title`}
        className="label border-b-2 border-rule bg-deck px-4 py-2.5 text-ink-dim"
      >
        {t('routeSettings.add.title')}
      </h3>
      <div className="grid gap-4 px-4 py-4">
        <p className="max-w-prose text-xs text-ink-dim">{t('routeSettings.add.lede')}</p>

        {libraries.isPending && (
          <p className="text-xs text-ink-dim">{t('routeSettings.add.loading')}</p>
        )}

        {libraries.isError && (
          <Notice signal="blocked" label={t('common.failed')}>
            {reachFailure?.reason === 'jellyfin_unreachable' ? (
              <>
                {t('routeSettings.add.unreachable')}{' '}
                <code className="value text-xs break-words">{reachFailure.detail}</code>
              </>
            ) : (
              t('routeSettings.add.failed')
            )}
          </Notice>
        )}

        {libraries.data && (
          <form
            noValidate
            className="grid gap-4"
            onSubmit={(event) => {
              event.preventDefault()
              const missing = !library || !target
              setIncomplete(missing)
              setBlank(!name.trim())
              if (missing || !name.trim()) return
              create.mutate()
            }}
          >
            <fieldset className="grid gap-2">
              <legend className="label text-ink-dim">{t('routeSettings.add.library')}</legend>
              {libraries.data.map((option, index) => {
                const id = `${formId}-library-${index}`
                return (
                  <div key={option.item_id} className="grid gap-1">
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                      <input
                        id={id}
                        type="radio"
                        name={`${formId}-library`}
                        value={option.item_id}
                        checked={libraryId === option.item_id}
                        disabled={!option.supported}
                        onChange={() => pick(option)}
                        className="size-4 shrink-0 accent-[var(--color-assigned)]"
                      />
                      <label htmlFor={id} className="text-sm text-ink">
                        {option.name}
                      </label>
                      {/* 機器字串（Jellyfin 的 collection type）走 `.value`：`.label` 會把它大寫掉。 */}
                      <span className="value text-xs text-ink-dim">
                        {option.collection_type || t('routes.picker.mixed')}
                      </span>
                    </div>
                    {!option.supported && (
                      <p className="pl-7 text-xs text-ink-dim">{t('routes.picker.unsupported')}</p>
                    )}
                    {option.uses_tvdb && (
                      <p className="pl-7 text-xs text-ink-dim">{t('routes.picker.tvdb')}</p>
                    )}
                  </div>
                )
              })}
            </fieldset>

            {library && (
              <Targets
                formId={formId}
                library={library}
                routes={routes}
                target={target}
                onPick={setTarget}
              />
            )}
            {incomplete && (!library || !target) && (
              <p role="alert" className="text-xs text-blocked-ink">
                {t('routeSettings.add.pickFirst')}
              </p>
            )}

            <div className="grid gap-4 sm:max-w-md">
              <Field
                label={t('routeSettings.edit.name')}
                value={name}
                onChange={(event) => setName(event.target.value)}
                error={blank ? t('routeSettings.edit.nameRequired') : undefined}
              />
              {library?.collection_type === 'tvshows' && (
                <ProfilePicker group={`${formId}-profile`} value={profile} onPick={setProfile} />
              )}
            </div>

            <div className="grid grid-cols-1 gap-2 sm:grid-cols-[minmax(0,14rem)_auto] sm:items-center">
              <PrimaryButton type="submit" disabled={create.isPending}>
                {create.isPending
                  ? t('routeSettings.add.submitting')
                  : t('routeSettings.add.submit')}
              </PrimaryButton>
              <GhostButton type="button" onClick={onCancel}>
                {t('common.cancel')}
              </GhostButton>
            </div>

            {create.isError && (
              <Notice signal="blocked" label={t('common.failed')}>
                {refusal && refusal.reason in CREATE_REFUSAL
                  ? t(CREATE_REFUSAL[refusal.reason as keyof typeof CREATE_REFUSAL])
                  : t('routeSettings.add.failed')}
              </Notice>
            )}
          </form>
        )}
      </div>
    </section>
  )
}

/** 這個媒體庫回報的路徑。已經有 Route 的選不了，旁邊寫是哪一條（以 `aria-describedby` 掛上）。 */
function Targets({
  formId,
  library,
  routes,
  target,
  onPick,
}: {
  formId: string
  library: LibraryOption
  routes: ManagedRoute[]
  target: string
  onPick: (path: string) => void
}) {
  const { t } = useTranslation()
  const free = freePaths(library)

  return (
    <fieldset className="grid gap-2">
      <legend className="label text-ink-dim">{t('routeSettings.add.target')}</legend>
      {library.locations.map((path, index) => {
        const id = `${formId}-target-${index}`
        const taken = library.taken.includes(path)
        const holder = routes.find((row) => row.route.target_path === path)?.route.name
        return (
          <div key={path} className="flex flex-wrap items-start gap-x-3 gap-y-1">
            <input
              id={id}
              type="radio"
              name={`${formId}-target`}
              value={path}
              checked={target === path}
              disabled={taken}
              aria-describedby={taken ? `${id}-taken` : undefined}
              onChange={() => onPick(path)}
              className="mt-0.5 size-4 shrink-0 accent-[var(--color-assigned)]"
            />
            <label htmlFor={id} className="value min-w-0 break-words text-xs text-ink">
              {path}
            </label>
            {taken && (
              <span id={`${id}-taken`} className="text-xs text-ink-dim">
                {holder
                  ? t('routeSettings.add.taken', { name: holder })
                  : t('routeSettings.add.takenUnnamed')}
              </span>
            )}
          </div>
        )
      })}
      {free.length === 0 && (
        <p className="max-w-prose text-xs text-ink-dim">{t('routeSettings.add.noneFree')}</p>
      )}
    </fieldset>
  )
}
