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
})
