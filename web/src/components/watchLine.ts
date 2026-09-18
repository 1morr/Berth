import type { TFunction } from 'i18next'

import type { WatchState } from '../api/jellyfin'

/**
 * 觀看狀態那一行字（判定在後端，`services/watch.py`）：已看、看到幾 %（只有影片）、剩幾集沒看（只有劇集，沒開始看的
 * 也說——jellyfin-web 的計數徽章）。還沒看過的片是空字串。都是字，不靠顏色、不塗漆。
 *
 * 媒體庫牆的卡片（票 05）、Media 詳情的主按鈕與集卡（票 08）共用：同一句話各寫一份遲早會分岔。
 */
export function watchLine(t: TFunction, watch: WatchState): string {
  if (watch.played) return t('inventory.watch.played')
  if (watch.progress !== null) return t('inventory.watch.progress', { progress: watch.progress })
  if (watch.unplayed_episodes !== null) {
    return t('inventory.watch.unplayed', { count: watch.unplayed_episodes })
  }
  return ''
}
