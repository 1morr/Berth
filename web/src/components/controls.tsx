import { useId, useState, type ComponentPropsWithRef, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { SIGNAL_FILL, type Signal } from './signal'
import { ConfirmPanel } from './ConfirmPanel'
import { useInPlaceConfirm } from './useInPlaceConfirm'

/**
 * 表單控制項。用原生 `input` / `button` / `checkbox`：第 1–2 步沒有任何需要行為基礎的
 * 元件（無 dropdown / dialog / popover / tabs），原生的無障礙比重寫一份好。
 * 外觀全部改造成塗裝色塊與模板字，沒有 stock 樣式。
 */

/**
 * 手機上主要動作固定在底部安全區之上（shape brief §6）；桌機恢復成一般的行內按鈕。
 * `-mx-6` 是為了讓貼底的那一條橫跨整個工作面，而不是縮在 padding 裡面。
 */
export const STICKY_ACTION =
  'sticky bottom-0 -mx-6 border-t-2 border-rule bg-hull px-6 pb-[max(1rem,env(safe-area-inset-bottom))] pt-4 lg:static lg:mx-0 lg:border-0 lg:bg-transparent lg:p-0'

// `ComponentPropsWithRef` 而不是 `InputHTMLAttributes`：登入失敗後要把焦點送回密碼欄，
// 呼叫端得拿得到那個 input（React 19 的 `ref` 就是一個一般的 prop）。
type FieldProps = ComponentPropsWithRef<'input'> & {
  label: string
  hint?: ReactNode
  error?: string
}

export function Field({ label, hint, error, ...input }: FieldProps) {
  const id = useId()
  const hintId = `${id}-hint`
  const errorId = `${id}-error`
  const described = [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(' ')

  return (
    <p className="grid gap-2">
      <label htmlFor={id} className="label text-ink-dim">
        {label}
      </label>
      <input
        {...input}
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={described || undefined}
        className={`value w-full border-2 bg-hull px-3 py-2.5 text-sm text-ink placeholder:text-ink-dim disabled:bg-well disabled:text-ink-dim ${
          error ? 'border-blocked' : 'border-rule focus:border-rule-strong'
        }`}
      />
      {hint && (
        <span id={hintId} className="text-xs text-ink-dim">
          {hint}
        </span>
      )}
      {error && (
        <span id={errorId} role="alert" className="text-xs text-blocked-ink">
          {error}
        </span>
      )}
    </p>
  )
}

export function PasswordField({ label, ...input }: FieldProps) {
  const { t } = useTranslation()
  const [shown, setShown] = useState(false)

  return (
    <div className="relative">
      <Field {...input} label={label} type={shown ? 'text' : 'password'} />
      <button
        type="button"
        onClick={() => setShown((was) => !was)}
        className="label absolute right-0 top-0 flex min-h-6 min-w-6 items-center justify-center px-1 text-ink-dim hover:text-ink"
      >
        {shown ? t('common.hide') : t('common.show')}
      </button>
    </div>
  )
}

export function Checkbox({
  label,
  hint,
  checked,
  disabled = false,
  onChange,
}: {
  label: string
  hint?: string
  checked: boolean
  /** 鎖住但照樣顯示（票 14：精靈泊位 4 上已經有 Route 的媒體庫）。 */
  disabled?: boolean
  onChange: (checked: boolean) => void
}) {
  const id = useId()

  return (
    <div className="grid gap-2">
      <div className="flex items-start gap-3">
        <input
          id={id}
          type="checkbox"
          checked={checked}
          disabled={disabled}
          onChange={(event) => onChange(event.target.checked)}
          className="mt-0.5 size-4 shrink-0 accent-[var(--color-assigned)] disabled:cursor-not-allowed"
        />
        <label htmlFor={id} className="text-sm leading-snug text-ink">
          {label}
        </label>
      </div>
      {hint && <p className="pl-7 text-xs text-ink-dim">{hint}</p>}
    </div>
  )
}

/** 主要動作：hi-vis 塗裝色塊。這塊板子上沒有藍色 primary 按鈕。

 邊框不是裝飾：亮色主題下黃漆對紙白只有 1.36:1，沒有邊的話按鈕的輪廓看不出來
 （WCAG 2.2 的非文字對比要 3:1）。`rule-strong` 對兩個底色都有 6.4:1。 */
export function PrimaryButton({
  children,
  ...button
}: ComponentPropsWithRef<'button'> & { children: ReactNode; type?: 'button' | 'submit' }) {
  return (
    <button
      {...button}
      className="label w-full border-2 border-rule-strong bg-assigned px-4 py-3.5 text-on-signal disabled:cursor-not-allowed disabled:bg-deck disabled:text-ink-dim"
    >
      {children}
    </button>
  )
}

/**
 * 主要動作，但它是一條連結（換頁、開新分頁）：Media 詳情的主按鈕「繼續看」（M1.5 票 08）。外觀同 `PrimaryButton`，
 * 寬度由呼叫端給（元件的滿版是按鈕的形狀，這一條在 `sm` 以上有最小寬度就好）。
 */
export const PRIMARY_LINK =
  'label inline-flex min-h-12 items-center justify-center border-2 border-rule-strong bg-assigned px-4 py-3.5 text-center text-on-signal'

/** 次要動作：只有外框，不搶主要動作的位置。 */
export function GhostButton({
  children,
  ...button
}: ComponentPropsWithRef<'button'> & { children: ReactNode; type?: 'button' | 'submit' }) {
  return (
    <button
      {...button}
      className="label border-2 border-rule px-4 py-2.5 text-ink hover:border-rule-strong disabled:cursor-not-allowed disabled:text-ink-dim"
    >
      {children}
    </button>
  )
}

/**
 * 次要動作，但它其實是一條連結（導到別頁，不是在這一頁做一件事）。
 *
 * 與 `GhostButton` 一模一樣的外觀。這一份存在是因為那串類名一度被逐字抄了三遍
 * （票 04 的 code review）——外觀的單一來源是元件，不是一段字串。
 * `children` 之外的 prop 交給呼叫端的 `Link`，所以路由型別檢查仍然成立。
 */
/**
 * 比 Ghost 小一號的按鈕，擠得進卡片最下面那一行或區塊標題列（命中面積仍 ≥ 24px）：牆卡片的「標為已看」
 * （票 05）與繼續觀看、下一集的「全部 N 項」（票 07）。
 */
export const COMPACT_BUTTON =
  'label inline-flex min-h-6 items-center border-2 border-rule px-2 py-1 text-ink hover:border-rule-strong aria-disabled:text-ink-dim'

export const GHOST_LINK =
  'label justify-self-start border-2 border-rule px-4 py-2.5 text-ink hover:border-rule-strong'

/**
 * 每一頁唯一的 `<h1>`（票 03 第 13 條）。四頁本來各長各的——`/settings/routes` 有 h1，
 * `/health` 與 `/settings/services` 從 `<h2>` 開起，精靈一個標題都沒有。大小與可見性
 * 在這裡定一次，**外距由呼叫端給**（同 `NAV_BOX` 的理由：同一個元素上誰贏看 CSS 先後）。
 */
export const PAGE_TITLE = 'value text-lg font-semibold text-ink'

/**
 * 導覽方塊：頁首導覽、媒體庫的 Route 切換列與篩選列（票 13）。當前那一個重橫線 + `deck` 底，
 * 不靠顏色（狀態不只靠顏色，PRODUCT.md）。
 *
 * **不含內距**：兩種尺寸的方塊共用這一份，而同一個元素上的 `px-4` 與 `px-3` 誰贏看的是
 * CSS 裡的先後，不是類名字串的先後——內距由呼叫端自己給一次。
 */
export const NAV_BOX = 'label border-2 border-rule hover:border-rule-strong'
export const NAV_BOX_ACTIVE = 'label border-2 border-rule-strong bg-deck'

/**
 * 路由的 `Link` 用這一個：當前那一個由 TanStack 自己掛的 `data-status="active"` 換漆（票 13）。
 *
 * 不用 `activeProps`：它的 `className` 是**接在** `className` 後面，當前那一格因此同時帶著 `border-rule` 與
 * `border-rule-strong`，誰贏看 Tailwind 產生的先後，不是看字串（M1.5 票 11 audit）。按鈕沒有這個問題
 * （`aria-pressed` 的那幾處是二選一），照舊用上面兩個。
 */
export const NAV_LINK = `${NAV_BOX} data-[status=active]:border-rule-strong data-[status=active]:bg-deck`

/**
 * 帶狀態的訊息塊。標記是**塗上去的色塊 + 模板字**，不是左側的粗色條——
 * 那條粗色條是 AI 介面最好認的胎記，也不是這塊板子的語彙。
 */
export function Notice({
  signal,
  label,
  children,
}: {
  signal: Signal
  label: string
  children: ReactNode
}) {
  return (
    <div
      role={signal === 'blocked' ? 'alert' : undefined}
      className="flex flex-wrap items-start gap-x-3 gap-y-2 border-2 border-rule bg-well px-3 py-2.5"
    >
      <span className={`label px-2 py-1.5 ${SIGNAL_FILL[signal]}`}>{label}</span>
      <span className="min-w-0 flex-1 self-center text-sm text-ink">{children}</span>
    </div>
  )
}

/** 可複製的手動步驟。失敗一定要說得出下一步（PRODUCT.md 原則 4）。 */
export function CopyLine({ command }: { command: string }) {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)

  async function copy() {
    try {
      await navigator.clipboard.writeText(command)
      setCopied(true)
    } catch {
      // 沒有剪貼簿權限就算了，指令本身仍然選得起來。
      setCopied(false)
    }
  }

  return (
    // `min-w-0`：這一塊常常是 grid 項目，而 grid 項目的 `min-width` 預設是 `auto`——
    // 底下的 `<code>` 是 `whitespace-pre`，所以它的 min-content 是那一整串不斷行的字，
    // 於是整欄被撐寬、`overflow-x-auto` 永遠沒事做（票 04 的集表踩過同一個坑）。
    <div className="flex min-w-0 items-stretch gap-px bg-rule">
      <code className="value min-w-0 flex-1 overflow-x-auto whitespace-pre bg-hull px-3 py-2 text-xs text-ink">
        {command}
      </code>
      <button
        type="button"
        onClick={() => void copy()}
        className="label shrink-0 bg-deck px-3 text-ink-dim hover:text-ink"
      >
        {copied ? t('common.copied') : t('common.copy')}
      </button>
    </div>
  )
}

/**
 * 「主要動作 + 取消」那一列：就地確認（`ConfirmAction`、送單）與新增表單的送出列共用。
 *
 * 取消是 `max-content` 而不是 `auto`：`auto` 軌會分掉剩下的空白（CSS Grid §12.8 的
 * stretch auto tracks），於是容器一寬，取消就畫得比 14rem 的主要動作還寬，看起來像是在推人
 * 按取消（票 03 第 3 條）。窄版兩顆各自整寬疊起來，主要動作在上。
 *
 * 一份而不是每個呼叫端各寫一次：那串類名原本被逐字抄了三遍，而缺陷就在那一段字裡。
 */
export const CONFIRM_ACTIONS =
  'grid grid-cols-1 gap-2 sm:grid-cols-[minmax(0,14rem)_max-content] sm:items-center'

/**
 * 需要二次確認的動作（plan §9.5 的「加入 Berth 路徑」）。確認就地展開，不跳離當前泊位
 * （direction contract：失敗與確認都在原地）。`warning` 說清楚按下去會發生什麼。
 */
export function ConfirmAction({
  label,
  confirmLabel,
  warning,
  pending = false,
  pendingLabel,
  onConfirm,
}: {
  label: string
  confirmLabel: string
  warning: ReactNode
  pending?: boolean
  pendingLabel: string
  onConfirm: () => void
}) {
  const { t } = useTranslation()
  const { asked, open, close, trigger, panel, onKeyDown } = useInPlaceConfirm()
  const warningId = useId()

  if (!asked) {
    return (
      <GhostButton ref={trigger} type="button" disabled={pending} onClick={open}>
        {pending ? pendingLabel : label}
      </GhostButton>
    )
  }

  return (
    <ConfirmPanel panelRef={panel} onKeyDown={onKeyDown} labelledBy={warningId}>
      <p id={warningId} className="max-w-prose text-xs text-ink">
        {warning}
      </p>
      <div className={CONFIRM_ACTIONS}>
        <PrimaryButton
          type="button"
          disabled={pending}
          onClick={() => {
            close()
            onConfirm()
          }}
        >
          {pending ? pendingLabel : confirmLabel}
        </PrimaryButton>
        <GhostButton type="button" onClick={close}>
          {t('common.cancel')}
        </GhostButton>
      </div>
    </ConfirmPanel>
  )
}
