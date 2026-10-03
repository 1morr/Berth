import { screen, within } from '@testing-library/react'

/**
 * 精靈泊位板上的五格（`<ul>`）。不是整塊板：窄版的摘要列也在板裡、名字裡也有目前那一格的泊位碼
 * （M4 票 30），以整塊板為範圍找「BTH 3」會找到兩顆。
 */
export function boardCells(): HTMLElement {
  return within(screen.getByRole('region', { name: '泊位板' })).getByRole('list')
}

export async function findBoardCells(): Promise<HTMLElement> {
  return within(await screen.findByRole('region', { name: '泊位板' })).getByRole('list')
}
