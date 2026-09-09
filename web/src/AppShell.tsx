import type { ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { meQueryOptions, signOut } from './api/auth'
import { GhostButton } from './components/controls'
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
      <header className="flex flex-wrap items-center gap-x-6 gap-y-3 border-b-2 border-rule-strong px-6 py-4">
        <div>
          <p className="value text-lg font-semibold tracking-tight">{t('app.name')}</p>
          <p className="text-sm text-ink-dim">{t('app.tagline')}</p>
        </div>
        <span className="ml-auto">
          <Identity />
        </span>
      </header>
      <main>{children}</main>
    </div>
  )
}

/** 導覽的一項。當前頁用重橫線標出來，不是靠顏色（狀態不只靠顏色，PRODUCT.md）。 */
function NavLink({
  to,
  children,
}: {
  to: '/' | '/health' | '/settings/services'
  children: ReactNode
}) {
  return (
    <Link
      to={to}
      // `/` 是每一條路徑的前綴，預設的模糊比對會讓探索永遠是「當前頁」。
      activeOptions={{ exact: to === '/' }}
      className="label border-2 border-rule px-4 py-2.5 hover:border-rule-strong"
      activeProps={{ className: 'label border-2 border-rule-strong bg-deck px-4 py-2.5' }}
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
      <NavLink to="/">{t('nav.discover')}</NavLink>
      <NavLink to="/health">{t('nav.health')}</NavLink>
      {me.data.role === 'admin' && <NavLink to="/settings/services">{t('nav.settings')}</NavLink>}
      <GhostButton type="button" disabled={leave.isPending} onClick={() => leave.mutate()}>
        {leave.isPending ? t('nav.signingOut') : t('nav.signOut')}
      </GhostButton>
      <LanguageToggle />
    </div>
  )
}
