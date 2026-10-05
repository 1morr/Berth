import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import '../i18n'
import { step } from '../test/fixtures'
import { StepLine } from './StepLine'

describe('StepLine 的狀態字', () => {
  it('預設照狀態說：待處理是「尚未執行」', () => {
    render(<StepLine label="Prowlarr" row={step('prowlarr', 'pending', '0')} />)

    expect(screen.getByText('尚未執行')).toBeInTheDocument()
  })

  it('呼叫端說得出這一種待處理是什麼時換掉它（M4 票 31：連上了、0 站是「還沒有站」）', () => {
    render(<StepLine label="Prowlarr" status="還沒有站" row={step('prowlarr', 'pending', '0')} />)

    expect(screen.getByText('還沒有站')).toBeInTheDocument()
    expect(screen.queryByText('尚未執行')).not.toBeInTheDocument()
  })
})
