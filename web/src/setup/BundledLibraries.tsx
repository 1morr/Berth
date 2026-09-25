import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { COMPACT_BUTTON, Field, GhostButton } from '../components/controls'
import { SIGNAL_FILL } from '../components/signal'
import type { LibraryDraft } from '../api/setup'
import { folderFor, pathUnder, type RowProblems } from './libraryRules'
import { type DraftRow, type LibraryDraftState } from './useLibraryDraft'

const TYPES = ['movies', 'tvshows'] as const satisfies readonly LibraryDraft['collection_type'][]

/**
 * 套件內 Jellyfin 要建的媒體庫（票 06f）。慣例是 Jellyfin 自己啟動精靈的「新增媒體庫」：
 * 內容類型 + 顯示名稱 + 資料夾。這一份清單就是泊位 1 的剖面——按下「開始靠泊」之前改得動，
 * 按下去之後建好的那幾列鎖住（改名、刪除要去 Jellyfin），還沒建的照樣能加能刪，重跑只建它們。
 */

export function BundledLibraries({
  draft,
  libraryRoot,
  locked,
  saving,
  saveFailed,
}: {
  draft: LibraryDraftState
  libraryRoot: string
  /** 靠泊序列正在跑：清單整份停住，跑完再說。 */
  locked: boolean
  saving: boolean
  /** 存不下來的那一句（後端的拒絕或請求沒跑完），沒有就是 `null`。 */
  saveFailed: string | null
}) {
  const { t } = useTranslation()
  const { rows, setRows, problems } = draft
  const [focusKey, setFocusKey] = useState<number | null>(null)
  const anyBuilt = rows.some((row) => row.built)

  function change(key: number, patch: Partial<LibraryDraft>) {
    setRows(
      rows.map((row) => {
        if (row.key !== key) return row
        const next = { ...row, ...patch }
        if (patch.folder !== undefined) return { ...next, folderEdited: true }
        if (patch.name !== undefined && !row.folderEdited) {
          return { ...next, folder: folderFor(patch.name) }
        }
        return next
      }),
    )
  }

  function add() {
    const key = Math.max(-1, ...rows.map((row) => row.key)) + 1
    setRows([
      ...rows,
      { key, name: '', collection_type: 'tvshows', folder: '', built: false, folderEdited: false },
    ])
    setFocusKey(key)
  }

  return (
    <section className="border-2 border-rule bg-well">
      <h3 className="label border-b-2 border-rule bg-deck px-4 py-2.5 text-ink-dim">
        {t('jellyfin.bundled.list.title')}
      </h3>
      <p className="px-4 pt-3 text-xs text-ink-dim">{t('jellyfin.bundled.list.lede')}</p>

      <ol className="divide-y-2 divide-rule">
        {rows.map((row, index) =>
          row.built ? (
            <BuiltRow key={row.key} row={row} libraryRoot={libraryRoot} />
          ) : (
            <EditableRow
              key={row.key}
              row={row}
              position={index + 1}
              libraryRoot={libraryRoot}
              problems={problems.rows[index] ?? {}}
              locked={locked}
              focus={row.key === focusKey}
              onChange={(patch) => change(row.key, patch)}
              onRemove={() => setRows(rows.filter((other) => other.key !== row.key))}
            />
          ),
        )}
      </ol>

      <div className="grid gap-3 border-t-2 border-rule px-4 py-3">
        {problems.empty && (
          <p role="alert" className="text-xs text-blocked-ink">
            {t('jellyfin.bundled.list.problem.empty')}
          </p>
        )}
        <div>
          <GhostButton type="button" disabled={locked} onClick={add}>
            {t('jellyfin.bundled.list.add')}
          </GhostButton>
        </div>
        {anyBuilt && <p className="text-xs text-ink-dim">{t('jellyfin.bundled.list.builtHint')}</p>}
        <p aria-live="polite" className="text-xs text-ink-dim">
          {saveFailed ? (
            <span className="text-blocked-ink">{saveFailed}</span>
          ) : saving ? (
            t('jellyfin.bundled.list.saving')
          ) : draft.blocked ? (
            t('jellyfin.bundled.list.unsaved')
          ) : (
            ''
          )}
        </p>
      </div>
    </section>
  )
}

