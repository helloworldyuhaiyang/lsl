import { useMemo, useRef, useState } from 'react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface FileDropzoneProps {
  disabled?: boolean
  onFileSelected: (file: File) => void
}

const ACCEPT = '.mp3,.wav,.m4a,audio/mpeg,audio/wav,audio/x-wav,audio/mp4,audio/m4a'

export function FileDropzone({ disabled = false, onFileSelected }: FileDropzoneProps) {
  const inputRef = useRef<HTMLInputElement | null>(null)
  const [isDragging, setIsDragging] = useState(false)

  const label = useMemo(() => {
    if (disabled) {
      return 'Upload in progress...'
    }
    return 'Drag and drop an audio file here, or click to choose from local disk.'
  }, [disabled])

  return (
    <div className="space-y-3">
      <input
        ref={inputRef}
        className="hidden"
        type="file"
        accept={ACCEPT}
        onChange={(event) => {
          const file = event.target.files?.[0]
          if (file) {
            onFileSelected(file)
          }
          event.currentTarget.value = ''
        }}
      />

      <button
        type="button"
        disabled={disabled}
        onDragOver={(event) => {
          event.preventDefault()
          if (!disabled) {
            setIsDragging(true)
          }
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(event) => {
          event.preventDefault()
          setIsDragging(false)
          if (disabled) {
            return
          }
          const file = event.dataTransfer.files?.[0]
          if (file) {
            onFileSelected(file)
          }
        }}
        onClick={() => inputRef.current?.click()}
        className={cn(
          'w-full rounded-xl border border-dashed px-6 py-10 text-left transition-colors',
          isDragging ? 'border-cyan-400 bg-cyan-50/80' : 'border-slate-300 bg-slate-50/70',
          disabled ? 'cursor-not-allowed opacity-60' : 'hover:border-slate-400 hover:bg-slate-100/70',
        )}
      >
        <p className="text-sm font-medium text-slate-700">Audio Input</p>
        <p className="mt-2 text-sm text-slate-600">{label}</p>
        <p className="mt-3 text-xs text-slate-500">Supported: mp3 / wav / m4a</p>
      </button>
    </div>
  )
}
