import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { LanguageToggle } from './components/LanguageToggle'

/** setup 完成之後的頁面共用的外框。導覽在有更多頁時才長出來（票 10 起）。 */
export function AppShell({ children }: { children: ReactNode }) {
  const { t } = useTranslation()

  return (
    <div className="min-h-dvh bg-hull text-ink">
      <header className="flex flex-wrap items-center gap-x-6 gap-y-3 border-b-2 border-rule-strong px-6 py-4">
        <div>
          <p className="value text-lg font-semibold tracking-tight">{t('app.name')}</p>
          <p className="text-sm text-ink-dim">{t('app.tagline')}</p>
        </div>
        <span className="ml-auto">
          <LanguageToggle />
        </span>
      </header>
      <main className="mx-auto max-w-3xl px-6 py-8">{children}</main>
    </div>
  )
}
