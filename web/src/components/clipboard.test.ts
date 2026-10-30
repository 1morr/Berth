import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { copyText } from './clipboard'

// 區網 IP 走 HTTP 時不是 secure context：`navigator.clipboard` 是 `undefined`，只剩舊的 `execCommand('copy')`。
describe('copyText', () => {
  let copied: string | null
  let execCommand: ReturnType<typeof vi.fn>

  beforeEach(() => {
    copied = null
    execCommand = vi.fn((command: string) => {
      if (command !== 'copy') return false
      const area = document.activeElement
      copied =
        area instanceof HTMLTextAreaElement
          ? area.value.slice(area.selectionStart, area.selectionEnd)
          : null
      return true
    })
    Object.defineProperty(document, 'execCommand', { value: execCommand, configurable: true })
  })

  afterEach(() => {
    Reflect.deleteProperty(document, 'execCommand')
    Reflect.deleteProperty(navigator, 'clipboard')
  })

  function withoutClipboardApi() {
    Object.defineProperty(navigator, 'clipboard', { value: undefined, configurable: true })
  }

  it('有 Clipboard API 就用它', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })

    await expect(copyText('berth doctor')).resolves.toBe(true)
    expect(writeText).toHaveBeenCalledWith('berth doctor')
    expect(execCommand).not.toHaveBeenCalled()
  })

  it('沒有 Clipboard API（HTTP）時改用選取再複製', async () => {
    withoutClipboardApi()

    await expect(copyText('berth doctor')).resolves.toBe(true)
    expect(copied).toBe('berth doctor')
    // 借來選取的那一塊用完就拿掉。
    expect(document.querySelector('textarea')).toBeNull()
  })

  it('Clipboard API 被拒（例如沒權限）也退回舊方法', async () => {
    const writeText = vi.fn().mockRejectedValue(new DOMException('denied', 'NotAllowedError'))
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })

    await expect(copyText('berth doctor')).resolves.toBe(true)
    expect(copied).toBe('berth doctor')
  })

  it('兩條路都不通就回 false', async () => {
    withoutClipboardApi()
    execCommand.mockReturnValue(false)

    await expect(copyText('berth doctor')).resolves.toBe(false)
  })
})
