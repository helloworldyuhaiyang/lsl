import { buildApiUrl, requestJson } from '@/lib/api/client'

interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

export interface AuthUser {
  user_id: string
  provider: string
  provider_subject: string
  username?: string | null
  display_name?: string | null
  email?: string | null
  avatar_url?: string | null
  created_at: string
  updated_at: string
}

export interface AuthMeData {
  user: AuthUser | null
}

export async function getMe(): Promise<AuthMeData> {
  const response = await requestJson<ApiResponse<AuthMeData>>('/auth/me')
  return response.data
}

export async function logout(): Promise<AuthMeData> {
  const response = await requestJson<ApiResponse<AuthMeData>>('/auth/logout', {
    method: 'POST',
  })
  return response.data
}

export function getLoginUrl(): string {
  return buildApiUrl('/auth/login')
}
