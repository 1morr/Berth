import { useTranslation } from 'react-i18next'

import {
  STICKY_BAR,
  STICKY_WIDE,
  GhostButton,
  PrimaryButton,
  TEXT_LINK,
} from '../components/controls'
import { STEP } from './navigation'

/**
 * 每一頁工作面底部的「上一個泊位 / 前往下一個泊位」（票 06d）。
 *
 * 「前往下一個」只在這一頁做完了才有（後端已經過了它）：前進只能靠把事做完。有它的時候它是
 * 這一頁的主要動作，所以固定在底部，**桌機也是**（M4 票 08：頁 3 做完是四條 Route 加上清單與重新
 * 檢查，1280 × 720 上它被擠到畫面外）；那一頁自己的「重跑」同時降成次要、不再固定
 * （兩個 sticky 會疊在同一個位置）。
 *
 * **還沒做完時，前進鍵的位置說還差什麼**（`missing`，M4 票 27）：每一件是一顆連結樣式的按鈕，按了把
 * 焦點送到那一區（`target` 是它的 `id`，那一區要 `tabIndex={-1}`）。只在桌機固定：窄版的底部是那一頁
 * 自己的主要動作（`STICKY_ACTION`）。
 */
export function BerthNav({
  onPrevious,
  onNext,
  missing = [],
}: {
  onPrevious?: () => void
  onNext?: () => void
  missing?: readonly { label: string; target: string }[]
}) {
  const { t } = useTranslation()
  const pending = !onNext && missing.length > 0
  if (!onPrevious && !onNext && !pending) return null

  return (
    <nav
      aria-label={t('setup.nav.label')}
      // 窄版也排成一列：固定在底部的一條要矮，上一個縮成它自己的寬度，下一個佔滿剩下的。
      className={`mt-8 grid grid-cols-[auto_minmax(0,1fr)] gap-3 sm:grid-cols-[auto_minmax(0,18rem)] sm:justify-between ${
        onNext ? STICKY_BAR : pending ? STICKY_WIDE : ''
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
        // `StepFrame` 在焦點掉回 body 時把它接到這一顆（票 06h）。
        <PrimaryButton type="button" data-berth-next onClick={onNext}>
          {t('setup.nav.next')}
        </PrimaryButton>
      )}
      {pending && (
        <p className="flex flex-wrap items-baseline gap-x-3 gap-y-1 self-center text-sm text-ink-dim">
          <span className="label">{t('setup.nav.missing')}</span>
          {missing.map((item) => (
            <button
              key={item.target}
              type="button"
              className={`${TEXT_LINK} text-left`}
              onClick={() => document.getElementById(item.target)?.focus()}
            >
              {item.label}
            </button>
          ))}
        </p>
      )}
    </nav>
  )
}

/**
 * 回頭看的那一頁說出能改什麼、不能改的去哪裡改，以頁號查（票 06e 把原本「步驟 → 頁名 → 字」
 * 兩張表收成這一張）。查表：動態組 key 過不了 `strictKeyChecks`。
 */
const REVISIT = {
  [STEP.jellyfin]: {
    can: 'setup.revisit.jellyfin.can',
    elsewhere: 'setup.revisit.jellyfin.elsewhere',
  },
  [STEP.qbittorrent]: {
    can: 'setup.revisit.qbittorrent.can',
    elsewhere: 'setup.revisit.qbittorrent.elsewhere',
  },
  [STEP.routes]: { can: 'setup.revisit.routes.can', elsewhere: 'setup.revisit.routes.elsewhere' },
  // 頁 4 依來源分兩套（M4 票 20）：套件內那一台 Berth 能移除站、改登入，你自己的那一台不行。
  // 這一格是還沒選時的預設（實際上做完這一頁一定選過了）。
  [STEP.indexer]: {
    can: 'setup.revisit.indexer.bundled.can',
    elsewhere: 'setup.revisit.indexer.bundled.elsewhere',
  },
  [STEP.tmdb]: { can: 'setup.revisit.tmdb.can', elsewhere: 'setup.revisit.tmdb.elsewhere' },
} as const

/** 套件內的 Jellyfin 回頭看時的「這裡能做」：「改位址」只有既有的那一台有（M4 票 31）。 */
const REVISIT_BUNDLED_JELLYFIN = {
  can: 'setup.revisit.jellyfin.bundledCan',
  elsewhere: 'setup.revisit.jellyfin.elsewhere',
} as const

/** 既有的 Prowlarr 回頭看時的那一套。 */
const REVISIT_EXISTING_INDEXER = {
  can: 'setup.revisit.indexer.existing.can',
  elsewhere: 'setup.revisit.indexer.existing.elsewhere',
} as const

/**
 * 回頭看的說明（票 06d）：每一步都是冪等命令，回頭照樣重跑；這一格做不到的事去哪裡做。
 * 只在這一頁已經做完（後端過了它）時出現——目前這一步要做的事，lede 已經說了。
 * 沒有說明的頁（完成頁）什麼都不畫。
 *
 * `origin` 是這一頁那個服務選了哪一種：頁 4 既有的 Prowlarr 說的是另一套（M4 票 20），頁 1 套件內的
 * Jellyfin 不提「改位址」（M4 票 31）。
 */
export function RevisitNote({ step, origin }: { step: number; origin?: 'bundled' | 'existing' }) {
  const { t } = useTranslation()
  const words =
    step === STEP.indexer && origin === 'existing'
      ? REVISIT_EXISTING_INDEXER
      : step === STEP.jellyfin && origin === 'bundled'
        ? REVISIT_BUNDLED_JELLYFIN
        : (REVISIT as Partial<Record<number, (typeof REVISIT)[keyof typeof REVISIT]>>)[step]
  if (!words) return null

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
