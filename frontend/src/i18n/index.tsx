import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { en } from './en'
import { zhCN } from './zh-CN'

export type LanguageCode = 'en' | 'zh-CN'
type Messages = typeof en
type TranslationKey = keyof Messages
type InterpolationValues = Record<string, string | number>
type MessageCatalog = Record<TranslationKey, string>

const STORAGE_KEY = 'lsl.uiLanguage'

const messages: Record<LanguageCode, MessageCatalog> = {
  en,
  'zh-CN': zhCN,
}

interface I18nContextValue {
  language: LanguageCode
  setLanguage: (language: LanguageCode) => void
  t: (key: TranslationKey, values?: InterpolationValues) => string
}

const I18nContext = createContext<I18nContextValue | null>(null)

function detectInitialLanguage(): LanguageCode {
  if (typeof window === 'undefined') return 'en'
  const saved = window.localStorage.getItem(STORAGE_KEY)
  if (saved === 'en' || saved === 'zh-CN') return saved
  return window.navigator.language.toLowerCase().startsWith('zh') ? 'zh-CN' : 'en'
}

function interpolate(template: string, values?: InterpolationValues): string {
  if (!values) return template
  return Object.entries(values).reduce(
    (result, [key, value]) => result.replaceAll(`{{${key}}}`, String(value)),
    template,
  )
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<LanguageCode>(() => detectInitialLanguage())

  const setLanguage = useCallback((nextLanguage: LanguageCode) => {
    setLanguageState(nextLanguage)
    window.localStorage.setItem(STORAGE_KEY, nextLanguage)
  }, [])

  useEffect(() => {
    document.documentElement.lang = language
  }, [language])

  const t = useCallback((key: TranslationKey, values?: InterpolationValues) => {
    const template = messages[language][key] ?? en[key] ?? key
    return interpolate(template, values)
  }, [language])

  const value = useMemo<I18nContextValue>(() => ({
    language,
    setLanguage,
    t,
  }), [language, setLanguage, t])

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n(): I18nContextValue {
  const context = useContext(I18nContext)
  if (!context) {
    throw new Error('useI18n must be used within I18nProvider')
  }
  return context
}
