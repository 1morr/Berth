import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useEffect, useRef, useState, type KeyboardEvent, type PointerEvent } from 'react'
import { flushSync } from 'react-dom'
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
import { ConversationPicker } from './ConversationList'
import { PanelFailed, PanelLoading } from './PanelStates'
import {
  CONVERSATIONS_ID,
  CONVERSATIONS_TOGGLE_ID,
  INPUT_ID,
  PANEL_ID,
  PANEL_TITLE_ID,
  TOGGLE_ID,
  useLeavePanel,
  usePanel,
} from './panelState'
import {
  PANEL_WIDTH_DEFAULT,
  PANEL_WIDTH_LARGE_STEP,
  PANEL_WIDTH_MAX,
  PANEL_WIDTH_MIN,
  PANEL_WIDTH_STEP,
  clampPanelWidth,
  readPanelWidth,
  rootRem,
  writePanelWidth,
} from './panelWidth'

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
 *
 * 桌機的那一欄可以拖寬（M5.6 票 10b）：左緣的把手拖動、或用鍵盤的左右方向鍵，寬度記在這個瀏覽器。
 */
export function AgentPanel({ narrow }: { narrow: boolean }) {
  const { t } = useTranslation()
  const { open, setOpen, conversationId, startNew } = usePanel()
  // 同一份查詢 `PanelBody` 也在讀；AI 沒開時「對話」「新對話」沒有意義，不畫。
  const enabled = useQuery(agentStatusQueryOptions).data?.enabled === true
  // 「對話」那一塊（M5.5 票 18）：disclosure，同帳號選單。
  const [listing, setListing] = useState(false)
  const [width, setWidth] = useState(readPanelWidth)
  // 拖動或聚焦時抬頭列多一格寬度讀數（M5.6 票 10b 的 critique）：拖到上下限時看得出來是到底了。
  const [adjusting, setAdjusting] = useState(false)
  // 拖到一半放手、下一次拖動的起點：pointerup 當下的 state 可能還是上一格，用 ref 讀最新的。
  const latestWidth = useRef(width)
  const drag = useRef<{ x: number; width: number; rem: number } | null>(null)

  if (!open) return null

  function setPanelWidth(next: number) {
    latestWidth.current = next
    setWidth(next)
  }

  function onKeyDown(event: KeyboardEvent) {
    if (event.key !== 'Escape' || event.defaultPrevented) return
    event.preventDefault()
    if (listing) {
      // 先收起清單，焦點回到「對話」；再按一次才收起面板。
      setListing(false)
      document.getElementById(CONVERSATIONS_TOGGLE_ID)?.focus()
      return
    }
    closePanel(setOpen)
  }

  /** 把手在面板的左緣：往左＝面板變寬。 */
  function resizeWithKeys(event: KeyboardEvent<HTMLDivElement>) {
    const step = event.shiftKey ? PANEL_WIDTH_LARGE_STEP : PANEL_WIDTH_STEP
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
    event.preventDefault()
    const next = clampPanelWidth(latestWidth.current + (event.key === 'ArrowLeft' ? step : -step))
    setPanelWidth(next)
    writePanelWidth(next)
  }

  function startDrag(event: PointerEvent<HTMLDivElement>) {
    if (event.button !== 0) return
    // 拖動不搶焦點、不選字：焦點只靠 Tab 進來（票 10b）。
    event.preventDefault()
    event.currentTarget.setPointerCapture?.(event.pointerId)
    drag.current = { x: event.clientX, width: latestWidth.current, rem: rootRem() }
  }

  function dragTo(event: PointerEvent<HTMLDivElement>) {
    const start = drag.current
    if (start === null) return
    if (event.buttons === 0) {
      // 沒收到 pointerup（在視窗外放手、capture 被搶走）：收掉這次拖動、把它記下來，
      // 之後的 hover 不要接著改寬度。
      drag.current = null
      writePanelWidth(latestWidth.current)
      return
    }
    setPanelWidth(clampPanelWidth(start.width + (start.x - event.clientX) / start.rem))
  }

  function endDrag(event: PointerEvent<HTMLDivElement>) {
    if (drag.current === null) return
    drag.current = null
    setAdjusting(false)
    const handle = event.currentTarget
    if (handle.hasPointerCapture?.(event.pointerId)) handle.releasePointerCapture(event.pointerId)
    // 放手才寫：拖動途中每一格都寫 `localStorage` 是同步 I/O，會讓拖動掉格。
    writePanelWidth(latestWidth.current)
  }

  /** 雙擊回預設：拖歪了不必一格一格按回來（critique P1）。 */
  function resetWidth() {
    setPanelWidth(PANEL_WIDTH_DEFAULT)
    writePanelWidth(PANEL_WIDTH_DEFAULT)
  }

  return (
    <aside
      id={PANEL_ID}
      aria-labelledby={PANEL_TITLE_ID}
      role={narrow ? 'dialog' : undefined}
      aria-modal={narrow ? true : undefined}
      onKeyDown={onKeyDown}
      style={narrow ? undefined : { width: `${width}rem` }}
      className="fixed inset-0 z-10 flex min-w-0 flex-col bg-hull lg:sticky lg:top-0 lg:z-auto lg:h-dvh lg:shrink-0 lg:border-l-2 lg:border-rule-strong"
    >
      {/* 拖寬的把手（M5.6 票 10b）：蓋在面板左緣的分隔線上，桌機才有——窄版面板蓋滿視窗，拖了也沒有意義。
          命中區 `w-6`（24px，DESIGN.md〈命中面積〉）；畫出來的是置中的 2px 線，平常透明（露出分隔線），
          hover 與聚焦時換成 `ink`。`preventDefault` 讓拖動不搶焦點、不在頁面上選字；`touch-none` 讓觸控拖動不變成捲頁。 */}
      {narrow ? null : (
        <div
          role="separator"
          aria-orientation="vertical"
          aria-label={t('agent.resize')}
          aria-valuenow={Math.round(width)}
          aria-valuetext={t('agent.resizeValue', { width: Math.round(width) })}
          aria-valuemin={PANEL_WIDTH_MIN}
          aria-valuemax={PANEL_WIDTH_MAX}
          tabIndex={0}
          onKeyDown={resizeWithKeys}
          onPointerDown={(event) => {
            setAdjusting(true)
            startDrag(event)
          }}
          onPointerMove={dragTo}
          onPointerUp={endDrag}
          onPointerCancel={endDrag}
          onDoubleClick={resetWidth}
          onFocus={() => setAdjusting(true)}
          onBlur={() => setAdjusting(false)}
          className="group absolute inset-y-0 left-0 z-10 w-6 -translate-x-1/2 cursor-col-resize touch-none"
        >
          <span
            aria-hidden="true"
            className="pointer-events-none absolute inset-y-0 left-1/2 w-0.5 -translate-x-1/2 bg-transparent group-hover:bg-ink group-focus-visible:bg-ink"
          />
          {/* 靜止時的握把刻記（critique P1）：三條短橫線，hover／聚焦轉 `ink`。 */}
          <span
            aria-hidden="true"
            className="pointer-events-none absolute top-1/2 left-1/2 flex -translate-x-1/2 -translate-y-1/2 flex-col gap-1"
          >
            {[0, 1, 2].map((tick) => (
              <span
                key={tick}
                className="block h-0.5 w-3 bg-ink-dim group-hover:bg-ink group-focus-visible:bg-ink"
              />
            ))}
          </span>
        </div>
      )}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b-2 border-rule bg-deck px-4 py-2.5">
        <h2 id={PANEL_TITLE_ID} tabIndex={-1} className="label mr-auto bg-deck text-ink">
          {t('agent.title')}
        </h2>
        {adjusting ? (
          // 寬度讀數（critique P1）：拖動或聚焦時才出現，滑鼠離開就收掉。
          <span className="value text-xs text-ink-dim">{Math.round(width)} rem</span>
        ) : null}
        {enabled ? (
          <>
            <GhostButton
              id={CONVERSATIONS_TOGGLE_ID}
              type="button"
              aria-expanded={listing}
              aria-controls={CONVERSATIONS_ID}
              onClick={() => setListing((was) => !was)}
            >
              {t('agent.conversations.toggle')}
            </GhostButton>
            <GhostButton
              type="button"
              onClick={() => {
                setListing(false)
                startNew()
              }}
            >
              {t('agent.newConversation')}
            </GhostButton>
          </>
        ) : null}
        <GhostButton type="button" onClick={() => closePanel(setOpen)}>
          {t('agent.close')}
        </GhostButton>
      </div>
      {enabled && listing ? (
        <ConversationPicker id={CONVERSATIONS_ID} onPicked={() => setListing(false)} />
      ) : null}
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
      <Paused until={status.data.paused_until} error={status.data.pause_error} />
      <SpendAlerts spend={status.data.spend} />
      <Conversation key={conversationId} conversationId={conversationId} />
    </>
  )
}

