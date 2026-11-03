import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { AgentPanel, AgentToggle } from './agent/AgentPanel'
import { usePanel } from './agent/panelState'
import { useNarrow } from './agent/useNarrow'
import { meQueryOptions } from './api/auth'
import { waitingQueryOptions } from './api/waiting'
import { NAV_LINK } from './components/controls'
import { LanguageToggle } from './components/LanguageToggle'
import { AccountMenu } from './nav/AccountMenu'
import { SectionLink } from './nav/SectionLink'
import { AIRING_PAGES, WAITING_PAGES } from './nav/sections'

/**
 * setup 完成之後的頁面共用的外框。
 *
 * `main` 不設寬度上限：健康頁的泊位板是整寬的橫幅（direction contract 的 FIRST VIEWPORT），
 * 每一頁自己決定內文那一欄有多寬。
 *
 * 側面板（M5 票 12）在桌面是右邊的一欄，頁面讓位；窄版蓋滿整個視窗，底下這一頁 `inert`
 * （`.scratch/m5/side-panel-shape.md`）。
 */
export function AppShell({ children }: { children: ReactNode }) {
  const { open } = usePanel()
  const narrow = useNarrow()

  return (
    <div className="min-h-dvh bg-hull text-ink lg:flex">
      <div inert={open && narrow} className="min-w-0 flex-1">
        <Page>{children}</Page>
      </div>
      <AgentPanel narrow={narrow} />
    </div>
  )
}

function Page({ children }: { children: ReactNode }) {
  const { t } = useTranslation()
  const me = useQuery(meQueryOptions)

  return (
    <>
      {/* 鍵盤使用者每換一頁都要先過完頁首的停留點（票 15 audit）。平常看不見，拿到焦點才浮出來。
          `not-sr-only` 會把 padding 歸零，所以浮出時的 padding 寫在 `focus:` 那一組（票 15 實跑量到 58×15px）。 */}
      <a
        href="#main"
        className="label sr-only border-2 border-rule-strong bg-deck text-ink focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:px-4 focus:py-2.5"
      >
        {t('nav.skip')}
      </a>
      {/* 桌機一列：應用名、導覽、靠右的助理與帳號選單。窄版導覽自己一整列、放不下就換行
          （`order-last basis-full`），不收進漢堡選單：每一項與它的件數都看得到（M5.5 票 07）。 */}
      <header className="flex flex-wrap items-center gap-x-6 gap-y-3 border-b-2 border-rule-strong px-6 py-4">
        <div>
          <p className="value text-lg font-semibold tracking-tight">{t('app.name')}</p>
          {/* 窄版收起副標：第一列才放得下應用名、助理與帳號選單（M5.5 票 07）。 */}
          <p className="hidden text-sm text-ink-dim sm:block">{t('app.tagline')}</p>
        </div>
        {me.data && <MainNav admin={me.data.role === 'admin'} />}
        <div className="ml-auto flex flex-wrap items-stretch gap-x-4 gap-y-2">
          {me.data ? (
            <>
              {/* 不在導覽裡：它不換頁，是一顆開關（`aria-expanded`）。 */}
              <AgentToggle />
              <AccountMenu me={me.data} />
            </>
          ) : (
            <LanguageToggle />
          )}
        </div>
      </header>
      {/* `tabIndex={-1}`：skip link 跳過來時焦點要真的落在這裡，下一個 Tab 才從內容開始。 */}
      <main id="main" tabIndex={-1} className="outline-none">
        {children}
      </main>
    </>
  )
}

/** 導覽的一項。當前頁用重橫線標出來，不是靠顏色（狀態不只靠顏色，PRODUCT.md）。 */
function NavLink({ to, children }: { to: '/' | '/library' | '/jobs'; children: ReactNode }) {
  return (
    <Link
      to={to}
      // `/` 是每一條路徑的前綴，預設的模糊比對會讓探索永遠是「當前頁」。
      activeOptions={{ exact: to === '/' }}
      // `inline-flex items-center`：導覽項一律拉到同一列的高度（帶件數的那兩格比較高），字要置中。
      className={`${NAV_LINK} inline-flex items-center px-4 py-2.5`}
    >
      {children}
    </Link>
  )
}

/**
 * 主導覽（M5.5 票 07，`.scratch/m5.5/navigation-shape.md`）：探索、新番、媒體庫、下載、待處理。
 *
 * 新番連時間表、每個人都有（M5.5 票 09）；件數（待綁定）與待處理只有 admin（後端同時回 403）。件數各歸
 * 各頁：待處理是審核加 Issue、新番是待綁定，加起來就是 Discord「有 N 件等你處理」的 N。
 *
 * 導覽是 landmark：螢幕閱讀器的地標清單跳得到它（M0 的 critique 記過，票 15 收掉）。
 */
function MainNav({ admin }: { admin: boolean }) {
  const { t } = useTranslation()
  const counts = useQuery({ ...waitingQueryOptions, enabled: admin }).data

  return (
    <nav
      aria-label={t('nav.label')}
      className="order-last flex basis-full flex-wrap items-stretch gap-2 sm:order-none sm:basis-auto sm:gap-x-4"
    >
      <NavLink to="/">{t('nav.discover')}</NavLink>
      <SectionLink
        to="/schedule"
        pages={AIRING_PAGES}
        label={t('nav.airing')}
        count={admin ? counts?.rss : undefined}
      />
      <NavLink to="/library">{t('nav.inventory')}</NavLink>
      <NavLink to="/jobs">{t('nav.jobs')}</NavLink>
      {admin && (
        <SectionLink
          to="/review"
          pages={WAITING_PAGES}
          label={t('nav.waiting')}
          count={counts && counts.review + counts.issue}
        />
      )}
    </nav>
  )
}
