import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18next from 'i18next'
import { afterEach, describe, expect, it } from 'vitest'

import '../i18n'
import { MountFix } from './MountFix'

/**
 * 使用者自己那一台要多加的掛載（M4 票 63，審計 P1-6）：三種寫法都帶 Berth 的 `DATA_ROOT` 真正的值；
 * 相對路徑說相對於哪裡、要換成絕對路徑；不知道值時照舊 `${DATA_ROOT}`。
 */

const ABSOLUTE = { path: '/mnt/user/media/Berth', relative: false }

afterEach(async () => {
  await i18next.changeLanguage('zh-Hant')
})

/** Unraid 那一格的欄位 → 值（`dt` / `dd` 成對）。 */
function unraidFields(): Record<string, string> {
  const terms = screen.getAllByRole('term')
  return Object.fromEntries(
    terms.map((term) => [term.textContent, term.nextElementSibling?.textContent ?? '']),
  )
}

describe.each(['zh-Hant', 'en'])('MountFix（%s）', (language) => {
  it('compose、docker run 與 Unraid 模板都是 Berth 的那個資料夾', async () => {
    await i18next.changeLanguage(language)
    const user = userEvent.setup()
    render(<MountFix service="jellyfin" root="/data" host={ABSOLUTE} />)

    expect(
      screen.getByText(/jellyfin:\s+volumes:\s+- \/mnt\/user\/media\/Berth:\/data/),
    ).toBeVisible()
    expect(screen.getByText('-v /mnt/user/media/Berth:/data')).toBeVisible()
    // 絕對路徑沒有要另外說的：片段照貼就對。
    expect(screen.queryByText(i18next.t('routes.fix.mount.hostUnknown'))).toBeNull()

    await user.click(screen.getByText(i18next.t('routes.fix.mount.unraid')))
    // 票 55 實測的欄位名（Unraid 7.1.4 的介面字串），不翻譯。
    expect(unraidFields()).toEqual({
      'Config Type': 'Path',
      Name: 'Berth',
      'Container Path': '/data',
      'Host Path': '/mnt/user/media/Berth',
      'Access Mode': 'Read/Write',
    })
    // CA 模板已經掛了 /data/tvshows 那種：照樣加，說會發生什麼（scripts/experiments/nested_data_mount.sh）。
    expect(screen.getByText(/\/data\/tvshows/)).toBeVisible()
  })

  it('相對路徑：說它相對於 Berth 的 docker-compose.yml、要換成絕對路徑', async () => {
    await i18next.changeLanguage(language)
    render(
      <MountFix service="qbittorrent" root="/data" host={{ path: './data', relative: true }} />,
    )

    const note = screen.getByText(i18next.t('routes.fix.mount.hostRelative', { path: './data' }))
    expect(note).toBeVisible()
    expect(note.textContent).toContain('docker-compose.yml')
    expect(screen.getByText('-v ./data:/data')).toBeVisible()
  })

  it('不知道值（compose 沒傳進來）：片段是 ${DATA_ROOT}，說去 Berth 的 .env 找', async () => {
    await i18next.changeLanguage(language)
    render(<MountFix service="qbittorrent" root="/data" host={{ path: '', relative: false }} />)

    expect(screen.getByText(i18next.t('routes.fix.mount.hostUnknown'))).toBeVisible()
    expect(screen.getByText('-v ${DATA_ROOT}:/data')).toBeVisible()
  })
})
