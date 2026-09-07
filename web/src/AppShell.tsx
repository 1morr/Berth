import { Outlet } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

/** 每一頁共用的外框。導覽在有第二頁時才長出來（票 05 起）。 */
export function AppShell() {
  const { t } = useTranslation()

  return (
    <div className="min-h-dvh bg-canvas text-ink">
      <header className="border-b border-edge px-6 py-4">
        <h1 className="text-xl font-semibold tracking-tight">{t('app.name')}</h1>
        <p className="text-sm text-ink-muted">{t('app.tagline')}</p>
      </header>
      <main className="mx-auto max-w-3xl px-6 py-8">
        <Outlet />
      </main>
    </div>
  )
}
