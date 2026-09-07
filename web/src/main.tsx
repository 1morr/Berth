import { StrictMode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from '@tanstack/react-router'
import { createRoot } from 'react-dom/client'

import './i18n'
import './index.css'
import { router } from './router'

const container = document.getElementById('root')
if (!container) {
  throw new Error('Missing #root element in index.html')
}

const queryClient = new QueryClient()

createRoot(container).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
)
