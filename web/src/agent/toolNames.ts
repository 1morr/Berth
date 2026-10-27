/** 工具名（後端的 `tool_name`：登錄表的名字把 `.` 換成 `_`）→ 人話。認不得的照原文畫。 */
const TOOL_NAMES = {
  discover_search_media: 'agent.tool.names.discover_search_media',
  why_not_explain: 'agent.tool.names.why_not_explain',
  jobs_list_jobs: 'agent.tool.names.jobs_list_jobs',
  jobs_read_job_events: 'agent.tool.names.jobs_read_job_events',
  // 票 13：送單那一條路。
  search_search_torrents: 'agent.tool.names.search_search_torrents',
  media_route_choices: 'agent.tool.names.media_route_choices',
  downloading_add_manual_download: 'agent.tool.names.downloading_add_manual_download',
  // 票 17：設了 Tavily key 才有；`web_search` 是 Anthropic 伺服器端那一種，不經登錄表。
  web_tavily_search: 'agent.tool.names.web_tavily_search',
  web_search: 'agent.tool.names.web_search',
} as const

/**
 * 一個工具的人話名稱的 i18n key；認不得是 `null`（照原文畫）。收側面板的工具名（`why_not_explain`），
 * 也收步驟頁上命令登錄表的名字（`why_not.explain`，M5 票 21）。
 */
export function toolNameKey(name: string) {
  const tool = name.replaceAll('.', '_')
  return Object.hasOwn(TOOL_NAMES, tool) ? TOOL_NAMES[tool as keyof typeof TOOL_NAMES] : null
}
