import { useId } from 'react'

import type { Candidate } from '../api/rss'
import type { DiscoverItem } from '../api/discover'

// 待綁定那一列的「綁定」（`SeriesBinder`）與一次性 RSS 連結（`OneshotSection`，票 18）共用：
// 同樣是「搜一部作品、挑一條 Route」。

/** 選得了的一部作品：搜尋結果（`DiscoverItem`）與自動綁定的候選（`Candidate`）共有的那幾格。 */
export type Pickable = Pick<DiscoverItem | Candidate, 'id' | 'kind' | 'title' | 'title_en' | 'year'>

/** 一串可選的作品，一部一顆鍵；選定的那一顆是按下的樣子。 */
export function Choices({
  label,
  items,
  picked,
  onPick,
  titleOf,
  aboutOf,
}: {
  label: string
  items: readonly Pickable[]
  picked: Pickable | null
  onPick: (item: Pickable) => void
  titleOf: (item: Pickable) => string
  aboutOf: (item: Pickable) => string
}) {
  const labelId = useId()
  return (
    <div className="grid gap-1">
      <p id={labelId} className="label text-ink-dim">
        {label}
      </p>
      <ul className="grid gap-1" aria-labelledby={labelId}>
        {items.map((item) => (
          <li key={item.id}>
            <button
              type="button"
              aria-pressed={picked?.id === item.id}
              onClick={() => onPick(item)}
              className={`value flex min-h-6 w-full flex-wrap items-baseline gap-x-2 border-2 px-3 py-2 text-left text-sm text-ink ${
                picked?.id === item.id
                  ? 'border-rule-strong bg-deck'
                  : 'border-rule hover:border-rule-strong'
              }`}
            >
              <span className="wrap-anywhere">{titleOf(item)}</span>
              <span className="text-xs text-ink-dim">{aboutOf(item)}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
