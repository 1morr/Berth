import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useId, useRef, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'

import { parseRssRefusal, RSS_KEY } from '../api/rss'
import { COMPACT_BUTTON, Field, GhostButton } from '../components/controls'

/**
 * 一鍵加入的建議項（brief §15：720p、简体這類，不預設勾）。解析度與字幕語言是最常見的「這一種我不要」；
 * 兩種字形都列，讓看繁體或看簡體的人都有得挑。
 */
const SUGGESTED_RULES: readonly string[] = ['720p', '简体', '简日', '繁體', '繁日']

interface RulesProps {
  rules: readonly string[]
  /** 整組覆寫這一層。寫壞的那一條讓整組不存（422 `rule_invalid`）。 */
  save: (rules: string[]) => Promise<unknown>
  /** 這一層與其他層的關係，一句話。 */
  lede?: string
}

/**
 * 一層的排除條件（M3 票 10，brief §15「全部接受，只排除」）：一條一格、加入欄、建議項一鍵加入。
 * 全域、Feed、RSS Series 三處共用；**改了就存**（整組覆寫），不另外按儲存——一條規則就是一個動作。
 *
 * 寫壞的正則由後端擋（Python 的 `re` 才是比對的那一個，瀏覽器的 RegExp 語法不同），原因印在欄位下方，
 * 打的字留著讓人改。
 */
export function RulesEditor({ rules, save, lede }: RulesProps) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const listId = useId()
  const input = useRef<HTMLInputElement>(null)
  const [draft, setDraft] = useState('')
  const change = useMutation({
    mutationFn: (next: string[]) => save(next),
    onSuccess: async (_, sent) => {
      if (sent.length > rules.length) {
        setDraft('')
      } else {
        // 拿掉的那一格連同它的按鈕一起消失：焦點落回加入欄，不掉回 body。
        input.current?.focus()
      }
      // 規則一改，還沒送的 Item 可能被擋下：三份清單一起重問。
      await queryClient.invalidateQueries({ queryKey: RSS_KEY })
    },
  })
  const refusal = change.isError ? parseRssRefusal(change.error) : null
  const error =
    refusal?.reason === 'rule_invalid'
      ? t('rss.rules.invalid', { detail: refusal.detail })
      : refusal
        ? t(`rss.refusal.${refusal.reason}`)
        : change.isError
          ? t('rss.failed')
          : undefined
  const suggestions = SUGGESTED_RULES.filter((rule) => !rules.includes(rule))

  const add = (rule: string) => {
    const trimmed = rule.trim()
    if (trimmed === '' || rules.includes(trimmed)) {
      setDraft('')
      return
    }
    change.mutate([...rules, trimmed])
  }
  const submit = (event: FormEvent) => {
    event.preventDefault()
    add(draft)
  }

  return (
    <div className="grid gap-3">
      {lede && <p className="max-w-prose text-xs text-ink-dim">{lede}</p>}
      <p id={listId} className="sr-only">
        {t('rss.rules.list')}
      </p>
      {rules.length === 0 ? (
        <p className="text-sm text-ink-dim">{t('rss.rules.none')}</p>
      ) : (
        <ul aria-labelledby={listId} className="flex flex-wrap gap-2">
          {rules.map((rule) => (
            <li key={rule} className="flex min-w-0 items-center border-2 border-rule bg-hull">
              <span className="value min-w-0 px-2 py-1 text-sm wrap-anywhere text-ink">{rule}</span>
              <button
                type="button"
                aria-label={t('rss.rules.remove', { rule })}
                aria-disabled={change.isPending || undefined}
                onClick={() => {
                  if (!change.isPending) change.mutate(rules.filter((one) => one !== rule))
                }}
                className="label flex min-h-6 min-w-6 items-center justify-center self-stretch border-l-2 border-rule px-2 text-ink-dim hover:text-ink"
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
      <form onSubmit={submit} className="grid gap-2 sm:grid-cols-[1fr_auto] sm:items-start">
        <Field
          ref={input}
          label={t('rss.rules.add')}
          hint={t('rss.rules.hint')}
          autoComplete="off"
          spellCheck={false}
          value={draft}
          error={error}
          onChange={(event) => setDraft(event.target.value)}
        />
        <div className="sm:pt-7">
          <GhostButton type="submit" busy={change.isPending} disabled={draft.trim() === ''}>
            {change.isPending ? t('rss.rules.saving') : t('rss.rules.addAction')}
          </GhostButton>
        </div>
      </form>
      {suggestions.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="label text-ink-dim">{t('rss.rules.suggestions')}</span>
          {suggestions.map((rule) => (
            <button
              key={rule}
              type="button"
              aria-label={t('rss.rules.suggest', { rule })}
              aria-disabled={change.isPending || undefined}
              onClick={() => {
                if (!change.isPending) add(rule)
              }}
              className={COMPACT_BUTTON}
            >
              <span aria-hidden="true">+</span>
              <span className="value ml-1 normal-case">{rule}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

/**
 * Feed 與 RSS Series 那一列上的排除條件：平常收起來只說有幾條，展開才是編輯區（它不是那一列的主要事）。
 */
export function RulesToggle({ rules, save, lede }: RulesProps) {
  const { t } = useTranslation()
  const regionId = useId()
  const [open, setOpen] = useState(false)

  return (
    <div className="grid gap-2">
      <div>
        <button
          type="button"
          aria-expanded={open}
          aria-controls={regionId}
          onClick={() => setOpen((was) => !was)}
          className={COMPACT_BUTTON}
        >
          {t('rss.rules.toggle', { count: rules.length })}
          {/* 看得見的展開狀態；聽得見的是 `aria-expanded`。 */}
          <span aria-hidden="true" className="ml-1">
            {open ? '−' : '+'}
          </span>
        </button>
      </div>
      <div id={regionId} hidden={!open}>
        {open && <RulesEditor rules={rules} save={save} lede={lede} />}
      </div>
    </div>
  )
}
