import { useTranslation } from 'react-i18next'

import { STICKY_ACTION, GhostButton, PrimaryButton } from '../components/controls'

/**
 * 每一頁工作面底部的「上一個泊位 / 前往下一個泊位」（票 06d）。
 *
 * 「前往下一個」只在這一頁做完了才有（後端已經過了它）：前進只能靠把事做完。有它的時候它是
 * 這一頁的主要動作，所以窄版固定在底部；那一頁自己的「重跑」同時降成次要、不再固定
 * （兩個 sticky 會疊在同一個位置）。
 */
export function BerthNav({ onPrevious, onNext }: { onPrevious?: () => void; onNext?: () => void }) {
  const { t } = useTranslation()
  if (!onPrevious && !onNext) return null

  return (
    <nav
      aria-label={t('setup.nav.label')}
      // 窄版也排成一列：固定在底部的一條要矮，上一個縮成它自己的寬度，下一個佔滿剩下的。
      className={`mt-8 grid grid-cols-[auto_minmax(0,1fr)] gap-3 sm:grid-cols-[auto_minmax(0,18rem)] sm:justify-between ${
        onNext ? STICKY_ACTION : ''
      }`}
    >
      {onPrevious ? (
        <GhostButton type="button" onClick={onPrevious}>
          {t('setup.nav.previous')}
        </GhostButton>
      ) : (
        <span aria-hidden />
      )}
      {onNext && (
        <PrimaryButton type="button" onClick={onNext}>
          {t('setup.nav.next')}
        </PrimaryButton>
      )}
    </nav>
  )
}

/** 回頭看的那一頁說出能改什麼、不能改的去哪裡改。查表：動態組 key 過不了 `strictKeyChecks`。 */
const REVISIT = {
  detect: { can: 'setup.revisit.detect.can', elsewhere: 'setup.revisit.detect.elsewhere' },
  jellyfin: { can: 'setup.revisit.jellyfin.can', elsewhere: 'setup.revisit.jellyfin.elsewhere' },
  qbittorrent: {
    can: 'setup.revisit.qbittorrent.can',
    elsewhere: 'setup.revisit.qbittorrent.elsewhere',
  },
  routes: { can: 'setup.revisit.routes.can', elsewhere: 'setup.revisit.routes.elsewhere' },
  source: { can: 'setup.revisit.source.can', elsewhere: 'setup.revisit.source.elsewhere' },
} as const

export type RevisitPage = keyof typeof REVISIT

/**
 * 回頭看的說明（票 06d）：每一步都是冪等命令，回頭照樣重跑；這一格做不到的事去哪裡做。
 * 只在這一頁已經做完（後端過了它）時出現——目前這一步要做的事，lede 已經說了。
 */
export function RevisitNote({ page }: { page: RevisitPage }) {
  const { t } = useTranslation()
  const words = REVISIT[page]

  return (
    <div
      role="note"
      aria-label={t('setup.revisit.label')}
      className="mt-4 grid max-w-prose gap-x-4 gap-y-2 border-2 border-rule bg-well px-4 py-3 sm:grid-cols-[auto_minmax(0,1fr)]"
    >
      <span className="label self-baseline text-ink-dim">{t('setup.revisit.can')}</span>
      <p className="text-sm text-ink">{t(words.can)}</p>
      <span className="label self-baseline text-ink-dim">{t('setup.revisit.elsewhere')}</span>
      <p className="text-sm text-ink-dim">{t(words.elsewhere)}</p>
    </div>
  )
}
