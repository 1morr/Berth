import type { ReactNode } from 'react'
import { Link } from '@tanstack/react-router'

/**
 * 到一筆下載的詳情頁（`/jobs/:hash`，M2 票 12）。`/review` 與 `/issues` 的列上「所屬下載」那一格都是它：
 * 那一頁有這一筆的完整時間線、整份計劃與它能按的動作。
 */
export function JobLink({ hash, children }: { hash: string; children: ReactNode }) {
  return (
    <Link
      to="/jobs/$hash"
      params={{ hash }}
      className="underline decoration-rule-strong underline-offset-4 hover:decoration-ink"
    >
      {children}
    </Link>
  )
}
