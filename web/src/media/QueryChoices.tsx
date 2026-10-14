import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { NameChip, NameKind, QueryChoice, QueryPlan } from '../api/search'
import { seasonCode } from '../components/episodes'
import { ExpandHint } from '../components/ExpandHint'
import { ToggleChips, type ToggleChip } from '../components/ToggleChips'

/** 「不指定季」那一顆的值。逐季那幾顆的值是季號的字串。 */
const ANY_SEASON = 'any'

/**
 * 按搜尋之前，要拿哪幾個名字、哪幾季去問（M4 票 84，`.scratch/m4/search-choose-shape.md`）。
 *
 * 一個名字一顆 chip，帶它是哪幾種（英文名、原名…）；別名三十幾個，收在一個展開區，摘要說有幾個、開了幾個。
 * 季是「不指定季」加逐季一顆，只在照作品名搜時畫：搜缺的集時缺的形狀決定問哪幾季（`seasons` 傳 `false`）。
 *
 * 這裡只畫、只回報新的選擇；查詢由後端照它算（`GET /api/search/queries`），記不記住由呼叫端決定——
 * 按了哪一顆、它是哪幾種都在 `onName` 的參數裡。
 */
export function QueryChoices({
  plan,
  choice,
  seasons,
  onChange,
  onName,
}: {
  plan: QueryPlan
  choice: QueryChoice
  seasons: boolean
  onChange: (choice: QueryChoice) => void
  onName: (chip: NameChip, on: boolean) => void
}) {
  const { t } = useTranslation()
  const names = new Set(choice.names)
  const main = plan.names.filter((chip) => !chip.kinds.includes('alias'))
  const aliases = plan.names.filter((chip) => chip.kinds.includes('alias'))
  const aliasesOn = aliases.filter((chip) => names.has(chip.name)).length
  const pressedSeasons = new Set([
    ...(choice.anySeason ? [ANY_SEASON] : []),
    ...choice.seasons.map(String),
  ])

  function toggleName(name: string) {
    const chip = plan.names.find((one) => one.name === name)
    if (!chip) return
    const on = !names.has(name)
    // 照 chip 的順序存，不照按的順序：送出去的參數與預覽才不跟著按的順序變。
    onChange({
      ...choice,
      names: plan.names
        .map((one) => one.name)
        .filter((one) => (one === name ? on : names.has(one))),
    })
    onName(chip, on)
  }

  function toggleSeason(value: string) {
    if (value === ANY_SEASON) {
      onChange({ ...choice, anySeason: !choice.anySeason })
      return
    }
    const number = Number(value)
    const opened = choice.seasons.includes(number)
      ? choice.seasons.filter((one) => one !== number)
      : [...choice.seasons, number].sort((a, b) => a - b)
    onChange({ ...choice, seasons: opened })
  }

  const nameChip = (chip: NameChip): ToggleChip<string> => ({
    value: chip.name,
    label: chip.name,
    machine: true,
    note: chip.kinds.map((kind: NameKind) => t(`search.kind.${kind}`)).join(' · '),
  })

  return (
    <div className="grid gap-4">
      <ChoiceRow label={t('search.choose.names')}>
        <ToggleChips
          label={t('search.choose.namesGroup')}
          chips={main.map(nameChip)}
          selected={names}
          onToggle={toggleName}
        />
        {aliases.length > 0 && (
          <details className="group min-w-0">
            <summary className="flex w-fit cursor-pointer flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-dim marker:content-none">
              <span>
                {t('search.choose.aliases', { count: aliases.length })}
                {aliasesOn > 0 ? t('search.choose.aliasesOn', { count: aliasesOn }) : ''}
              </span>
              <ExpandHint />
            </summary>
            <div className="mt-2">
              <ToggleChips
                label={t('search.choose.aliasesGroup')}
                chips={aliases.map(nameChip)}
                selected={names}
                onToggle={toggleName}
              />
            </div>
          </details>
        )}
      </ChoiceRow>
      {seasons && plan.seasons.length > 0 && (
        <ChoiceRow label={t('search.choose.seasons')}>
          <ToggleChips
            label={t('search.choose.seasonsGroup')}
            chips={[
              { value: ANY_SEASON, label: t('search.choose.anySeason') },
              ...plan.seasons.map((one) => ({
                value: String(one.number),
                label: seasonCode(one.number),
              })),
            ]}
            selected={pressedSeasons}
            onToggle={toggleSeason}
          />
        </ChoiceRow>
      )}
    </div>
  )
}

/**
 * 一組：標籤在上、chip 在下，所有寬度都一樣（M4 票 84b 推翻票 84 的左欄標籤）：關鍵字、預覽、資料夾名的
 * 標籤都在欄位上方，左欄那一條軸讓 chip 從一個跟上下都對不齊的 x 起跑。
 */
function ChoiceRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-2">
      <p className="label text-ink-dim">{label}</p>
      <div className="grid min-w-0 gap-2">{children}</div>
    </div>
  )
}
