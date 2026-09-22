import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '../test/render'
import { ConfirmAction } from './controls'

function renderConfirm(onConfirm = vi.fn()) {
  renderWithProviders(
    <ConfirmAction
      label="刪除這條 Route"
      confirmLabel="確定刪除"
      warning="刪掉之後精靈與送單都不會再看到它。"
      pendingLabel="刪除中…"
      onConfirm={onConfirm}
    />,
  )
  return onConfirm
}

/**
 * 就地展開的二次確認沒有 dialog 替它管焦點（票 15 的 critique：確認之後焦點掉回 body，
 * 鍵盤使用者要從頁首重新 Tab 過來）。
 */
describe('ConfirmAction', () => {
  it('展開時焦點進到那段後果說明，取消之後回到觸發鍵', async () => {
    renderConfirm()

    await userEvent.click(screen.getByRole('button', { name: '刪除這條 Route' }))
    expect(screen.getByRole('group', { name: /精靈與送單都不會再看到它/ })).toHaveFocus()

    await userEvent.click(screen.getByRole('button', { name: '取消' }))
    expect(screen.getByRole('button', { name: '刪除這條 Route' })).toHaveFocus()
  })

  it('Esc 收起確認，不執行動作', async () => {
    const onConfirm = renderConfirm()

    await userEvent.click(screen.getByRole('button', { name: '刪除這條 Route' }))
    await userEvent.keyboard('{Escape}')

    expect(screen.queryByRole('button', { name: '確定刪除' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '刪除這條 Route' })).toHaveFocus()
    expect(onConfirm).not.toHaveBeenCalled()
  })

  it('確定之後執行動作，焦點回到觸發鍵', async () => {
    const onConfirm = renderConfirm()

    await userEvent.click(screen.getByRole('button', { name: '刪除這條 Route' }))
    await userEvent.click(screen.getByRole('button', { name: '確定刪除' }))

    expect(onConfirm).toHaveBeenCalledOnce()
    expect(screen.getByRole('button', { name: '刪除這條 Route' })).toHaveFocus()
  })

  /**
   * 票 03 第 3 條。jsdom 沒有版面引擎，量不到寬度，所以斷言的是決定寬度的**那一段字面**：
   * `auto` 軌會把剩下的空白分給取消（CSS Grid §12.8 的 stretch auto tracks），`max-content` 不會。
   *
   * 刻意不寫成 `toHaveClass(...CONFIRM_ACTIONS.split(' '))`——那是拿元件自己用的常數去比它自己，
   * 把 `max-content` 改回 `auto` 照樣綠（票 03 的 code review 抓到）。
   */
  it('取消與主要動作在同一列，且取消不吃掉剩下的寬度', async () => {
    renderConfirm()

    await userEvent.click(screen.getByRole('button', { name: '刪除這條 Route' }))
    const confirm = screen.getByRole('button', { name: '確定刪除' })
    const cancel = screen.getByRole('button', { name: '取消' })

    expect(confirm.parentElement).toBe(cancel.parentElement)
    const row = cancel.parentElement!.className
    expect(row).toContain('sm:grid-cols-[minmax(0,14rem)_max-content]')
    expect(row).not.toContain('_auto]')
  })
})
