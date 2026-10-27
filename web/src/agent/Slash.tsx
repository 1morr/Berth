import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { SlashName, SlashResult } from '../api/agent'
import { Timestamp } from '../components/Timestamp'
import { SLASH_HINT_ID, slashOptionId } from './panelState'

/**
 * 斜線指令（M5 票 18）：輸入 `/` 時的提示清單，與指令的結果。
 *
 * 結果只在這個分頁看得到：它不進對話歷史（指令不經過模型，也不該讓下一輪的模型讀到），重新載入就不見。
 */

/**
 * 輸入欄上方的提示清單（`listbox`）。焦點留在輸入欄，上下鍵移動、Enter 執行、Tab 補完、Esc 收起
 * 由 `Conversation` 處理；滑鼠點一列直接執行。
 */
export function SlashHint({
  options,
  active,
  onPick,
}: {
  options: SlashName[]
  active: number
  onPick: (name: SlashName) => void
}) {
  const { t } = useTranslation()
  return (
    <ul
      id={SLASH_HINT_ID}
      role="listbox"
      aria-label={t('agent.slash.hintLabel')}
      className="grid border-2 border-rule-strong bg-well"
    >
      {options.map((name, index) => (
        <li
          key={name}
          id={slashOptionId(name)}
          role="option"
          aria-selected={index === active}
          // 按下去就執行；`mousedown` 不搶走輸入欄的焦點。
          onMouseDown={(event) => event.preventDefault()}
          onClick={() => onPick(name)}
          className={`flex cursor-pointer flex-wrap items-baseline gap-x-3 gap-y-0.5 px-3 py-1.5 ${
            index === active ? 'bg-deck shadow-[inset_3px_0_0_var(--color-ink)]' : ''
          }`}
        >
          <span className="value text-sm text-ink">/{name}</span>
          <span className="min-w-0 flex-1 text-xs text-ink-dim">
            {t(`agent.slash.about.${name}`)}
          </span>
        </li>
      ))}
    </ul>
  )
}

type Shown = Exclude<SlashResult, { command: 'new' }>

/** 一個指令的結果，接在打它的那一刻的對話後面。 */
export function SlashOutput({ result }: { result: Shown }) {
  const { t } = useTranslation()
  return (
    <section
      aria-label={`/${result.command}`}
      className="grid min-w-0 gap-2 border-2 border-rule bg-well px-3 py-2"
    >
      <div className="flex flex-wrap items-baseline gap-x-3">
        <span className="label text-ink-dim">{t('agent.slash.label')}</span>
        <span className="value text-sm text-ink">/{result.command}</span>
      </div>
      <Body result={result} />
    </section>
  )
}

function Body({ result }: { result: Shown }) {
  switch (result.command) {
    case 'compact':
      return <Compacted result={result} />
    case 'usage':
      return <Usage result={result} />
    case 'status':
      return <Status result={result} />
    case 'pending':
      return <Pending result={result} />
    case 'skills':
      return <Skills result={result} />
  }
}

function useFormat() {
  const { i18n } = useTranslation()
  const language = i18n.language
  return {
    number: (value: number) => value.toLocaleString(language),
    percent: (value: number) =>
      new Intl.NumberFormat(language, { style: 'percent', maximumFractionDigits: 0 }).format(value),
  }
}

function Compacted({ result }: { result: Extract<Shown, { command: 'compact' }> }) {
  const { t } = useTranslation()
  if (result.error) {
    return (
      <p className="text-sm text-ink">
        {t('agent.slash.compact.failed')}{' '}
        <span className="value text-xs wrap-anywhere">{result.error}</span>
      </p>
    )
  }
  if (result.after === null) {
    return <p className="text-sm text-ink">{t('agent.slash.compact.nothing')}</p>
  }
  return (
    <p className="text-sm text-ink">
      {t('agent.slash.compact.done', { before: result.before, after: result.after })}
    </p>
  )
}

function Facts({ children }: { children: ReactNode }) {
  return <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1 text-sm">{children}</dl>
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <>
      <dt className="label self-baseline text-ink-dim">{label}</dt>
      <dd className="value min-w-0 text-ink wrap-anywhere">{children}</dd>
    </>
  )
}

