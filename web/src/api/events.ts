import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import { JOBS_LIST_KEY } from './jobs'
import type { Schemas } from './schemas'

/**
 * `GET /api/events/stream`：讓下載列表自己動（plan §6 events 群組、票 10）。
 *
 * 收到的是**提示不是真相**：後端只送 hash、狀態與進度，這裡拿它讓清單與那一筆失效再問一次。
 * 好處是漏掉一筆的後果是慢一點，不是畫面說謊——重連之後那一次重問會把中間錯過的全部補上。
 *
 * **一批推播只重抓一次**（M4 票 04）：poller 下載中每 5 秒一輪、每一筆有動的 Job 各推一個，RSS
 * 一次綁定就是上百筆。逐則失效的話一批 N 則就是 N 次整頁 `GET /jobs`。
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
 * 第一則推播之後等多久才失效（毫秒）。這段時間裡到的都併進同一次：poller 一輪的推播是同一刻
 * 送出來的，一秒涵蓋得了一輪；代價是單獨一則也晚一秒才畫上去。
 */
export const COALESCE_MS = 1000

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
    // 這一批推播到的 hash，與要把它們送出去的那一個計時器。
    const pending = new Set<string>()
    let timer: ReturnType<typeof setTimeout> | undefined

    const flush = () => {
      timer = undefined
      const keys = [JOBS_LIST_KEY, ...[...pending].map((hash) => ['jobs', hash])]
      // **有一份還在抓就等它回來**：`cancelRefetch: false` 不會再抓一次，而那一次是這一批推播之前
      // 送出去的——它回來時把失效標記清掉，這一批就沒了。取消重抓的話，一批一批不停的推播會讓清單
      // 永遠抓不完（後端照樣跑完每一次）。
      if (keys.some((queryKey) => queryClient.isFetching({ queryKey }) > 0)) {
        timer = setTimeout(flush, COALESCE_MS)
        return
      }
      pending.clear()
      // 清單與推播到的那幾筆（它們的詳情、時間線與計劃）；別的 Job 展開中的那幾份不動。
      for (const queryKey of keys) {
        void queryClient.invalidateQueries({ queryKey }, { cancelRefetch: false })
      }
    }

    // **連上的那一刻先重問一次。** 這條連線沒有補送：訂閱建立之前推出去的那幾筆誰都
    // 收不到，而「訂閱之前」包含**這一頁自己載入的那幾百毫秒**——實跑當場踩到：送單後
    // 那一筆在頁面還在連線時就完成了，於是畫面停在「已取得檔案清單」再也不動。
    // 同一行也涵蓋每一次重連（Berth 重啟、筆電睡醒、換基地台），那時候錯過的更多——不知道是哪幾筆，
    // 所以是整個 `['jobs']` 前綴，還沒送出的那一批也併進來。**這一次取消進行中的請求**：頁面自己載入的
    // 那一次正是在訂閱之前送出去的，沿用它就是上面那個 bug。代價是每次進頁多一個被取消的請求。
    const onOpen = () => {
      clearTimeout(timer)
      timer = undefined
      pending.clear()
      void queryClient.invalidateQueries({ queryKey: ['jobs'] })
    }
    const onJob = (event: MessageEvent<string>) => {
      // 認得出形狀才動作。
      const hash = signalledHash(event.data)
      if (hash === null) return
      pending.add(hash)
      timer ??= setTimeout(flush, COALESCE_MS)
    }

    source.addEventListener('open', onOpen)
    source.addEventListener(JOB_EVENT, onJob as EventListener)
    return () => {
      source.removeEventListener('open', onOpen)
      source.removeEventListener(JOB_EVENT, onJob as EventListener)
      clearTimeout(timer)
      // 一定要關：`EventSource` 不會因為元件卸載就自己收，而每一條沒收的連線在後端
      // 都是一個還在被寫入的佇列。
      source.close()
    }
  }, [queryClient])
}

/**
 * 推播說的是哪一筆；認不得的 payload 是 `null`，就丟掉。
 *
 * 後端加了新的欄位不該讓這一條炸掉——而如果它根本不是 JSON（反向代理插了一頁 HTML），
 * 靜靜忽略比讓整頁白掉好：清單本身是 `GET /jobs` 畫出來的，它還在。
 *
 * **只看形狀，不驗 `state` 的值**（也不讀它）：推播是提示不是資料，後端加一個新狀態時這一條
 * 仍然要讓清單去重問一次——擋下來只會讓畫面停在舊的狀態上。
 */
function signalledHash(data: string): string | null {
  try {
    const payload: unknown = JSON.parse(data)
    if (typeof payload !== 'object' || payload === null) return null
    const { hash, state } = payload as Partial<JobSignal>
    return typeof hash === 'string' && typeof state === 'string' ? hash : null
  } catch {
    return null
  }
}
