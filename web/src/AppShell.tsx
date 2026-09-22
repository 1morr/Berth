import type { ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { meQueryOptions, signOut } from './api/auth'
import { GhostButton, NAV_BOX, NAV_BOX_ACTIVE } from './components/controls'
import { LanguageToggle } from './components/LanguageToggle'

/**
 * setup 完成之後的頁面共用的外框。
 *
 * `main` 不設寬度上限：健康頁的泊位板是整寬的橫幅（direction contract 的 FIRST VIEWPORT），
 * 每一頁自己決定內文那一欄有多寬。
 */
export function AppShell({ children }: { children: ReactNode }) {
  const { t } = useTranslation()

  return (
    <div className="min-h-dvh bg-hull text-ink">
      {/* 頁首有八個 Tab 停留點；鍵盤使用者每換一頁都要先過完它們（票 15 audit）。
          平常看不見，拿到焦點才浮出來。`not-sr-only` 會把 padding 歸零，所以浮出時的 padding
          寫在 `focus:` 那一組（票 15 實跑量到 58×15px）。 */}
      <a
        href="#main"
        className="label sr-only border-2 border-rule-strong bg-deck text-ink focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:px-4 focus:py-2.5"
      >
        {t('nav.skip')}
      </a>
      <header className="flex flex-wrap items-center gap-x-6 gap-y-3 border-b-2 border-rule-strong px-6 py-4">
        <div>
          <p className="value text-lg font-semibold tracking-tight">{t('app.name')}</p>
          <p className="text-sm text-ink-dim">{t('app.tagline')}</p>
        </div>
        <span className="ml-auto">
          <Identity />
        </span>
      </header>
      {/* `tabIndex={-1}`：skip link 跳過來時焦點要真的落在這裡，下一個 Tab 才從內容開始。 */}
      <main id="main" tabIndex={-1} className="outline-none">
        {children}
      </main>
    </div>
  )
}

/** 導覽的一項。當前頁用重橫線標出來，不是靠顏色（狀態不只靠顏色，PRODUCT.md）。 */
function NavLink({
  to,
  children,
}: {
  to: '/' | '/library' | '/jobs' | '/issues' | '/health' | '/settings'
  children: ReactNode
}) {
  return (
    <Link
      to={to}
      // `/` 是每一條路徑的前綴，預設的模糊比對會讓探索永遠是「當前頁」。
      activeOptions={{ exact: to === '/' }}
      className={`${NAV_BOX} px-4 py-2.5`}
      activeProps={{ className: `${NAV_BOX_ACTIVE} px-4 py-2.5` }}
    >
      {children}
    </Link>
  )
}

/**
 * 誰登入了、他是什麼角色、他能去哪裡（票 07）。
 *
 * 角色用**中性色塊**：四個信號色各自只有一個意思，角色不是狀態，不能借用它們。
 * 它仍然要看得見——`user` 因此知道自己為什麼沒有「設定」那顆按鈕，而不是以為壞了。
 */
function Identity() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const me = useQuery(meQueryOptions)

  const leave = useMutation({
    mutationFn: signOut,
    onSettled: async () => {
      // 登出後整份快取都不再屬於這個人。
      queryClient.clear()
      await navigate({ to: '/login' })
    },
  })

  if (!me.data) return <LanguageToggle />

  // `items-stretch`：語言切換原本比旁邊兩顆按鈕矮一截，這一列才對得齊。
  return (
    <div className="flex flex-wrap items-stretch gap-x-4 gap-y-2">
      <span className="flex items-center gap-2">
        <span className="label bg-deck px-2 py-1.5 text-ink">{t(`role.${me.data.role}`)}</span>
        <span className="value text-sm text-ink">{me.data.name}</span>
      </span>
      {/* 導覽是 landmark：螢幕閱讀器的地標清單跳得到它（M0 的 critique 記過，票 15 收掉）。 */}
      <nav aria-label={t('nav.label')} className="flex flex-wrap items-stretch gap-x-4 gap-y-2">
        <NavLink to="/">{t('nav.discover')}</NavLink>
        <NavLink to="/library">{t('nav.inventory')}</NavLink>
        <NavLink to="/jobs">{t('nav.jobs')}</NavLink>
        {/* 待處理與設定同一個規則：修正是 admin 的事（plan §6），後端同時回 403。 */}
        {me.data.role === 'admin' && <NavLink to="/issues">{t('nav.issues')}</NavLink>}
        <NavLink to="/health">{t('nav.health')}</NavLink>
        {/* 連 `/settings` 而不是第一個分頁：前綴比對讓它在兩個設定頁上都是當前頁（票 14a）。 */}
        {me.data.role === 'admin' && <NavLink to="/settings">{t('nav.settings')}</NavLink>}
      </nav>
      <GhostButton type="button" disabled={leave.isPending} onClick={() => leave.mutate()}>
        {leave.isPending ? t('nav.signingOut') : t('nav.signOut')}
      </GhostButton>
      <LanguageToggle />
    </div>
  )
}
