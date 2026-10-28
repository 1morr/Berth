import { useTranslation } from 'react-i18next'

/** 前幾筆直接列出，其餘收在 `<details>`：一季幾十筆的話 390 寬會太長。 */
const SHOWN = 5

/**
 * 一串發佈名（M5 票 26：關鍵字訂閱的第一批）：作品頁的訂閱面板與確認卡共用。`.value`，新的在前，照傳進來的順序。
 */
export function ReleaseTitles({ titles }: { titles: readonly string[] }) {
  const { t } = useTranslation()
  const rest = titles.slice(SHOWN)
  return (
    <>
      <ul className="grid gap-0.5">
        {titles.slice(0, SHOWN).map((title) => (
          <li key={title} className="value text-xs wrap-anywhere text-ink">
            {title}
          </li>
        ))}
      </ul>
      {rest.length > 0 ? (
        <details className="text-xs">
          <summary className="cursor-pointer text-ink-dim">
            {t('rss.releasesMore', { count: rest.length })}
          </summary>
          <ul className="mt-0.5 grid gap-0.5">
            {rest.map((title) => (
              <li key={title} className="value wrap-anywhere text-ink">
                {title}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </>
  )
}
