import { useId } from 'react'
import { useTranslation } from 'react-i18next'

import { Checkbox, Field } from '../components/controls'
import { SIGNAL_FILL } from '../components/signal'
import type { NewLibraryProblem, NewLibraryState, NewLibraryType } from './newLibrary'

const TYPES: readonly NewLibraryType[] = ['movies', 'tvshows']

/** 名稱那一格的錯 → 那一句。查表而不是動態組 key（`strictKeyChecks`，同 `PATH_FAILED`）。 */
const NAME_PROBLEM = {
  name_missing: 'routes.newLibrary.problem.name_missing',
  name_taken: 'routes.newLibrary.problem.name_taken',
} as const satisfies Partial<Record<NewLibraryProblem['reason'], string>>

/**
 * 既有 Jellyfin 頁 3 勾選表最後一張：「在這台 Jellyfin 新建一個媒體庫」（M4 票 64，
 * `.scratch/m4/existing-new-library-shape.md`）。預設不勾；勾了才展開類型、名稱與資料夾。
 *
 * 資料夾只顯示不給改：`<library root>/<slug>`，與「加入 Berth 路徑」同一個算法，寫入目標就是它。
 * 那個媒體庫伺服器上所有人都看得到，所以勾了才建，勾的時候就說。
 */
export function NewLibraryCard({
  type,
  name,
  path,
  ticked,
  locked,
  problem,
  onChange,
}: {
  type: NewLibraryType
  name: string
  /** 它會落在哪裡（`newLibraryPath`）。 */
  path: string
  ticked: boolean
  /** 建立並檢查中：照樣顯示，改不動。 */
  locked: boolean
  problem: NewLibraryProblem | null
  onChange: (patch: Partial<Omit<NewLibraryState, 'sent'>>) => void
}) {
  const { t } = useTranslation()
  const typeName = useId()
  const folderId = useId()

  return (
    <li className="min-w-0 border-2 border-rule bg-well px-4 py-3">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <Checkbox
          label={t('routes.newLibrary.tick')}
          checked={ticked}
          disabled={locked}
          onChange={(next) => onChange({ ticked: next })}
        />
        <span className={`label ml-auto px-1.5 py-0.5 ${SIGNAL_FILL.neutral}`}>
          {t('routes.newLibrary.badge')}
        </span>
      </div>

      {!ticked && (
        <p className="mt-2 max-w-prose text-xs text-ink-dim">{t('routes.newLibrary.when')}</p>
      )}

      {ticked && (
        <div className="mt-3 grid gap-4 border-t-2 border-rule pt-3">
          <p className="max-w-prose text-xs text-ink">{t('routes.newLibrary.visible')}</p>

          <fieldset className="grid gap-2" disabled={locked}>
            <legend className="label text-ink-dim">{t('jellyfin.bundled.list.type')}</legend>
            <div className="flex flex-wrap gap-x-6 gap-y-2">
              {TYPES.map((option) => (
                <label key={option} className="flex items-center gap-x-2 text-sm text-ink">
                  <input
                    type="radio"
                    name={typeName}
                    value={option}
                    checked={type === option}
                    onChange={() => onChange({ type: option })}
                    className="size-4 shrink-0 accent-[var(--color-assigned)] disabled:cursor-not-allowed"
                  />
                  {t(`jellyfin.bundled.list.types.${option}`)}
                </label>
              ))}
            </div>
          </fieldset>

          <Field
            label={t('jellyfin.bundled.list.name')}
            value={name}
            disabled={locked}
            autoComplete="off"
            error={
              problem && problem.reason !== 'folder_taken'
                ? t(NAME_PROBLEM[problem.reason], {
                    holder: problem.reason === 'name_taken' ? problem.holder : '',
                  })
                : undefined
            }
            onChange={(event) => onChange({ name: event.target.value })}
          />

          <div className="grid gap-2">
            <span id={folderId} className="label text-ink-dim">
              {t('jellyfin.bundled.list.folder')}
            </span>
            <span aria-labelledby={folderId} className="value text-xs wrap-anywhere text-ink">
              {path}
            </span>
            {problem?.reason === 'folder_taken' ? (
              <span role="alert" className="text-xs text-blocked-ink">
                {t('routes.newLibrary.problem.folder_taken', { holder: problem.holder, path })}
              </span>
            ) : (
              <span className="text-xs text-ink-dim">{t('routes.newLibrary.folderHint')}</span>
            )}
          </div>
        </div>
      )}
    </li>
  )
}
