import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { meQueryOptions } from './api/auth'
import { assistantStatusQueryOptions } from './api/assistant'
import { AssistantControlContext } from './assistant/AssistantControl'
import { AssistantPanel, PANEL_ID, type ConversationRequest } from './assistant/AssistantPanel'
import { usePanelOpen } from './assistant/usePanelOpen'
import { GhostButton, NAV_BOX, NAV_BOX_ACTIVE, NAV_LINK } from './components/controls'
import { LanguageToggle } from './components/LanguageToggle'
import { useSignOut } from './components/useSignOut'

/**
 * setup 完成之後的頁面共用的外框。
 *
 * `main` 不設寬度上限：健康頁的泊位板是整寬的橫幅（direction contract 的 FIRST VIEWPORT），
 * 每一頁自己決定內文那一欄有多寬。
 *
 * **助理的側面板掛在這裡**（M5 票 08，`.scratch/m5/side-panel-shape.md`）：換頁不關。`lg` 以上固定在右側、
 * 全高，外框讓出同樣寬的一欄，頁首與頁面變窄、照常可操作（並排，不疊在任何東西上：這個系統沒有浮起來的層）；
 * `lg` 以下開著時取代頁首與 `main`，面板裡的連結換了頁就收起（M5 票 15）。登入之後才有。
 */
export function AppShell({ children }: { children: ReactNode }) {
  const { t } = useTranslation()
  const me = useQuery(meQueryOptions)
  const [open, setOpen] = usePanelOpen()
  // 使用者自己按開的才把焦點交給輸入框；重整時照記憶打開的不搶。
  const [byHand, setByHand] = useState(false)
  const panel = open && me.data !== undefined
  // 頁面要面板顯示某一則對話（AI 活動頁）：面板接下就清掉。
  const [request, setRequest] = useState<ConversationRequest | null>(null)
  const control = useMemo(
    () => ({
      openConversation: (id: number) => {
        setByHand(true)
        setOpen(true)
        setRequest((current) => ({ id, nonce: (current?.nonce ?? 0) + 1 }))
      },
    }),
    [setOpen],
  )
  const handled = useCallback(() => setRequest(null), [])

  const toggle = () => {
    setByHand(!open)
    setOpen(!open)
  }
  // 關閉之後焦點回到「助理」鍵。等畫完再給：`lg` 以下面板開著時頁首是收起來的，那時鍵還拿不到焦點。
  const returning = useRef(false)
  useEffect(() => {
    if (open || !returning.current) return
    returning.current = false
    document.getElementById(TOGGLE_ID)?.focus()
  }, [open])
  const close = () => {
    returning.current = true
    setOpen(false)
  }

  return (
    <AssistantControlContext value={control}>
      <div className={`min-h-dvh bg-hull text-ink ${panel ? 'lg:pr-[26rem] xl:pr-[28rem]' : ''}`}>
        {/* 頁首有八個 Tab 停留點；鍵盤使用者每換一頁都要先過完它們（票 15 audit）。
          平常看不見，拿到焦點才浮出來。`not-sr-only` 會把 padding 歸零，所以浮出時的 padding
          寫在 `focus:` 那一組（票 15 實跑量到 58×15px）。 */}
        <a
          href="#main"
          className="label sr-only border-2 border-rule-strong bg-deck text-ink focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:px-4 focus:py-2.5"
        >
          {t('nav.skip')}
        </a>
        {/* `lg` 以下面板開著時連頁首一起收起，面板佔滿畫面、輸入框在第一屏（M5 票 15）。是收起不是疊上去：
            這個系統沒有浮起來的層。面板自己的抬頭列有「關閉」。 */}
        <header
          className={`flex flex-wrap items-center gap-x-6 gap-y-3 border-b-2 border-rule-strong px-6 py-4 ${panel ? 'max-lg:hidden' : ''}`}
        >
          <div>
            <p className="value text-lg font-semibold tracking-tight">{t('app.name')}</p>
            <p className="text-sm text-ink-dim">{t('app.tagline')}</p>
          </div>
          <span className="ml-auto">
            <Identity assistantOpen={open} onToggleAssistant={toggle} />
          </span>
        </header>
        <div className="lg:flex lg:items-start">
          {/* `tabIndex={-1}`：skip link 跳過來時焦點要真的落在這裡，下一個 Tab 才從內容開始。 */}
          <main
            id="main"
            tabIndex={-1}
            className={`outline-none lg:min-w-0 lg:flex-1 ${panel ? 'max-lg:hidden' : ''}`}
          >
            {children}
          </main>
          {panel && (
            <AssistantPanel
              admin={me.data.role === 'admin'}
              focusOnMount={byHand}
              onClose={close}
              onLeave={() => setOpen(false)}
              request={request}
              onRequestHandled={handled}
            />
          )}
        </div>
      </div>
    </AssistantControlContext>
  )
}

