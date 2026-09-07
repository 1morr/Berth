import type { ReactNode } from 'react'

/**
 * 剖面即預覽：把「將會做什麼」切開露出來，套用前後看同一個剖面（direction contract）。
 * 值貼在它那一行，不進散文。
 */
export function Cutaway({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="border-2 border-rule bg-well">
      <h3 className="label border-b-2 border-rule bg-deck px-4 py-2.5 text-ink-dim">{title}</h3>
      <dl className="divide-y divide-rule">{children}</dl>
    </section>
  )
}

export function CutawayRow({
  term,
  value,
  muted = false,
}: {
  term: string
  value: ReactNode
  muted?: boolean
}) {
  return (
    <div className="grid grid-cols-1 gap-1 px-4 py-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] sm:gap-4">
      <dt className="label min-w-0 self-center break-all text-ink-dim">{term}</dt>
      <dd className={`value min-w-0 break-words text-sm ${muted ? 'text-ink-dim' : 'text-ink'}`}>
        {value}
      </dd>
    </div>
  )
}