function Usage({ result }: { result: Extract<Shown, { command: 'usage' }> }) {
  const { t } = useTranslation()
  const { number, percent } = useFormat()
  const unknown = t('agent.slash.usage.unknown')
  const hit =
    result.cache_read_tokens === null
      ? unknown
      : percent(result.input_tokens > 0 ? result.cache_read_tokens / result.input_tokens : 0)
  return (
    <>
      <Facts>
        <Fact label={t('agent.slash.usage.turns')}>{number(result.turns)}</Fact>
        {result.compactions > 0 ? (
          <Fact label={t('agent.slash.usage.compactions')}>{number(result.compactions)}</Fact>
        ) : null}
        <Fact label={t('agent.slash.usage.requests')}>{number(result.requests)}</Fact>
        <Fact label={t('agent.slash.usage.toolCalls')}>{number(result.tool_calls)}</Fact>
        <Fact label={t('agent.slash.usage.input')}>{number(result.input_tokens)}</Fact>
        <Fact label={t('agent.slash.usage.output')}>{number(result.output_tokens)}</Fact>
        <Fact label={t('agent.slash.usage.cacheHit')}>{hit}</Fact>
        <Fact label={t('agent.slash.usage.webSearches')}>{number(result.web_searches)}</Fact>
        <Fact label={t('agent.slash.usage.tavily')}>{number(result.tavily_searches)}</Fact>
        <Fact label={t('agent.slash.usage.cost')}>
          {result.cost_usd === null ? unknown : `$${result.cost_usd.toFixed(4)}`}
        </Fact>
      </Facts>
      <p className="text-xs text-ink-dim">{t('agent.slash.usage.note')}</p>
    </>
  )
}

function Status({ result }: { result: Extract<Shown, { command: 'status' }> }) {
  const { t } = useTranslation()
  const { number, percent } = useFormat()
  return (
    <Facts>
      <Fact label={t('agent.slash.status.model')}>
        {result.provider} · {result.model}
      </Fact>
      <Fact label={t('agent.slash.status.context')}>
        {result.context_tokens === null
          ? t('agent.slash.status.contextNone')
          : t('agent.slash.status.contextValue', {
              tokens: number(result.context_tokens),
              window: number(result.context_window),
              percent: percent(result.context_tokens / result.context_window),
            })}
      </Fact>
      <Fact label={t('agent.slash.status.compactAt')}>
        {t('agent.slash.status.compactAtValue', { percent: percent(result.compact_at) })}
      </Fact>
      <Fact label={t('agent.slash.status.messages')}>{number(result.messages)}</Fact>
      {result.paused_until ? (
        <Fact label={t('agent.slash.status.pausedUntil')}>
          <Timestamp at={result.paused_until} />
        </Fact>
      ) : null}
    </Facts>
  )
}

function Pending({ result }: { result: Extract<Shown, { command: 'pending' }> }) {
  const { t } = useTranslation()
  if (result.cards.length === 0) {
    return <p className="text-sm text-ink">{t('agent.slash.pending.none')}</p>
  }
  return (
    <ul className="grid gap-2">
      {result.cards.map((card) => (
        <li
          key={card.id}
          className="grid gap-0.5 border-t-2 border-rule pt-2 first:border-t-0 first:pt-0"
        >
          <div className="flex flex-wrap items-baseline gap-x-3">
            <span className="value text-sm text-ink">
              #{card.id} {card.command}
            </span>
            <span className="label text-ink-dim">
              {t(
                card.status === 'detached'
                  ? 'agent.slash.pending.status.detached'
                  : 'agent.slash.pending.status.pending',
              )}
            </span>
          </div>
          <p className="text-xs text-ink-dim">
            {t('agent.slash.pending.rows', { count: card.rows })} ·{' '}
            {t(card.here ? 'agent.slash.pending.here' : 'agent.slash.pending.elsewhere')} ·{' '}
            {t('agent.slash.pending.expires')} <Timestamp at={card.expires_at} />
          </p>
        </li>
      ))}
    </ul>
  )
}

function Skills({ result }: { result: Extract<Shown, { command: 'skills' }> }) {
  const { t } = useTranslation()
  if (result.skills.length === 0) {
    return <p className="text-sm text-ink">{t('agent.slash.skills.none')}</p>
  }
  return (
    <>
      <ul className="grid gap-2">
        {result.skills.map((skill) => (
          <li key={skill.name} className="grid gap-0.5">
            <span className="value text-sm text-ink">{skill.name}</span>
            <span className="text-xs text-ink-dim" lang="en">
              {skill.description}
            </span>
          </li>
        ))}
      </ul>
      <p className="text-xs text-ink-dim">{t('agent.slash.skills.note')}</p>
    </>
  )
}
