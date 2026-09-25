import type { ReactNode } from 'react'

/**
 * 剖面即預覽：把「將會做什麼」切開露出來，套用前後看同一個剖面（direction contract）。
 * 值貼在它那一行，不進散文。
 */
export function Cutaway({
  title,
  level = 3,
  children,
}: {
  title: string
  /** 標題層級跟著它所在的頁面：精靈裡它在步驟的 h2 底下，Media 詳情裡它緊接著 h1（票 15 audit）。 */
  level?: 2 | 3
  children: ReactNode
}) {
  const Heading = level === 2 ? 'h2' : 'h3'
  return (
    <section className="border-2 border-rule bg-well">
      <Heading className="label border-b-2 border-rule bg-deck px-4 py-2.5 text-ink-dim">
        {title}
      </Heading>
      <dl className="divide-y divide-rule">{children}</dl>
    </section>
  )
}

export function CutawayRow({
  term,
  value,
  muted = false,
  code = false,
}: {
  term: string
  value: ReactNode
  muted?: boolean
  /**
   * term 是機器字串（API 端點、設定鍵）而不是角色名。
   *
   * `.label` 對拉丁文會 `text-transform: uppercase`，套在端點上就會把
   * `POST /Library/VirtualFolders` 印成 `POST /LIBRARY/VIRTUALFOLDERS`——右欄的纜繩列
   * 同一畫面印的是正確的那一個，於是同九個端點兩種大小寫，其中一種不是真的端點。
   * 中文版沒事（`text-transform: none`），所以這個 bug 只有英文使用者看得到。
   */
  code?: boolean
}) {
  return (
    <div className="grid grid-cols-1 gap-1 px-4 py-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] sm:gap-4">
      <dt
        className={`min-w-0 self-center leading-[1.4] text-ink-dim ${
          code ? 'value text-xs wrap-anywhere' : 'label'
        }`}
      >
        {term}
      </dt>
      <dd className={`value min-w-0 wrap-anywhere text-sm ${muted ? 'text-ink-dim' : 'text-ink'}`}>
        {value}
      </dd>
    </div>
  )
}
