import { useQuery, useQueryClient } from '@tanstack/react-query'

/**
 * 像 `useState`，但值放在 query cache：元件卸下再掛回來時還在（M4 票 31，實測 #40）。
 *
 * 頁 4 的「測試」與試搜結論原本是元件自己的 state。移除一站之後清單重讀，那幾秒畫面整段不畫
 * （`IndexerStep` 的 `mode`），回來時全部重掛，結論跟著不見。值只活在這個分頁：重新整理就沒了——
 * 它們是對活的站的一次現場探測，「測試」是只讀命令，不為了留住它而改成寫入（brief §14）。
 *
 * `key` 要帶上它說的是哪一台（換了一台 Prowlarr，上一台的結論不算）。
 */
export function useRemembered<T>(
  key: readonly unknown[],
  initial: () => T,
): [T, (update: (was: T) => T) => void] {
  const client = useQueryClient()
  const queryKey = ['remembered', ...key]
  const { data } = useQuery({
    queryKey,
    queryFn: initial,
    initialData: initial,
    enabled: false,
    staleTime: Infinity,
    gcTime: Infinity,
  })
  function set(update: (was: T) => T) {
    client.setQueryData<T>(queryKey, (was) => update(was ?? initial()))
  }
  return [data ?? initial(), set]
}
