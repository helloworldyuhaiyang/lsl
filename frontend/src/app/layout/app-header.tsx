import { NavLink } from 'react-router-dom'

import { NAV_ITEMS } from '@/lib/constants/routes'
import { cn } from '@/lib/utils'

export function AppHeader() {
  return (
    <header className="border-b border-slate-200/80 bg-white/90 backdrop-blur">
      <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-4 sm:px-6">
        <div className="space-y-0.5">
          <p className="text-sm font-semibold tracking-[0.16em] text-slate-900">LSL</p>
          <p className="text-xs text-slate-500">Listening and speaking training workspace</p>
        </div>

        <nav className="flex items-center gap-2">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.href}
              to={item.href}
              className={({ isActive }) =>
                cn(
                  'rounded-md px-3 py-2 text-sm font-medium transition-colors',
                  isActive ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </div>
    </header>
  )
}
