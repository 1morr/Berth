import { useId, useState, type ComponentPropsWithRef, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { SIGNAL_FILL, type Signal } from './signal'

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
  onChange,
}: {
  label: string
  hint?: string
  checked: boolean
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
          onChange={(event) => onChange(event.target.checked)}
          className="mt-0.5 size-4 shrink-0 accent-[var(--color-assigned)]"
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
export const GHOST_LINK =
  'label justify-self-start border-2 border-rule px-4 py-2.5 text-ink hover:border-rule-strong'

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
    <div className="flex items-stretch gap-px bg-rule">
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
 * 需要二次確認的動作（plan §9.5 的兩顆按鈕）。確認就地展開，不跳離當前泊位
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
  const [asked, setAsked] = useState(false)

  if (!asked) {
    return (
      <GhostButton type="button" disabled={pending} onClick={() => setAsked(true)}>
        {pending ? pendingLabel : label}
      </GhostButton>
    )
  }

  return (
    <div className="grid gap-3 border-2 border-rule-strong bg-well px-3 py-3">
      <p className="max-w-prose text-xs text-ink">{warning}</p>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-[minmax(0,14rem)_auto] sm:items-center">
        <PrimaryButton
          type="button"
          disabled={pending}
          onClick={() => {
            setAsked(false)
            onConfirm()
          }}
        >
          {pending ? pendingLabel : confirmLabel}
        </PrimaryButton>
        <GhostButton type="button" onClick={() => setAsked(false)}>
          {t('common.cancel')}
        </GhostButton>
      </div>
    </div>
  )
}
