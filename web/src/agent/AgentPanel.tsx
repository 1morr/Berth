import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { flushSync } from 'react-dom'
import type { KeyboardEvent } from 'react'
import { useTranslation } from 'react-i18next'

import { agentStatusQueryOptions, type AgentStatus } from '../api/agent'
import { meQueryOptions } from '../api/auth'
import {
  GHOST_LINK,
  GhostButton,
  NAV_BOX,
  NAV_BOX_ACTIVE,
  Notice,
  TEXT_LINK,
} from '../components/controls'
import { alertText, unknownText } from '../usage/alerts'
import { Conversation } from './Conversation'
import { PanelFailed, PanelLoading } from './PanelStates'
import { INPUT_ID, PANEL_ID, PANEL_TITLE_ID, TOGGLE_ID, usePanel } from './panelState'
import { useNarrow } from './useNarrow'

/**
 * 頁首的「助理」鍵（M5 票 12，`.scratch/m5/side-panel-shape.md`〈與頁面的關係〉）。打開時是當前導覽
 * 那一種方塊（重線 + `deck`），不靠顏色；焦點跟著進面板。
 */
export function AgentToggle() {
  const { t } = useTranslation()
  const { open, setOpen } = usePanel()

  function toggle() {
    if (open) {
      setOpen(false)
      return
    }
    // 先把面板畫出來，焦點才有地方落。
    flushSync(() => setOpen(true))
    focusPanel()
  }

  return (
    <button
      id={TOGGLE_ID}
      type="button"
      aria-expanded={open}
      aria-controls={PANEL_ID}
      onClick={toggle}
      className={`${open ? NAV_BOX_ACTIVE : NAV_BOX} px-4 py-2.5`}
    >
      {t('agent.toggle')}
    </button>
  )
}

/** 打開時焦點落在輸入欄；對話還在讀、或 AI 沒開（沒有輸入欄）時落在面板標題。 */
function focusPanel() {
  const target = document.getElementById(INPUT_ID) ?? document.getElementById(PANEL_TITLE_ID)
  target?.focus()
}

function closePanel(setOpen: (open: boolean) => void) {
  // 先同步重畫：窄版的頁面在面板開著時是 `inert`，焦點送不進去。
  flushSync(() => setOpen(false))
  document.getElementById(TOGGLE_ID)?.focus()
}

/**
 * 側面板。桌面（`lg` 以上）是外框右側的一欄，頁面讓位、兩邊都能操作；窄版蓋滿整個視窗，
 * 底下那一頁由 `AppShell` 設成 `inert`，所以這裡是一個 modal dialog。
 */
export function AgentPanel({ narrow }: { narrow: boolean }) {
  const { t } = useTranslation()
  const { open, setOpen, conversationId, startNew } = usePanel()
  // 同一份查詢 `PanelBody` 也在讀；AI 沒開時「新對話」沒有意義，不畫。
  const enabled = useQuery(agentStatusQueryOptions).data?.enabled === true

  if (!open) return null

  function onKeyDown(event: KeyboardEvent) {
    if (event.key !== 'Escape' || event.defaultPrevented) return
    event.preventDefault()
    closePanel(setOpen)
  }

  return (
    <aside
      id={PANEL_ID}
      aria-labelledby={PANEL_TITLE_ID}
      role={narrow ? 'dialog' : undefined}
      aria-modal={narrow ? true : undefined}
      onKeyDown={onKeyDown}
      className="fixed inset-0 z-10 flex min-w-0 flex-col bg-hull lg:sticky lg:top-0 lg:z-auto lg:h-dvh lg:w-[26rem] lg:shrink-0 lg:border-l-2 lg:border-rule-strong"
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b-2 border-rule bg-deck px-4 py-2.5">
        <h2 id={PANEL_TITLE_ID} tabIndex={-1} className="label mr-auto bg-deck text-ink">
          {t('agent.title')}
        </h2>
        {enabled ? (
          <GhostButton type="button" onClick={() => startNew()}>
            {t('agent.newConversation')}
          </GhostButton>
        ) : null}
        <GhostButton type="button" onClick={() => closePanel(setOpen)}>
          {t('agent.close')}
        </GhostButton>
      </div>
      <PanelBody conversationId={conversationId} />
    </aside>
  )
}

function PanelBody({ conversationId }: { conversationId: string }) {
  const { t } = useTranslation()
  const status = useQuery(agentStatusQueryOptions)
  const me = useQuery(meQueryOptions)

  if (status.isError) return <PanelFailed error={status.error} />
  if (status.isPending || me.isPending) return <PanelLoading />
  if (!status.data.enabled) {
    // 沒有 AI 時 Berth 完整可用（plan §11.6）：這不是錯誤，不塗漆。
    return me.data?.role === 'admin' ? (
      <div className="grid gap-3 p-4">
        <p className="max-w-prose text-sm text-ink">{t('agent.off.admin')}</p>
        <Link to="/settings/ai" className={GHOST_LINK}>
          {t('agent.off.settings')}
        </Link>
      </div>
    ) : (
      <p className="max-w-prose p-4 text-sm text-ink">{t('agent.off.user')}</p>
    )
  }
  // `key`：換一段對話就是換一份 `Chat`，輸入欄以外的狀態（失敗的那一句）跟著清掉。
  return (
    <>
      <SpendAlerts spend={status.data.spend} />
      <Conversation key={conversationId} conversationId={conversationId} />
    </>
  )
}

/**
 * 今天的花費提醒（M5 票 21）：後端只給管理員，一般使用者是 `null`。只提醒、不停用，不推 Discord。
 * 有費用未知的呼叫時多一句說提醒沒算進它們：不然「沒有提醒」看起來像沒事（協調者 2026-10-27）。
 */
function SpendAlerts({ spend }: { spend: AgentStatus['spend'] }) {
  const { t, i18n } = useTranslation()
  const narrow = useNarrow()
  const { setOpen } = usePanel()
  if (spend === null) return null
  const unknown = unknownText(t, spend, 'panel')
  if (spend.alerts.length === 0 && unknown === null) return null
  const toUsage = (
    <Link
      to="/settings/usage"
      onClick={() => {
        if (narrow) setOpen(false)
      }}
      className={TEXT_LINK}
    >
      {t('agent.spend.link')}
    </Link>
  )
  return (
    <div className="grid gap-2 border-b-2 border-rule px-4 py-3">
      {spend.alerts.map((alert) => (
        <Notice key={alert.kind} signal="assigned" label={t('agent.spend.label')}>
          {alertText(t, alert, i18n.language, 'panel')} {toUsage}
        </Notice>
      ))}
      {unknown !== null ? (
        <Notice signal="neutral" label={t('agent.spend.unknownLabel')}>
          {unknown} {spend.alerts.length === 0 ? toUsage : null}
        </Notice>
      ) : null}
    </div>
  )
}
