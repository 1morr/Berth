import { renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { WAITING_RETEST_MS } from './signals'
import { useWaitingRetest } from './useWaitingRetest'

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
})

type Props = {
  waiting: 'jellyfin' | null
  busy: boolean
  lastRetest: number
  retest: (kind: 'jellyfin') => void
}

function mount(initial: Omit<Props, 'lastRetest'> & { lastRetest?: number }) {
  return renderHook((props: Props) => useWaitingRetest(props), {
    initialProps: { lastRetest: 0, ...initial },
  })
}

describe('useWaitingRetest', () => {
  it('重測那一台還在啟動的服務，每 3 秒一次', () => {
    const retest = vi.fn()
    mount({ waiting: 'jellyfin', busy: false, retest })

    vi.advanceTimersByTime(WAITING_RETEST_MS - 1)
    expect(retest).not.toHaveBeenCalled()
    vi.advanceTimersByTime(1)
    expect(retest).toHaveBeenCalledExactlyOnceWith('jellyfin')
  })

  it('重新 render、呼叫端每次給一個新的函式，都不會重設 3 秒的計時（審計 S14）', () => {
    const first = vi.fn()
    const latest = vi.fn()
    const { rerender } = mount({ waiting: 'jellyfin', busy: false, retest: first })

    vi.advanceTimersByTime(WAITING_RETEST_MS - 1000)
    rerender({ waiting: 'jellyfin', busy: false, lastRetest: 0, retest: vi.fn() })
    rerender({ waiting: 'jellyfin', busy: false, lastRetest: 0, retest: latest })
    vi.advanceTimersByTime(1000)

    // 時間到的那一刻叫的是最新的那一個。
    expect(first).not.toHaveBeenCalled()
    expect(latest).toHaveBeenCalledExactlyOnceWith('jellyfin')
  })

  it('回應快到畫面沒畫出「在跑」，下一輪照樣從那一次重測起算 3 秒', () => {
    const retest = vi.fn()
    const { rerender } = mount({ waiting: 'jellyfin', busy: false, retest })

    vi.advanceTimersByTime(WAITING_RETEST_MS)
    expect(retest).toHaveBeenCalledOnce()
    // 那一輪送出又回來，`busy` 一直是 false，只有送出的時刻變了。
    rerender({ waiting: 'jellyfin', busy: false, lastRetest: WAITING_RETEST_MS, retest })
    vi.advanceTimersByTime(WAITING_RETEST_MS)
    expect(retest).toHaveBeenCalledTimes(2)
  })

  it('不在等、或有命令在跑時不重測', () => {
    const retest = vi.fn()
    const { rerender } = mount({ waiting: null, busy: false, retest })
    vi.advanceTimersByTime(WAITING_RETEST_MS * 2)

    rerender({ waiting: 'jellyfin', busy: true, lastRetest: 0, retest })
    vi.advanceTimersByTime(WAITING_RETEST_MS * 2)
    expect(retest).not.toHaveBeenCalled()

    // 命令跑完、仍在等：從那一刻起再算 3 秒。
    rerender({ waiting: 'jellyfin', busy: false, lastRetest: 0, retest })
    vi.advanceTimersByTime(WAITING_RETEST_MS)
    expect(retest).toHaveBeenCalledOnce()
  })
})
