import { cn } from '@/lib/utils'

interface UploadProgressProps {
  value: number
}

export function UploadProgress({ value }: UploadProgressProps) {
  return (
    <div className="space-y-2">
      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200">
        <div
          className={cn('h-full rounded-full bg-slate-900 transition-all duration-300')}
          style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
        />
      </div>
      <p className="text-xs text-slate-600">Upload progress: {Math.max(0, Math.min(100, value))}%</p>
    </div>
  )
}