/** 導覽的一項。當前頁用重橫線標出來，不是靠顏色（狀態不只靠顏色，PRODUCT.md）。 */
function NavLink({
  to,
  children,
}: {
  to:
    | '/'
    | '/library'
    | '/jobs'
    | '/ai-activity'
    | '/review'
    | '/issues'
    | '/rss'
    | '/weekly'
    | '/health'
    | '/settings'
  children: ReactNode
}) {
  return (
    <Link
      to={to}
      // `/` 是每一條路徑的前綴，預設的模糊比對會讓探索永遠是「當前頁」。
      activeOptions={{ exact: to === '/' }}
      className={`${NAV_LINK} px-4 py-2.5`}
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
/** 頁首的「助理」鍵：`aria-controls` 指著面板，關掉面板時焦點回到這裡。 */
const TOGGLE_ID = 'assistant-toggle'

function Identity({
  assistantOpen,
  onToggleAssistant,
}: {
  assistantOpen: boolean
  onToggleAssistant: () => void
}) {
  const { t } = useTranslation()
  const me = useQuery(meQueryOptions)
  const leave = useSignOut()
  // AI 沒設定好時導覽沒有這一格（直接進網址照樣看得到以前的）；人人看得到，不分角色。
  const assistant = useQuery(assistantStatusQueryOptions)

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
        {assistant.data?.ready === true && (
          <NavLink to="/ai-activity">{t('nav.aiActivity')}</NavLink>
        )}
        {/* 審核與待處理同一個規則：審核與修正是 admin 的事（plan §6），後端同時回 403。 */}
        {me.data.role === 'admin' && <NavLink to="/review">{t('nav.review')}</NavLink>}
        {me.data.role === 'admin' && <NavLink to="/issues">{t('nav.issues')}</NavLink>}
        {/* RSS 同一個規則（M3 票 08）：聚合 feed 的網址帶 token，綁定會替整個家送單。 */}
        {me.data.role === 'admin' && <NavLink to="/rss">{t('nav.rss')}</NavLink>}
        {/* 週報同一個規則（M4 票 131）：後端的門禁在 `/weekly`。 */}
        {me.data.role === 'admin' && <NavLink to="/weekly">{t('nav.weekly')}</NavLink>}
        <NavLink to="/health">{t('nav.health')}</NavLink>
        {/* 連 `/settings` 而不是第一個分頁：前綴比對讓它在兩個設定頁上都是當前頁（票 14a）。
            每個人都有：一般使用者的設定只有通知那一頁，`/settings` 把他帶到那裡（M4 票 125）。 */}
        <NavLink to="/settings">{t('nav.settings')}</NavLink>
      </nav>
      {/* 不是一頁，是這一頁旁邊的一欄：按鈕而不是連結，開著時同導覽的當前格（重線 + `deck`）。 */}
      <button
        id={TOGGLE_ID}
        type="button"
        aria-expanded={assistantOpen}
        aria-controls={assistantOpen ? PANEL_ID : undefined}
        onClick={onToggleAssistant}
        className={`${assistantOpen ? NAV_BOX_ACTIVE : NAV_BOX} px-4 py-2.5`}
      >
        {t('assistant.toggle')}
      </button>
      <GhostButton type="button" busy={leave.isPending} onClick={() => leave.mutate()}>
        {leave.isPending ? t('nav.signingOut') : t('nav.signOut')}
      </GhostButton>
      <LanguageToggle />
    </div>
  )
}
