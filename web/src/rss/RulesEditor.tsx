import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useId, useRef, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'

import { RSS_KEY, exclusionsQueryOptions } from '../api/rss'
import { COMPACT_BUTTON, Field, GhostButton, TEXT_LINK } from '../components/controls'
import { rssProblem } from './rssProblem'

/**
 * 一鍵加入的建議項（brief §15：720p、简体這類，不預設勾）。解析度與字幕語言是最常見的「這一種我不要」；
 * 兩種字形都列，讓看繁體或看簡體的人都有得挑。
 */
const SUGGESTED_RULES: readonly string[] = ['720p', '简体', '简日', '繁體', '繁日']

/** 全域那一段的錨點：Feed 與 RSS Series 那兩層的合集那一行連到這裡（M4 票 113）。 */
export const GLOBAL_EXCLUSIONS_ANCHOR = 'global-exclusions'

interface RulesProps {
  rules: readonly string[]
  /** 整組覆寫這一層。寫壞的那一條讓整組不存（422 `rule_invalid`）。 */
  save: (rules: string[]) => Promise<unknown>
}

/**
 * 一層的排除條件（M3 票 10，brief §15「全部接受，只排除」）：一條一格、加入欄、建議項一鍵加入。
 * 全域、Feed、RSS Series 三處共用；**改了就存**（整組覆寫），不另外按儲存——一條規則就是一個動作。
 *
 * 寫壞的正則由後端擋（Python 的 `re` 才是比對的那一個，瀏覽器的 RegExp 語法不同），原因印在欄位下方，
 * 打的字留著讓人改。
 */
export function RulesEditor({ rules, save }: RulesProps) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState('')
  const change = useMutation({
    mutationFn: (next: string[]) => save(next),
    // 規則一改，還沒送的 Item 可能被擋下：三份清單一起重問。
    onSuccess: () => queryClient.invalidateQueries({ queryKey: RSS_KEY }),
  })

  return (
    <RulesFields
      rules={rules}
      draft={draft}
      setDraft={setDraft}
      busy={change.isPending}
      error={change.isError ? rssProblem(t, change.error) : undefined}
      commit={(next, done) => change.mutate(next, { onSuccess: done })}
    />
  )
}

/**
 * 規則的畫面本身，不管存到哪裡：`RulesEditor` 一改就送後端；新增 Feed 的表單先記在表單裡，
 * 跟著 `POST /rss/feeds` 一起送（M4 票 110）。`commit` 存好之後呼叫 `done`，加入欄才清空。
 * 加入欄打的字由呼叫端持有：新增 Feed 送出時，打了沒按「加入規則」的那一條也要帶上。
 *
 * 加入欄自己是一個 `<form>`（Enter 加一條）：放進別的表單時要放在那個 `<form>` 元素外面。
 */
export function RulesFields({
  rules,
  draft,
  setDraft,
  commit,
  busy = false,
  error,
}: {
  rules: readonly string[]
  draft: string
  setDraft: (draft: string) => void
  commit: (next: string[], done: () => void) => void
  busy?: boolean
  error?: string
}) {
  const { t } = useTranslation()
  const listId = useId()
  const input = useRef<HTMLInputElement>(null)
  const suggestions = SUGGESTED_RULES.filter((rule) => !rules.includes(rule))

  const change = (next: string[]) => {
    const added = next.length > rules.length
    commit(next, () => {
      if (added) {
        setDraft('')
      } else {
        // 拿掉的那一格連同它的按鈕一起消失：焦點落回加入欄，不掉回 body。
        input.current?.focus()
      }
    })
  }
  const add = (rule: string) => {
    const trimmed = rule.trim()
    if (trimmed === '' || rules.includes(trimmed)) {
      setDraft('')
      return
    }
    change([...rules, trimmed])
  }
  const submit = (event: FormEvent) => {
    event.preventDefault()
    add(draft)
  }

  return (
    <div className="grid gap-3">
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
                aria-disabled={busy || undefined}
                onClick={() => {
                  if (!busy) change(rules.filter((one) => one !== rule))
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
          <GhostButton type="submit" busy={busy} disabled={draft.trim() === ''}>
            {busy ? t('rss.rules.saving') : t('rss.rules.addAction')}
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
              aria-disabled={busy || undefined}
              onClick={() => {
                if (!busy) add(rule)
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
export function RulesToggle({ rules, save, lede }: RulesProps & { lede: string }) {
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
      <div id={regionId} hidden={!open} className="grid gap-3">
        {open && (
          <>
            <LayerLede lede={lede} />
            <RulesEditor rules={rules} save={save} />
          </>
        )}
      </div>
    </div>
  )
}

/**
 * Feed 與 RSS Series 那一層的說明：這一層與其他層的關係，加上全域的合集設定。
 *
 * 這兩層沒有合集開關（brief §15 定在全域，2026-10-19 使用者確認不加）：第二行說出全域那一項的目前值、
 * 連回全域那一段，免得看起來像這一層漏了（M4 票 113）。讀的是全域那一段同一個查詢，切換全域開關後
 * 一起重問、跟著變。
 */
export function LayerLede({ lede }: { lede: string }) {
  const { t } = useTranslation()
  const global = useQuery(exclusionsQueryOptions())

  return (
    <div className="grid max-w-prose gap-1 text-xs text-ink-dim">
      <p>{lede}</p>
      {global.data && (
        <p className="flex flex-wrap items-center gap-x-2">
          <span>
            {global.data.not_single ? t('rss.rules.batchesOff') : t('rss.rules.batchesOn')}
          </span>
          <a href={`#${GLOBAL_EXCLUSIONS_ANCHOR}`} className={TEXT_LINK}>
            {t('rss.rules.toGlobal')}
          </a>
        </p>
      )}
    </div>
  )
}
