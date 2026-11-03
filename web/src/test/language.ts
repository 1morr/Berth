import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/**
 * 從頁首切到英文。語言鍵在帳號選單裡（M5.5 票 07），所以先打開選單；選單換完語言不收。
 */
export async function switchToEnglish(
  user: ReturnType<typeof userEvent.setup> | typeof userEvent = userEvent,
) {
  await user.click(screen.getByRole('button', { name: /^帳號：/ }))
  await user.click(screen.getByRole('button', { name: 'EN' }))
}
