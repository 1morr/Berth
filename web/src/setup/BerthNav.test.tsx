import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import '../i18n'
import { RevisitNote } from './BerthNav'
import { STEP } from './navigation'

/**
 * 回頭看頁 4 的說明依來源分兩套（M4 票 20）：套件內那一台 Berth 能移除站、改介面登入，
 * 你自己的那一台不行——同一頁寫著「不移除」，說明就不能叫人去移除。
 */
describe('頁 4 的回頭看', () => {
  it('套件內：說得出移除站與更換介面登入', () => {
    render(<RevisitNote step={STEP.indexer} origin="bundled" />)

    const note = screen.getByRole('note', { name: '回頭看' })
    expect(note).toHaveTextContent('移除不要的站')
    expect(note).toHaveTextContent('更換介面登入')
  })

  it('既有：不叫人移除，移除與登入指回那一台自己的介面', () => {
    render(<RevisitNote step={STEP.indexer} origin="existing" />)

    const note = screen.getByRole('note', { name: '回頭看' })
    expect(note).not.toHaveTextContent('移除不要的站')
    expect(note).toHaveTextContent('重新讀取站的清單')
    expect(note).toHaveTextContent('Berth 不移除你的站，也不碰它的登入')
  })

  it('其他頁不看來源', () => {
    render(<RevisitNote step={STEP.tmdb} origin="existing" />)

    expect(screen.getByRole('note', { name: '回頭看' })).toHaveTextContent('重貼一把 key')
  })
})
