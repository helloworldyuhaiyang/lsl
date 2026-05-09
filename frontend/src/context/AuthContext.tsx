import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { getLoginUrl, getMe, logout as logoutRequest } from '@/lib/api/auth'
import type { AuthUser } from '@/lib/api/auth'

interface AuthContextType {
  user: AuthUser | null
  loading: boolean
  error: string | null
  refreshUser: () => Promise<void>
  login: () => void
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refreshUser = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getMe()
      setUser(data.user)
    } catch (err) {
      setUser(null)
      setError(err instanceof Error ? err.message : 'Failed to load user')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refreshUser()
  }, [refreshUser])

  const login = useCallback(() => {
    window.location.assign(getLoginUrl())
  }, [])

  const logout = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      await logoutRequest()
      setUser(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to log out')
    } finally {
      setLoading(false)
    }
  }, [])

  const value = useMemo<AuthContextType>(
    () => ({
      user,
      loading,
      error,
      refreshUser,
      login,
      logout,
    }),
    [error, loading, login, logout, refreshUser, user],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}
