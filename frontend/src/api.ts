import type {
  AuditFilters,
  AuditPage,
  AuditVerify,
  Case,
  CaseDetail,
  Interview,
  InterviewDraft,
  QuestionBank,
  RefineResult,
  User,
  Version,
} from './types'

export class ApiError extends Error {
  code: string
  status: number

  constructor(code: string, message: string, status: number) {
    super(message)
    this.code = code
    this.status = status
  }
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    credentials: 'include',
    headers: init?.body ? { 'Content-Type': 'application/json', ...init.headers } : init?.headers,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    const err = body?.error
    const apiError = new ApiError(err?.code ?? 'UNKNOWN', err?.message ?? `Request failed (${res.status}).`, res.status)
    // a session that expired mid-use goes back to the login page; the login call itself reports its own 401
    if (res.status === 401 && path !== '/api/auth/login' && path !== '/api/auth/me' && location.pathname !== '/login') {
      location.assign('/login')
    }
    throw apiError
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })

export const login = (username: string, password: string) => post<User>('/api/auth/login', { username, password })
export const logout = () => post<void>('/api/auth/logout')
export const me = () => request<User>('/api/auth/me')

export const listCases = () => request<Case[]>('/api/cases')
export const createCase = (title: string) => post<Case>('/api/cases', { title })
export const getCase = (id: number) => request<CaseDetail>(`/api/cases/${id}`)

export const generate = (caseId: number, description: string) =>
  post<Version>(`/api/cases/${caseId}/generate`, { description })
export const refine = (caseId: number, message: string) =>
  post<RefineResult>(`/api/cases/${caseId}/refine`, { message })
export const revert = (caseId: number, versionId: number) =>
  post<Version>(`/api/cases/${caseId}/versions/${versionId}/revert`)

export const makePhoto = (caseId: number, versionId: number) =>
  post<Version>(`/api/cases/${caseId}/versions/${versionId}/photo`)

export const exportUrl = (caseId: number, versionId: number, style: 'photo' | 'sketch') =>
  `/api/cases/${caseId}/versions/${versionId}/export?style=${style}`

export function auditList(filters: AuditFilters) {
  const params = new URLSearchParams()
  for (const [k, v] of Object.entries(filters)) {
    if (v !== undefined && v !== '') params.set(k, String(v))
  }
  return request<AuditPage>(`/api/audit?${params}`)
}
export const auditVerify = () => request<AuditVerify>('/api/audit/verify')

export const interviewQuestions = () => request<QuestionBank>('/api/interview/questions')
export const listInterviews = (caseId: number) => request<Interview[]>(`/api/cases/${caseId}/interviews`)
export const startInterview = (caseId: number) => post<Interview>(`/api/cases/${caseId}/interviews`)
export const getInterview = (caseId: number, id: number) => request<Interview>(`/api/cases/${caseId}/interviews/${id}`)
export const saveInterview = (caseId: number, id: number, draft: InterviewDraft) =>
  request<Interview>(`/api/cases/${caseId}/interviews/${id}`, { method: 'PUT', body: JSON.stringify(draft) })
export const confirmInterview = (caseId: number, id: number) =>
  post<Interview>(`/api/cases/${caseId}/interviews/${id}/confirm`, { witness_confirmed: true })
