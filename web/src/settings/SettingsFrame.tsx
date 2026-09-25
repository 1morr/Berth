import type { ReactNode } from 'react'

import { PAGE_TITLE } from '../components/controls'
import { SettingsTabs } from '../components/SettingsTabs'

/**
 * 設定頁的骨架：分頁列、這一頁唯一的 `<h1>`、一句 lede，底下是單欄的區塊（票 06i 的 shape）。
 *
 * 精靈的泊位板、剖面、上一個 / 下一個不帶過來：來這裡的人是來改一件事的，不是來重走一次靠泊。
 */
export function SettingsFrame({
  title,
  lede,
  children,
}: {
  title: string
  lede: string
  children: ReactNode
}) {
  return (
    <div className="mx-auto w-full max-w-3xl px-6 py-8">
      <SettingsTabs />
      <h1 className={`mt-6 ${PAGE_TITLE}`}>{title}</h1>
      <p className="mt-2 max-w-prose text-sm text-ink-dim">{lede}</p>
      <div className="mt-6 grid gap-8">{children}</div>
    </div>
  )
}

/** 一頁裡的一個區塊。標題是 `<h2>`，`aria-labelledby` 讓區塊本身有名字。 */
export function SettingsSection({
  id,
  title,
  lede,
  children,
}: {
  id: string
  title: string
  lede?: string
  children: ReactNode
}) {
  return (
    <section aria-labelledby={id} className="min-w-0">
      <h2 id={id} className="value text-sm font-semibold text-ink">
        {title}
      </h2>
      {lede && <p className="mt-2 max-w-prose text-xs text-ink-dim">{lede}</p>}
      <div className="mt-3">{children}</div>
    </section>
  )
}
