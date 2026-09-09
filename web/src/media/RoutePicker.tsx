import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { Media, RouteChoice } from '../api/media'
import { berthNumberOf } from '../components/berths'
import { SetupHint } from '../components/SetupHint'

/**
 * 「入庫到哪裡」那一行（shape brief §6、票 04b）。
 *
 * 這是一個**偏好，不是承諾**：選了不會寫進任何地方。票 08 的搜尋把它當查詢參數送、票 09 的
 * 送單把它當 body 送，`media.default_route_id` 由送單成功時寫成「上次用的」。為了一個下拉的
 * 初值多一支 `PUT /media/{id}/route` 不划算——多數人只有一條相符的 Route，自動選中之後
 * 這件事根本不存在。
 *
 * **它在動作列的位置上，但這一票不黏底**：`STICKY_ACTION` 存在是為了讓按鈕在捲動時還按得到
 * （shape brief §3），而這一票沒有按鈕——實跑量到那條 bar 在 390×844 上永遠佔著 ~80px，
 * 卻沒有任何東西按得下去。票 08 的搜尋鍵回到這一行時它跟著回來。
 */
export function RoutePicker({ media }: { media: Media }) {
  const { t } = useTranslation()
  const selectId = useId()
  // `undefined` 是「這一輪還沒動過」，與使用者刻意選「尚未指定」（`null`）不是同一件事：
  // 兩者混在一起的話，只有一條 Route 的人清掉選擇之後會被自動選回去。
  const [chosen, setChosen] = useState<number | null | undefined>(undefined)
  const routeId = chosen === undefined ? onlyChoice(media.routes) : chosen

  if (media.routes.length === 0) return <NoRoutes kind={media.kind} />

  return (
    <p className="grid gap-2 sm:max-w-sm">
      <label htmlFor={selectId} className="label text-ink-dim">
        {t('media.route.label')}
      </label>
      <select
        id={selectId}
        value={routeId ?? ''}
        onChange={(event) =>
          setChosen(event.target.value === '' ? null : Number(event.target.value))
        }
        className="value w-full border-2 border-rule bg-hull px-3 py-2.5 text-sm text-ink focus:border-rule-strong"
      >
        <option value="">{t('media.route.none')}</option>
        {media.routes.map((route) => (
          <option key={route.id} value={route.id}>
            {route.name}
          </option>
        ))}
      </select>
    </p>
  )
}

/** 只有一條收得下這部作品的 Route 時就是它——沒有第二個選項的選擇不該讓使用者做。 */
function onlyChoice(routes: RouteChoice[]): number | null {
  return routes.length === 1 ? routes[0].id : null
}

/**
 * 一條相符的 Route 都沒有：說得出下一步，而不是給一個空的下拉。
 *
 * 精靈跑完之後只有 admin 進得去（後端同時回 403），所以那條連結也只給 admin——
 * 對一般使用者它是死路，而他要的是「去叫管理員」（票 10 code-review 的同一條）。
 */
function NoRoutes({ kind }: { kind: Media['kind'] }) {
  const { t } = useTranslation()

  return (
    <div className="grid gap-3 border-2 border-rule bg-well px-3 py-3">
      <p className="max-w-prose text-sm text-ink">{t(`media.route.missing.${kind}`)}</p>
      {/* 泊位 4 是媒體庫路徑——Route 就是在那一步建的。 */}
      <SetupHint
        berth={berthNumberOf('library')}
        label={t('media.route.toSetup')}
        fallback={t('media.route.askAdmin')}
      />
    </div>
  )
}
