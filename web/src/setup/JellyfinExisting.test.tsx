import { render, screen } from '@testing-library/react'
import i18next from 'i18next'
import { afterEach, describe, expect, it } from 'vitest'

import '../i18n'
import type { BerthPath } from '../api/setup'
import { AddPathFailures } from './JellyfinExisting'

/**
 * 頁 3 加不上 Berth 路徑（M4 票 63，審計 C5）：同一台 Jellyfin 看不到 `/data` 是整台的事，合併成一則、
 * 列出受影響的媒體庫，補法只給一次；只關一個媒體庫的原因照舊一個一條。
 */

const HOST = { path: '/srv/berth/data', relative: false }

function unseen(library: string): BerthPath {
  return {
    library,
    path: `/data/library/${library}`,
    status: 'failed',
    reason: 'jellyfin_cannot_see',
    error: `Jellyfin cannot see /data/library/${library}`,
  }
}

afterEach(async () => {
  await i18next.changeLanguage('zh-Hant')
})

describe.each([
  ['zh-Hant', /^「Shows」、「Films」沒加上 Berth 路徑：/],
  ['en', /^No Berth path was added to “Shows” and “Films”:/],
] as const)('AddPathFailures（%s）', (language, listed) => {
  it('看不到 /data 的合併成一則，名字照語言列出、加引號；補法只有一份', async () => {
    await i18next.changeLanguage(language)
    render(
      <AddPathFailures
        results={[
          unseen('Shows'),
          unseen('Films'),
          { ...unseen('Anime'), reason: 'library_missing', error: 'gone' },
        ]}
        root="/data"
        host={HOST}
      />,
    )

    expect(
      screen.getByText(i18next.t('jellyfin.libraries.pathFailed.unseenTitle', { root: '/data' })),
    ).toBeVisible()
    expect(screen.getByText(listed)).toBeVisible()
    expect(screen.getAllByTestId('mount-fix')).toHaveLength(1)
    expect(
      screen.getByText(i18next.t('jellyfin.libraries.pathFailed.title', { library: 'Anime' })),
    ).toBeVisible()
  })
})