/**
 * provider 斷路器暫停中（M5 票 20、22）：一般使用者也看得到到幾點；錯誤原文只給管理員（後端只給他）。
 * 不是錯誤、也不擋打字：被擋下的那一則才說（`ai_paused`）。到時間就重問一次，關了就收掉。
 */
function Paused({ until, error }: { until: string | null; error: string }) {
  const { t, i18n } = useTranslation()
  const queryClient = useQueryClient()
  const leave = useLeavePanel()

  useEffect(() => {
    if (until === null) return
    const wait = Math.max(new Date(until).getTime() - Date.now(), 0) + 1_000
    const timer = setTimeout(() => {
      void queryClient.invalidateQueries({ queryKey: agentStatusQueryOptions.queryKey })
    }, wait)
    return () => clearTimeout(timer)
  }, [until, queryClient])

  if (until === null) return null
  const time = new Date(until).toLocaleTimeString(i18n.language, {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
  return (
    <div className="grid gap-2 border-b-2 border-rule px-4 py-3">
      <Notice signal="assigned" label={t('agent.paused.label')}>
        {t('agent.paused.until')}{' '}
        <time dateTime={until} className="value">
          {time}
        </time>
        {t('agent.paused.why')}
      </Notice>
      {error ? (
        <div className="grid gap-1">
          <span className="label text-ink-dim">{t('agent.paused.error')}</span>
          <p className="value text-xs wrap-anywhere text-ink">{error}</p>
          <Link to="/settings/ai" onClick={leave} className={`${TEXT_LINK} justify-self-start`}>
            {t('agent.off.settings')}
          </Link>
        </div>
      ) : null}
    </div>
  )
}

/**
 * 今天的花費提醒（M5 票 21）：後端只給管理員，一般使用者是 `null`。只提醒、不停用，不推 Discord。
 * 有費用未知的呼叫時多一句說提醒沒算進它們：不然「沒有提醒」看起來像沒事（協調者 2026-10-27）。
 */
function SpendAlerts({ spend }: { spend: AgentStatus['spend'] }) {
  const { t, i18n } = useTranslation()
  const leave = useLeavePanel()
  if (spend === null) return null
  const unknown = unknownText(t, spend, 'panel')
  if (spend.alerts.length === 0 && unknown === null) return null
  const toUsage = (
    <Link to="/settings/usage" onClick={leave} className={TEXT_LINK}>
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
