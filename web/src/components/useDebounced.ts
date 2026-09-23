import { useEffect, useState } from 'react'

/** 鍵入即搜的防抖（使用者拍板）。每一個不同的字串都會花掉使用者自備的 TMDB 額度。 */
export const SEARCH_DEBOUNCE_MS = 500

/**
 * 鍵入即搜，但不是每個按鍵都送一次。探索頁的搜尋與待處理上的「選作品」共用：兩邊打的都是
 * `/discover/search`。
 */
export function useDebounced(value: string, delay: number) {
  const [settled, setSettled] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])

  return settled
}
