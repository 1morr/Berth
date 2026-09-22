import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import type { Schemas } from './schemas'

/**
 * `GET /api/events/stream`：讓下載列表自己動（plan §6 events 群組、票 10）。
 *
 * 收到的是**提示不是真相**：後端只送 hash、狀態與進度，這裡拿它讓 `['jobs']` 失效再問一次。
 * 好處是漏掉一筆的後果是慢一點，不是畫面說謊——重連之後那一次重問會把中間錯過的全部補上。
 *
 * 用原生 `EventSource` 而不是自己接 `fetch` 的串流：它自帶重連（斷線 3 秒後再試，
 * 由瀏覽器管），而重連正是這條連線最常發生的事——Berth 重啟、筆電睡醒、Wi-Fi 換基地台。
 * cookie 會自己帶（同源），而門禁對 GET 不要求 CSRF 標頭（`api/gate.py`）。
 */

/** SSE 的 `event:` 名。後端的 `services/events.py` 是同一個字串。 */
const JOB_EVENT = 'job'

/** 推播帶的那三格（後端 `api/events.py` 的 `JobSignalOut`）。 */
export type JobSignal = Schemas['JobSignalOut']

/**
 * 訂閱 job 的動靜，並讓相關 query 失效。
 *
 * **掛在需要它的那一頁上**，不在 AppShell：探索頁與設定頁不在乎 job 動了沒，而一條
 * 永遠開著的連線在後端就是一個永遠開著的訂閱。
 */
export function useJobStream(): void {
  const queryClient = useQueryClient()

  useEffect(() => {
    // jsdom 沒有 `EventSource`，而那裡的下載列表照樣畫得出來——推播是提示，不是資料來源。
    if (typeof EventSource === 'undefined') return

    const source = new EventSource('/api/events/stream')
    const refetch = () => {
      // `['jobs']` 是前綴，所以這一次失效同時涵蓋清單與每一列展開中的時間線
      // （`['jobs', hash, 'events']`），不必逐 hash 各發一次。
      void queryClient.invalidateQueries({ queryKey: ['jobs'] })
    }
    // **連上的那一刻先重問一次。** 這條連線沒有補送：訂閱建立之前推出去的那幾筆誰都
    // 收不到，而「訂閱之前」包含**這一頁自己載入的那幾百毫秒**——實跑當場踩到：送單後
    // 那一筆在頁面還在連線時就完成了，於是畫面停在「已取得檔案清單」再也不動。
    // 同一行也涵蓋每一次重連（Berth 重啟、筆電睡醒、換基地台），那時候錯過的更多。
    const onOpen = () => refetch()
    const onJob = (event: MessageEvent<string>) => {
      // 認得出形狀才動作。
      if (!looksLikeSignal(event.data)) return
      refetch()
    }

    source.addEventListener('open', onOpen)
    source.addEventListener(JOB_EVENT, onJob as EventListener)
    return () => {
      source.removeEventListener('open', onOpen)
      source.removeEventListener(JOB_EVENT, onJob as EventListener)
      // 一定要關：`EventSource` 不會因為元件卸載就自己收，而每一條沒收的連線在後端
      // 都是一個還在被寫入的佇列。
      source.close()
    }
  }, [queryClient])
}

/**
 * 認不得的 payload 就丟掉。
 *
 * 後端加了新的欄位不該讓這一條炸掉——而如果它根本不是 JSON（反向代理插了一頁 HTML），
 * 靜靜忽略比讓整頁白掉好：清單本身是 `GET /jobs` 畫出來的，它還在。
 *
 * **只看形狀，不驗 `state` 的值**（也不讀它）：推播是提示不是資料，後端加一個新狀態時這一條
 * 仍然要讓清單去重問一次——擋下來只會讓畫面停在舊的狀態上。
 */
function looksLikeSignal(data: string): boolean {
  try {
    const payload: unknown = JSON.parse(data)
    if (typeof payload !== 'object' || payload === null) return false
    const { hash, state } = payload as Partial<JobSignal>
    return typeof hash === 'string' && typeof state === 'string'
  } catch {
    return false
  }
}
