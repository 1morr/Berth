import { useEffect, useEffectEvent } from 'react'

import { WAITING_RETEST_MS } from './signals'

/**
 * 套件內那一台還在啟動（`waiting`）：每 3 秒重測一次，直到有結論或後端判逾時（M3 票 06g）。精靈的服務頁與
 * 設定頁的連線區共用這一份（M4 票 92）。
 *
 * 計時從三件事之一變了的那一刻起算：在等的那一台、有沒有命令在跑（`busy`，重測或存檔）、上一輪重測送出的時刻
 * （`lastRetest`，`useMutation` 的 `submittedAt`）。少了最後一個，回應快到畫面沒來得及畫出 `busy` 的那一輪
 * 之後就不會再測。`retest` 不在其中：時間到的那一刻才讀最新的那一個，呼叫端每次 render 給一個新的函式也不會
 * 把計時器一直往後推（審計 S14：`useMutation` 的回傳值每次 render 都是新物件）。
 */
export function useWaitingRetest<K>({
  waiting,
  busy,
  lastRetest,
  retest,
}: {
  /** 在等的那一台；沒有在等是 `null`。 */
  waiting: K | null
  busy: boolean
  lastRetest: number
  retest: (kind: K) => void
}) {
  const due = useEffectEvent((kind: K) => retest(kind))
  useEffect(() => {
    if (waiting === null || busy) return
    const timer = window.setTimeout(() => due(waiting), WAITING_RETEST_MS)
    return () => window.clearTimeout(timer)
  }, [waiting, busy, lastRetest])
}
