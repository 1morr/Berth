import { useTranslation } from 'react-i18next'

import { RequestFailed } from '../components/RequestFailed'

/** 面板裡還在讀（AI 開著沒有、接回對話）：不動的佔位（DESIGN.md：沒有骨架屏動畫）。 */
export function PanelLoading() {
  const { t } = useTranslation()
  return (
    <div className="grid flex-1 content-start gap-3 p-4" aria-busy="true">
      <span className="sr-only">{t('agent.loading')}</span>
      <span aria-hidden="true" className="h-4 w-1/3 bg-deck" />
      <span aria-hidden="true" className="h-12 bg-deck" />
      <span aria-hidden="true" className="h-4 w-1/2 bg-deck" />
    </div>
  )
}

/** 面板裡讀不到（問 AI 開著沒有、接回對話）。 */
export function PanelFailed({ error }: { error: unknown }) {
  return (
    <div className="p-4">
      <RequestFailed error={error} />
    </div>
  )
}
