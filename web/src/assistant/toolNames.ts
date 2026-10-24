import type { TFunction } from 'i18next'

/**
 * 工具在畫面上的名字：一個登記的工具一格（後端 `services/tools.py`）。沒有文案的工具（後端先加了）
 * 退回「工具」，不印出 key。
 */
const TOOL_NAMES = {
  recent_imports: 'assistant.tools.recent_imports',
  missing_episodes: 'assistant.tools.missing_episodes',
  search_indexers: 'assistant.tools.search_indexers',
  submit_search_result: 'assistant.tools.submit_search_result',
  add_indexer: 'assistant.tools.add_indexer',
  delete_downloads: 'assistant.tools.delete_downloads',
  search_mikan: 'assistant.tools.search_mikan',
  mikan_subgroups: 'assistant.tools.mikan_subgroups',
  subscribe_mikan: 'assistant.tools.subscribe_mikan',
  subscribe_search_feed: 'assistant.tools.subscribe_search_feed',
  add_feed: 'assistant.tools.add_feed',
} as const

type ToolNameKey = (typeof TOOL_NAMES)[keyof typeof TOOL_NAMES]

export function toolName(t: TFunction, name: string): string {
  const key: ToolNameKey | undefined = Object.hasOwn(TOOL_NAMES, name)
    ? TOOL_NAMES[name as keyof typeof TOOL_NAMES]
    : undefined
  return key ? t(key) : t('assistant.tools.other')
}
