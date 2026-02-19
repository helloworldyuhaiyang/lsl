import { Outlet } from 'react-router-dom'

import { AppHeader } from '@/app/layout/app-header'

export function AppShell() {
  return (
    <div className="min-h-screen bg-linear-to-b from-amber-50 via-slate-50 to-cyan-50">
      <AppHeader />
      <main className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 sm:py-10">
        <Outlet />
      </main>
    </div>
  )
}
