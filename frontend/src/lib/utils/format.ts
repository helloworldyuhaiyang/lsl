export function formatBytes(size: number): string {
  if (size < 1024) {
    return `${size} B`
  }

  const units = ['KB', 'MB', 'GB']
  let value = size / 1024
  let unitIndex = 0

  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024
    unitIndex += 1
  }

  return `${value.toFixed(2)} ${units[unitIndex]}`
}

export function formatDuration(seconds: number | null): string {
  if (seconds === null || Number.isNaN(seconds)) {
    return '--:--'
  }

  const total = Math.max(0, Math.floor(seconds))
  const minutes = Math.floor(total / 60)
  const remain = total % 60

  return `${String(minutes).padStart(2, '0')}:${String(remain).padStart(2, '0')}`
}

export function formatDateTime(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) {
    return '--'
  }

  return new Intl.DateTimeFormat('zh-CN', {
    hour12: false,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(date)
}
