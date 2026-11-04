import { useEffect, useId, useRef, useState, type KeyboardEvent, type FocusEvent } from 'react'
import { Link, useRouterState } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import type { Me } from '../api/auth'
import { GhostButton, NAV_BOX, NAV_BOX_ACTIVE, NAV_LINK } from '../components/controls'
import { LanguageToggle } from '../components/LanguageToggle'
import { useSignOut } from '../components/useSignOut'
import { ACCOUNT_PAGES, inSection } from './sections'

/**
 * 帳號選單（M5.5 票 07，`.scratch/m5.5/navigation-shape.md`）：名字與角色、設定、健康、週報（只有
 * admin）、語言、登出。Berth 的第一個下拉選單。
 *
 * **disclosure，不是 `role="menu"`**（WAI-ARIA APG 的 Disclosure Navigation Menu）：裡面是一般的連結與
 * 按鈕，Tab 依序走，不搶方向鍵。不用 `<details>`（`Esc` 與點外面都不會收）也不用 `popover`（jsdom 沒有，
 * 定位要 anchor positioning）。
 *
 * - `Esc` 收起，焦點回到觸發鍵（同 The Focus Follows The Confirm Rule）。
 * - Tab 走出選單、或點選單外面收起，焦點留在使用者放的地方。
 * - 點了連結收起（換頁）；換語言不收：還要看一眼換好了沒。
 */
export function AccountMenu({ me }: { me: Me }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const panelId = useId()
  const pathname = useRouterState({ select: (state) => state.location.pathname })
  const leave = useSignOut()
  const here = inSection(pathname, ACCOUNT_PAGES)

  useEffect(() => {
    if (!open) return
    const onPointerDown = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('pointerdown', onPointerDown)
    return () => document.removeEventListener('pointerdown', onPointerDown)
  }, [open])

  function onKeyDown(event: KeyboardEvent) {
    if (event.key !== 'Escape' || !open) return
    setOpen(false)
    trigger.current?.focus()
  }

  function onBlur(event: FocusEvent) {
    // `relatedTarget` 是 `null` 時是點到選單裡不能聚焦的地方（名字那一行）或整個視窗失焦：不收。
    // 點到外面由 `pointerdown` 收。
    const next = event.relatedTarget
    if (next instanceof Node && !root.current?.contains(next)) setOpen(false)
  }

  const close = () => setOpen(false)

  return (
    <div ref={root} onKeyDown={onKeyDown} onBlur={onBlur} className="relative">
      <button
        ref={trigger}
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={t('nav.account', { name: me.name })}
        onClick={() => setOpen((was) => !was)}
        // 選單裡的頁面是當前頁時，觸發鍵畫成當前、也說出來（同 `SectionLink` 在區塊別頁的 `true`）：
        // 設定、健康、週報不在頁首上了，人要知道自己在哪。展開與否由 `aria-expanded` 與面板本身說，不換漆。
        aria-current={here ? 'true' : undefined}
        className={`${here ? NAV_BOX_ACTIVE : NAV_BOX} inline-flex min-h-full items-center px-4 py-2.5 text-ink`}
      >
        {/* 名字是機器字串：`.value` 原樣，不被 `.label` 的大寫與字距改掉（The Machine String Rule）。 */}
        <span className="value max-w-[12rem] text-sm tracking-normal wrap-anywhere normal-case">
          {me.name}
        </span>
        <span aria-hidden="true" className="ml-2">
          ▾
        </span>
      </button>
      {open && (
        <div
          id={panelId}
          className="absolute top-full right-0 z-20 mt-2 grid w-max max-w-[calc(100vw-3rem)] min-w-[15rem] gap-4 border-2 border-rule-strong bg-deck p-4"
        >
          <p className="flex flex-wrap items-center gap-2">
            <span className="value text-sm wrap-anywhere text-ink">{me.name}</span>
            <span className="label bg-hull px-2 py-1.5 text-ink">{t(`role.${me.role}`)}</span>
          </p>
          <ul className="grid gap-2">
            <li>
              {/* 連 `/settings` 而不是第一個分頁：前綴比對讓它在每個設定頁上都是當前頁（票 14a）。
                  每個人都有：一般使用者的設定只有通知那一頁（M4 票 125）。 */}
              <Link to="/settings" onClick={close} className={`${NAV_LINK} block px-3 py-2`}>
                {t('nav.settings')}
              </Link>
            </li>
            <li>
              <Link to="/health" onClick={close} className={`${NAV_LINK} block px-3 py-2`}>
                {t('nav.health')}
              </Link>
            </li>
            {/* 週報說的是審核、Issue、RSS 那幾頁的事，那幾頁只有管理員進得去（M4 票 131）。 */}
            {me.role === 'admin' && (
              <li>
                <Link to="/weekly" onClick={close} className={`${NAV_LINK} block px-3 py-2`}>
                  {t('nav.weekly')}
                </Link>
              </li>
            )}
          </ul>
          {/* 面板是 `deck` 底，語言鍵選中那顆也是 `deck`：直接放上來，選中的與面板融在一起、沒選的反而像按下的
              （M5.5 票 19 的 critique）。墊一塊 `hull` 底，回到它在頁首時的樣子；前面一行說它是什麼。 */}
          <div className="flex flex-wrap items-center gap-3">
            <span aria-hidden="true" className="label text-ink-dim">
              {t('language.label')}
            </span>
            <div className="bg-hull p-1">
              <LanguageToggle />
            </div>
          </div>
          <div className="justify-self-start">
            <GhostButton type="button" busy={leave.isPending} onClick={() => leave.mutate()}>
              {leave.isPending ? t('nav.signingOut') : t('nav.signOut')}
            </GhostButton>
          </div>
        </div>
      )}
    </div>
  )
}
