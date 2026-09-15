import { useTranslation } from 'react-i18next'

import type { Profile } from '../api/schemas'

/**
 * 命名與解析偏好（CONTEXT.md 的 Profile）。劇集類型才問——電影沒有 anime 這條路徑。
 *
 * 精靈泊位 4 與 Route 設定頁共用（票 14）。`group` 是原生 radio 群組的 `name`：同一頁上有好幾組時
 * 各自要不同，否則方向鍵會在兩組之間跳，螢幕閱讀器也會把它們念成同一組。
 */
export function ProfilePicker({
  group,
  value,
  onPick,
}: {
  group: string
  value: Profile
  onPick: (profile: Profile) => void
}) {
  const { t } = useTranslation()

  return (
    <fieldset className="grid gap-2">
      <legend className="label text-ink-dim">{t('routes.picker.profile')}</legend>
      <div className="flex flex-wrap gap-4">
        {(['standard', 'anime'] as const).map((profile) => (
          <label key={profile} className="flex items-center gap-2">
            <input
              type="radio"
              name={group}
              value={profile}
              checked={value === profile}
              onChange={() => onPick(profile)}
              className="size-4 shrink-0 accent-[var(--color-assigned)]"
            />
            <span className="text-sm text-ink">{t(`routes.profile.${profile}`)}</span>
          </label>
        ))}
      </div>
    </fieldset>
  )
}
