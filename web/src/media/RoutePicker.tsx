import { useId } from 'react'
import { useTranslation } from 'react-i18next'

import type { Media } from '../api/media'
import { SettingsHint } from '../components/SettingsHint'

/**
 * 「入庫到哪裡」那一行（票 04b、`.scratch/m1/search-results-shape.md` §4）。
 *
 * 這是一個**偏好，不是承諾**：選了不會寫進任何地方。票 09 的送單把它當 body 送，
 * `media.default_route_id` 由送單成功時寫成「上次用的」。為了一個下拉的初值多一支
 * `PUT /media/{id}/route` 不划算。搜尋不看它（票 14e）。
 *
 * **它住在搜尋區塊裡**（使用者 2026-09-10 拍板，推翻 `media-detail-shape.md` §3 的
 * 「不動身分帶」）：當時的理由是它驅動查詢變體，留在身分帶等於一個按了沒反應的控制項。
 * 票 14e 起查詢不看它，它驅動的是結果表裡每一列的送單，位置不變。
 *
 * 受控元件：狀態在 `SearchPanel`，因為結果表裡每一列的送單都要讀它。
 */
export function RoutePicker({
  media,
  value,
  onChange,
}: {
  media: Media
  value: number | null
  onChange: (route: number | null) => void
}) {
  const { t } = useTranslation()
  const selectId = useId()

  if (media.routes.length === 0) return <NoRoutes kind={media.kind} />

  return (
    <p className="grid gap-2">
      <label htmlFor={selectId} className="label text-ink-dim">
        {t('media.route.label')}
      </label>
      <select
        id={selectId}
        value={value ?? ''}
        onChange={(event) =>
          onChange(event.target.value === '' ? null : Number(event.target.value))
        }
        className="value w-full border-2 border-rule-strong bg-hull px-3 py-2.5 text-sm text-ink focus:border-ink"
      >
        <option value="">{t('media.route.none')}</option>
        {media.routes.map((route) => (
          <option key={route.id} value={route.id}>
            {route.name}
          </option>
        ))}
      </select>
    </p>
  )
}

/**
 * 一條相符的 Route 都沒有：說得出下一步，而不是給一個空的下拉。
 *
 * 設定頁只有 admin 進得去（後端同時回 403），所以那條連結也只給 admin——
 * 對一般使用者它是死路，而他要的是「去叫管理員」（票 10 code-review 的同一條）。
 */
function NoRoutes({ kind }: { kind: Media['kind'] }) {
  const { t } = useTranslation()

  return (
    <div className="grid gap-3 border-2 border-rule bg-well px-3 py-3">
      <p className="max-w-prose text-sm text-ink">{t(`media.route.missing.${kind}`)}</p>
      {/* 媒體庫路徑那一頁：Route 在那裡新增。 */}
      <SettingsHint slot="library" fallback={t('media.route.askAdmin')} />
    </div>
  )
}
