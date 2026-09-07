// UI 文案的唯一來源。zh-Hant 是唯一語言（plan §7）；檔名 token 與 log 保持英文。
export const resources = {
  'zh-Hant': {
    translation: {
      app: {
        name: 'Berth',
        tagline: '媒體取得與入庫協調器',
      },
      health: {
        title: '健康',
        checking: '檢查中…',
        unreachable: '連不上 Berth 後端。確認程序是否還在執行。',
        backend: '後端',
        version: '版本',
        value: {
          ok: '正常',
          degraded: '降級',
        },
      },
    },
  },
} as const
