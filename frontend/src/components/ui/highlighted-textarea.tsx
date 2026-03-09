import { Fragment, type ReactNode, useEffect, useRef, useState } from 'react'

interface HighlightedTextareaProps {
  value: string
  onChange: (nextValue: string) => void
}

const BRACKET_SEGMENT_PATTERN = /\[[^[\]]*]/g
const MIN_TEXTAREA_HEIGHT = 48

function syncTextareaHeight(textarea: HTMLTextAreaElement | null) {
  if (!textarea) {
    return
  }

  textarea.style.height = '0px'
  textarea.style.height = `${Math.max(textarea.scrollHeight, MIN_TEXTAREA_HEIGHT)}px`
}

function renderHighlightedText(value: string) {
  const content = value.length > 0 ? value : '\u200b'
  const parts: ReactNode[] = []
  let lastIndex = 0

  for (const match of content.matchAll(BRACKET_SEGMENT_PATTERN)) {
    const matchedText = match[0]
    const start = match.index ?? 0

    if (start > lastIndex) {
      parts.push(
        <Fragment key={`plain-${lastIndex}`}>
          {content.slice(lastIndex, start)}
        </Fragment>,
      )
    }

    parts.push(
      <span key={`cue-${start}`} className="text-amber-600">
        {matchedText}
      </span>,
    )
    lastIndex = start + matchedText.length
  }

  if (lastIndex < content.length) {
    parts.push(
      <Fragment key={`plain-${lastIndex}`}>
        {content.slice(lastIndex)}
      </Fragment>,
    )
  }

  if (value.endsWith('\n')) {
    parts.push(<Fragment key="trailing-newline">{'\n\u200b'}</Fragment>)
  }

  return parts
}

export function HighlightedTextarea({ value, onChange }: HighlightedTextareaProps) {
  const [scrollTop, setScrollTop] = useState(0)
  const [scrollLeft, setScrollLeft] = useState(0)
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)

  useEffect(() => {
    syncTextareaHeight(textareaRef.current)
  }, [value])

  useEffect(() => {
    if (typeof ResizeObserver === 'undefined') {
      return
    }

    const textarea = textareaRef.current
    if (!textarea) {
      return
    }

    const observer = new ResizeObserver(() => {
      syncTextareaHeight(textarea)
    })
    observer.observe(textarea)

    return () => observer.disconnect()
  }, [])

  return (
    <div className="relative rounded-xl border border-slate-200 bg-white transition focus-within:border-slate-400 focus-within:ring-2 focus-within:ring-slate-200">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 overflow-hidden rounded-xl px-3 py-3 text-sm leading-6"
      >
        <div
          className="min-h-full whitespace-pre-wrap break-words text-slate-900"
          style={{ transform: `translate(${-scrollLeft}px, ${-scrollTop}px)` }}
        >
          {renderHighlightedText(value)}
        </div>
      </div>

      <textarea
        ref={textareaRef}
        value={value}
        onChange={(event) => {
          onChange(event.target.value)
          syncTextareaHeight(event.currentTarget)
        }}
        onScroll={(event) => {
          setScrollTop(event.currentTarget.scrollTop)
          setScrollLeft(event.currentTarget.scrollLeft)
        }}
        rows={1}
        className="relative z-10 w-full resize-none overflow-hidden border-0 bg-transparent px-3 py-3 text-sm leading-6 text-transparent caret-slate-900 outline-none selection:bg-slate-200/70"
      />
    </div>
  )
}