function EditableRow({
  row,
  position,
  libraryRoot,
  problems,
  locked,
  focus,
  onChange,
  onRemove,
}: {
  row: DraftRow
  position: number
  libraryRoot: string
  problems: RowProblems
  locked: boolean
  focus: boolean
  onChange: (patch: Partial<LibraryDraft>) => void
  onRemove: () => void
}) {
  const { t } = useTranslation()
  const typeId = useId()
  const path = pathUnder(libraryRoot, row.folder.trim() || '…')
  const label = row.name.trim() || t('jellyfin.bundled.list.unnamed', { position })

  return (
    <li className="px-4 py-4">
      <fieldset className="grid min-w-0 gap-3">
        <legend className="sr-only">{label}</legend>
        <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,9rem)]">
          <Field
            label={t('jellyfin.bundled.list.name')}
            value={row.name}
            disabled={locked}
            autoComplete="off"
            // 只在掛上的那一刻：新加的那一列，焦點直接落在它的名稱上。
            autoFocus={focus}
            error={problems.name ? t(`jellyfin.bundled.list.problem.${problems.name}`) : undefined}
            onChange={(event) => onChange({ name: event.target.value })}
          />
          <p className="grid content-start gap-2">
            <label htmlFor={typeId} className="label text-ink-dim">
              {t('jellyfin.bundled.list.type')}
            </label>
            <select
              id={typeId}
              value={row.collection_type}
              disabled={locked}
              onChange={(event) =>
                onChange({ collection_type: event.target.value as LibraryDraft['collection_type'] })
              }
              className="value w-full border-2 border-rule-strong bg-hull px-3 py-2.5 text-sm text-ink focus:border-ink disabled:bg-well disabled:text-ink-dim"
            >
              {TYPES.map((type) => (
                <option key={type} value={type}>
                  {t(`jellyfin.bundled.list.types.${type}`)}
                </option>
              ))}
            </select>
          </p>
        </div>
        <Field
          label={t('jellyfin.bundled.list.folder')}
          value={row.folder}
          disabled={locked}
          autoComplete="off"
          hint={<span className="value wrap-anywhere">{path}</span>}
          error={
            problems.folder ? t(`jellyfin.bundled.list.problem.${problems.folder}`) : undefined
          }
          onChange={(event) => onChange({ folder: event.target.value })}
        />
        <div>
          <button
            type="button"
            disabled={locked}
            onClick={onRemove}
            aria-label={t('jellyfin.bundled.list.removeNamed', { name: label })}
            className={`${COMPACT_BUTTON} disabled:cursor-not-allowed disabled:text-ink-dim`}
          >
            {t('jellyfin.bundled.list.remove')}
          </button>
        </div>
      </fieldset>
    </li>
  )
}

/** 已經在 Jellyfin 建好的一列：只讀。改名與刪除去 Jellyfin（`builtHint`）。 */
function BuiltRow({ row, libraryRoot }: { row: DraftRow; libraryRoot: string }) {
  const { t } = useTranslation()

  return (
    <li className="grid gap-1 px-4 py-3">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className={`label px-2 py-1 ${SIGNAL_FILL.neutral}`}>
          {t('jellyfin.bundled.list.built')}
        </span>
        <span className="value text-sm font-semibold text-ink">{row.name}</span>
        <span className="label ml-auto text-ink-dim">
          {t(`jellyfin.bundled.list.types.${row.collection_type}`)}
        </span>
      </div>
      <span className="value text-xs wrap-anywhere text-ink-dim">
        {pathUnder(libraryRoot, row.folder)}
      </span>
    </li>
  )
}
