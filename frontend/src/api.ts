import type {
  AuditFilters,
  AuditPage,
  AuditVerify,
  BodyFigure,
  BodyModel,
  BlenderJob,
  BodyType,
  Case,
  CaseDetail,
  CaseDetails,
  Head3D,
  Health,
  Interview,
  InterviewDraft,
  Proportions,
  QuestionBank,
  RecordDetail,
  RecordSearch,
  StyleCategory,
  FigureParams,
  FigureState,
  RefineResult,
  User,
  Variant,
  VariantKind,
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

export const generate = (caseId: number, description: string, lang?: string) =>
  post<Version>(`/api/cases/${caseId}/generate`, { description, lang })
export const translateText = (caseId: number, text: string, lang: string) =>
  post<{ english: string }>(`/api/cases/${caseId}/translate`, { text, lang })
export const refine = (caseId: number, message: string) =>
  post<RefineResult>(`/api/cases/${caseId}/refine`, { message })
export const revert = (caseId: number, versionId: number) =>
  post<Version>(`/api/cases/${caseId}/versions/${versionId}/revert`)

export const makePhoto = (caseId: number, versionId: number) =>
  post<Version>(`/api/cases/${caseId}/versions/${versionId}/photo`)

// a reshaped copy of the sketch as an object URL (caller revokes it); nothing is stored
export async function proportionPreview(caseId: number, versionId: number, adj: Proportions, signal?: AbortSignal) {
  const res = await fetch(`/api/cases/${caseId}/versions/${versionId}/proportions/preview`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(adj),
    signal,
  })
  if (!res.ok) {
    const err = (await res.json().catch(() => null))?.error
    throw new ApiError(err?.code ?? 'UNKNOWN', err?.message ?? `Request failed (${res.status}).`, res.status)
  }
  return URL.createObjectURL(await res.blob())
}

export const adjustProportions = (caseId: number, versionId: number, adj: Proportions) =>
  post<Version>(`/api/cases/${caseId}/versions/${versionId}/proportions`, adj)

export const saveDetails = (caseId: number, details: CaseDetails) =>
  request<CaseDetails>(`/api/cases/${caseId}/details`, { method: 'PUT', body: JSON.stringify(details) })

// null until a figure has been drawn
export const getBody = (caseId: number) =>
  request<BodyFigure>(`/api/cases/${caseId}/body`).catch((e) => {
    if (e instanceof ApiError && e.status === 404) return null
    throw e
  })
export const drawBody = (caseId: number) => post<BodyFigure>(`/api/cases/${caseId}/body`)

export const getBodyModel = (caseId: number) => request<BodyModel | null>(`/api/cases/${caseId}/figure/reconstruction`)
export const reconstructBody = (caseId: number, bodyId: number) =>
  post<BodyModel>(`/api/cases/${caseId}/figure/reconstruct`, { body_id: bodyId })
export const openBodyModel = (caseId: number, modelId: number) =>
  post<{ opened: boolean }>(`/api/cases/${caseId}/figure/reconstructions/${modelId}/blender`)

export const getBlenderJob = (caseId: number) => request<BlenderJob | null>(`/api/cases/${caseId}/figure/blender-jobs/latest`)
export const startBlenderJob = (caseId: number, bodyId: number, prompt: string) =>
  post<BlenderJob>(`/api/cases/${caseId}/figure/blender-jobs`, { body_id: bodyId, prompt })

export async function bodyModelMesh(url: string): Promise<ArrayBuffer> {
  const response = await fetch(url, { credentials: 'include' })
  if (!response.ok) {
    const error = (await response.json().catch(() => null))?.error
    throw new ApiError(error?.code ?? 'UNKNOWN', error?.message ?? 'Could not load reconstructed model.', response.status)
  }
  return response.arrayBuffer()
}

export const listBodyTypes = () => request<BodyType[]>('/api/body-types')

export const health = () => request<Health>('/health')
export const listHeads = (caseId: number) => request<Head3D[]>(`/api/cases/${caseId}/heads`)
export const makeHead = (caseId: number, versionId: number) => post<Head3D>(`/api/cases/${caseId}/versions/${versionId}/head`)

export const listStyles = () => request<StyleCategory[]>('/api/styles')
export const applyStyle = (caseId: number, body: { style: string } | { category: string; text: string }) =>
  post<RefineResult>(`/api/cases/${caseId}/style`, body)

export const getFigure = (caseId: number) => request<FigureState>(`/api/cases/${caseId}/figure`)
export const putFigure = (caseId: number, params: FigureParams) =>
  request<FigureState>(`/api/cases/${caseId}/figure`, { method: 'PUT', body: JSON.stringify(params) })
export const promptFigure = (caseId: number, text: string) => post<FigureState>(`/api/cases/${caseId}/figure/prompt`, { text })
export const saveFigure = (caseId: number) => post<{ body_id: number; image_url: string }>(`/api/cases/${caseId}/figure/save`)
export const figureBlendUrl = (caseId: number) => `/api/cases/${caseId}/figure.blend`

// the 3D model as raw GLB bytes; a 503 FIGURE_OFF means the Blender worker is not running
export async function figureModel(caseId: number, params?: FigureParams): Promise<ArrayBuffer> {
  const res = await fetch(params ? `/api/cases/${caseId}/figure/preview.glb` : `/api/cases/${caseId}/figure/model.glb`, {
    method: params ? 'POST' : 'GET',
    credentials: 'include',
    headers: params ? { 'Content-Type': 'application/json' } : undefined,
    body: params ? JSON.stringify(params) : undefined,
  })
  if (!res.ok) {
    const err = (await res.json().catch(() => null))?.error
    throw new ApiError(err?.code ?? 'UNKNOWN', err?.message ?? `Request failed (${res.status}).`, res.status)
  }
  return res.arrayBuffer()
}

export const listVariants = (caseId: number) => request<Variant[]>(`/api/cases/${caseId}/variants`)
export const makeVariant = (caseId: number, versionId: number, kind: VariantKind) =>
  post<Variant>(`/api/cases/${caseId}/versions/${versionId}/variants`, { kind })

export const sheetUrl = (caseId: number, versionId: number, format: 'png' | 'pdf') =>
  `/api/cases/${caseId}/sheet?version_id=${versionId}&format=${format}`

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
// Option B: feature key -> exact quotes from the saved free account
export const assistInterview = (caseId: number, id: number) =>
  post<{ covered: Record<string, string[]> }>(`/api/cases/${caseId}/interviews/${id}/assist`)
export const generateFromInterview = (caseId: number, id: number) =>
  post<Version>(`/api/cases/${caseId}/interviews/${id}/generate`)

export const searchRecords = (f: { q?: string; status?: string; area?: string }) => {
  const p = new URLSearchParams(Object.entries(f).filter(([, v]) => v) as [string, string][])
  return request<RecordSearch>(`/api/records?${p}`)
}
export const getRecord = (id: number) => request<RecordDetail>(`/api/records/${id}`)
