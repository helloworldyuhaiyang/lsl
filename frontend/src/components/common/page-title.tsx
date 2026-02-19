import type { ReactNode } from 'react'

interface PageTitleProps {
  eyebrow?: string
  title: string
  description?: string
  actions?: ReactNode
}

export function PageTitle({ eyebrow, title, description, actions }: PageTitleProps) {
  return (
    <header className="flex flex-wrap items-start justify-between gap-4">
      <div className="space-y-2">
        {eyebrow ? (
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">{eyebrow}</p>
        ) : null}
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900 sm:text-3xl">{title}</h1>
        {description ? <p className="max-w-2xl text-sm text-slate-600">{description}</p> : null}
      </div>
      {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
    </header>
  )
}
