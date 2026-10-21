import { useState } from 'react'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, onTestFinished, vi } from 'vitest'

import { renderInRoute } from '../test/render'
import { useHashTarget } from './useHashTarget'

function Page({ ready, ids }: { ready: boolean; ids: string[] }) {
  useHashTarget(ready)
  return (
    <ul>
      {ids.map((id) => (
        <li key={id} id={id}>
          {id}
        </li>
      ))}
    </ul>
  )
}

function Toggled() {
  const [ready, setReady] = useState(false)
  return (
    <>
      <button type="button" onClick={() => setReady(true)}>
        ready
      </button>
      <Page ready={ready} ids={['a-1']} />
    </>
  )
}

/** 路由器自己也會對片段呼叫 `scrollIntoView(true)`；這裡只數這個 hook 的那一種。 */
function centered(scrolled: ReturnType<typeof vi.fn>) {
  return scrolled.mock.calls.filter(([arg]) => (arg as { block?: string }).block === 'center')
}

function stubScroll() {
  const scrolled = vi.fn()
  const original = Element.prototype.scrollIntoView
  Element.prototype.scrollIntoView = scrolled
  onTestFinished(() => {
    Element.prototype.scrollIntoView = original
  })
  return scrolled
}

describe('useHashTarget', () => {
  it('ready 之前不動，ready 之後才捲過去', async () => {
    const scrolled = stubScroll()
    renderInRoute(<Toggled />, '/setup#a-1')
    await screen.findByText('a-1')
    expect(centered(scrolled)).toHaveLength(0)

    await userEvent.click(screen.getByRole('button', { name: 'ready' }))

    await waitFor(() => expect(centered(scrolled)).toHaveLength(1))
  })

  it('找不到那一列就什麼都不做', async () => {
    const scrolled = stubScroll()
    renderInRoute(<Page ready ids={['a-1']} />, '/setup#missing')
    await screen.findByText('a-1')

    expect(centered(scrolled)).toHaveLength(0)
    expect(document.body).toHaveFocus()
  })

  it('找得到：捲到中央、焦點落上去，重畫不再來一次', async () => {
    const scrolled = stubScroll()
    const view = renderInRoute(<Page ready ids={['a-1', 'a-2']} />, '/setup#a-2')

    await waitFor(() => expect(document.activeElement?.id).toBe('a-2'))
    expect(centered(scrolled)).toHaveLength(1)

    await view.router.invalidate()
    expect(centered(scrolled)).toHaveLength(1)
  })
})
