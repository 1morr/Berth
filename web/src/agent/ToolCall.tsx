import type { DynamicToolUIPart, ToolUIPart } from 'ai'
import { getToolName } from 'ai'
import { useTranslation } from 'react-i18next'
import { defaultUrlTransform } from 'react-markdown'

import { INLINE_LINK } from '../components/controls'
import { ExpandHint } from '../components/ExpandHint'
import { toolNameKey } from './toolNames'

type Phase = 'running' | 'done' | 'failed'

/**
 * 後端交給模型的失敗（`services/agent._failure`）：命令拒絕、守法擋下（票 14）、參數錯、命令出錯。
 * 對模型它是一筆結果，對人是沒做成。伺服器端 `web_search` 被服務拒絕時是
 * `{type: 'web_search_tool_result_error', error_code}`，同樣是沒做成。
 */
const FAILURE_KEYS = ['refused', 'invalid_arguments', 'error'] as const

function failedOutput(output: unknown): boolean {
  return (
    typeof output === 'object' &&
    output !== null &&
    (FAILURE_KEYS.some((key) => Object.hasOwn(output, key)) ||
      (output as { type?: unknown }).type === 'web_search_tool_result_error')
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

/** 伺服器端 `web_search` 的一筆結果（`encrypted_content` 已在 API 拿掉，M5.5 票 03）。 */
interface SearchResult {
  title: string
  url: string
  pageAge: string
}

/** `web_search` 的結果是一串網頁才畫成清單；其他工具、錯誤或認不得的形狀照原文印。 */
function searchResults(name: string, output: unknown): SearchResult[] | null {
  if (name !== 'web_search' || !Array.isArray(output)) return null
  const rows: unknown[] = output
  if (!rows.every((row) => typeof row === 'object' && row !== null && 'url' in row)) return null
  return rows.map((row) => {
    const { title, url, page_age: pageAge } = row as Record<string, unknown>
    return {
      title: typeof title === 'string' ? title : '',
      url: String(url),
      pageAge: typeof pageAge === 'string' ? pageAge : '',
    }
  })
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
  const pages = part.state === 'output-available' ? searchResults(name, part.output) : null

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
        {pages ? (
          <SearchResults label={t('agent.tool.output')} pages={pages} />
        ) : result ? (
          <ToolText label={t('agent.tool.output')} text={result} />
        ) : null}
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

/** 網搜的結果：標題（連到那一頁）、網址原文與服務給的日期（`page_age`，原樣，可能沒有）。 */
function SearchResults({ label, pages }: { label: string; pages: SearchResult[] }) {
  const { t } = useTranslation()
  if (pages.length === 0) {
    return (
      <div className="grid min-w-0 gap-1">
        <span className="label text-ink-dim">{label}</span>
        <span className="text-xs text-ink-dim">{t('agent.tool.noPages')}</span>
      </div>
    )
  }
  return (
    <div className="grid min-w-0 gap-1">
      <span className="label text-ink-dim">{label}</span>
      <ol aria-label={label} className="grid min-w-0 gap-2">
        {pages.map((page, index) => {
          // 連不連同助理回覆的 markdown（react-markdown 的預設：`javascript:` 這類換成空的）。
          const href = defaultUrlTransform(page.url)
          return (
            <li key={`${index}-${page.url}`} className="grid min-w-0 gap-0.5">
              {href ? (
                <a
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={`${INLINE_LINK} text-sm wrap-anywhere text-ink`}
                >
                  {page.title || page.url}
                </a>
              ) : (
                <span className="text-sm wrap-anywhere text-ink">{page.title || page.url}</span>
              )}
              <span className="value text-xs wrap-anywhere text-ink-dim">{page.url}</span>
              {page.pageAge ? <span className="text-xs text-ink-dim">{page.pageAge}</span> : null}
            </li>
          )
        })}
      </ol>
    </div>
  )
}
