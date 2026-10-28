export type Role = 'officer' | 'admin'

export interface User {
  id: number
  username: string
  role: Role
}

export interface Case {
  id: number
  case_number: string
  title: string
  status: string
  created_at: string
  created_by: number
}

export const ATTRIBUTE_KEYS = [
  'gender',
  'age_range',
  'skin_tone',
  'face_shape',
  'jaw',
  'eyes',
  'eyebrows',
  'nose',
  'mouth',
  'ears',
  'hair',
  'facial_hair',
  'marks',
  'accessories',
  'notes',
] as const

export type Attributes = Record<(typeof ATTRIBUTE_KEYS)[number], string | null>

export interface Version {
  id: number
  version_no: number
  kind: string
  instruction: string
  attributes: Attributes
  created_at: string
  image_url: string
}

export interface ChatMsg {
  id: number
  role: 'user' | 'assistant'
  content: string
  version_id: number | null
  created_at: string
}

export interface CaseDetail {
  case: Case
  versions: Version[]
  chat: ChatMsg[]
}

export interface RefineResult {
  version: Version | null
  reply: string
}

export interface AuditRow {
  id: number
  ts: string
  user_id: number | null
  username: string | null
  role: string | null
  action: string
  case_id: number | null
  version_id: number | null
  ip: string | null
  user_agent: string | null
  detail: Record<string, unknown>
  prev_hash: string
  hash: string
}

export interface AuditPage {
  items: AuditRow[]
  total: number
}

export interface AuditVerify {
  ok: boolean
  rows: number
  first_bad_id?: number
}

export interface AuditFilters {
  action?: string
  case_id?: number
  since?: string
  until?: string
  page?: number
  page_size?: number
}

export const AUDIT_ACTIONS = [
  'login',
  'login_failed',
  'logout',
  'case_create',
  'case_list',
  'case_open',
  'image_view',
  'generate',
  'refine',
  'revert',
  'export',
  'audit_view',
  'access_denied',
] as const
