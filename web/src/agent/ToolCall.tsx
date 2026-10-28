import type { DynamicToolUIPart, ToolUIPart } from 'ai'
import { getToolName } from 'ai'
import { useTranslation } from 'react-i18next'

import { ExpandHint } from '../components/ExpandHint'
import { toolNameKey } from './toolNames'

type Phase = 'running' | 'done' | 'failed'

/**
 * 後端交給模型的失敗（`services/agent._failure`）：命令拒絕、守法擋下（票 14）、參數錯、命令出錯。
 * 對模型它是一筆結果，對人是沒做成。
 */
const FAILURE_KEYS = ['refused', 'invalid_arguments', 'error'] as const

function failedOutput(output: unknown): boolean {
  return (
    typeof output === 'object' &&
    output !== null &&
    FAILURE_KEYS.some((key) => Object.hasOwn(output, key))
  )
}

function phaseOf(part: ToolUIPart | DynamicToolUIPart): Phase {
  switch (part.state) {
    case 'output-available':
      return failedOutput(part.output) ? 'failed' : 'done'
    case 'output-error':
    case 'output-denied':
      return 'failed'
    default:
      // 參數還在串、等結果、等確認（確認卡是票 13）：都還沒有結論。
      return 'running'
  }
}

function pretty(value: unknown): string {
  if (value === undefined) return ''
  if (typeof value === 'string') return value
  return JSON.stringify(value, null, 2)
}

/**
 * 助理叫的一個工具，收成一行（M5 票 12，`.scratch/m5/side-panel-shape.md`〈面板結構〉）。
 *
 * 執行中是 `working` 色塊；完成是常態，不塗漆；沒成功也不塗紅——助理自己會看那個結果，不是擋住你的事，
 * 框換成重線（The Heavier Line Rule）。展開看參數與結果的原文。
 */
export function ToolCall({ part }: { part: ToolUIPart | DynamicToolUIPart }) {
  const { t } = useTranslation()
  const name = getToolName(part)
  const key = toolNameKey(name)
  const known = key ? t(key) : null
  const phase = phaseOf(part)
  const result = part.state === 'output-error' ? part.errorText : pretty(part.output)

  return (
    <details
      className={`group min-w-0 border-2 bg-well ${phase === 'failed' ? 'border-rule-strong' : 'border-rule'}`}
    >
      <summary className="flex cursor-pointer flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2 [&::-webkit-details-marker]:hidden">
        <span className="label text-ink-dim">{t('agent.tool.label')}</span>
        {known ? (
          <span className="min-w-0 flex-1 text-sm text-ink">{known}</span>
        ) : (
          <span className="value min-w-0 flex-1 text-xs wrap-anywhere text-ink">{name}</span>
        )}
        {phase === 'running' ? (
          <span className="label bg-working px-1.5 py-0.5 text-on-signal">
            {t('agent.tool.running')}
          </span>
        ) : (
          <span className="label text-ink-dim">
            {phase === 'done' ? t('agent.tool.done') : t('agent.tool.failed')}
          </span>
        )}
        <ExpandHint />
      </summary>
      <div className="grid gap-2 border-t-2 border-rule bg-hull px-3 py-2">
        <ToolText label={t('agent.tool.input')} text={pretty(part.input)} />
        {result ? <ToolText label={t('agent.tool.output')} text={result} /> : null}
      </div>
    </details>
  )
}

function ToolText({ label, text }: { label: string; text: string }) {
  return (
    <div className="grid min-w-0 gap-1">
      <span className="label text-ink-dim">{label}</span>
      <pre className="value text-xs whitespace-pre-wrap wrap-anywhere text-ink">{text}</pre>
    </div>
  )
}
