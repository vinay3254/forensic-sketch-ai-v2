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
  details: CaseDetails
  latest_image_url: string | null
  version_count: number
}

// mirrors backend/cases/details.py
export const PERSON_FIELDS = [
  ['height', 'Height'],
  ['build', 'Build'],
  ['clothing', 'Clothing'],
  ['movement', 'Movement and walk'],
  ['voice', 'Voice and speech'],
  ['other_traits', 'Other traits'],
] as const
export const INCIDENT_FIELDS = [
  ['approach', 'Approach'],
  ['weapon', 'Weapon'],
  ['offence', 'Offence'],
  ['requesting_unit', 'Requesting unit'],
  ['reference', 'Reference no.'],
] as const
export type DetailKey = (typeof PERSON_FIELDS)[number][0] | (typeof INCIDENT_FIELDS)[number][0]
export type CaseDetails = Partial<Record<DetailKey, string>>

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
  photo_url: string | null
  interview_id: number | null
  uncertain: string[]
  localized: boolean
}

export interface ChatMsg {
  id: number
  role: 'user' | 'assistant'
  content: string
  version_id: number | null
  created_at: string
}

// mirrors backend/ai/prompts.py:VARIANTS
export const VARIANT_KINDS = [
  ['cap', 'Cap'],
  ['brimmed_hat', 'Brimmed hat'],
  ['hood', 'Hood'],
  ['glasses', 'Glasses'],
  ['sunglasses', 'Sunglasses'],
  ['moustache', 'Moustache'],
  ['full_beard', 'Full beard'],
  ['goatee', 'Goatee'],
  ['stubble', 'Stubble'],
  ['shaved_head', 'Shaved head'],
] as const

export type VariantKind = (typeof VARIANT_KINDS)[number][0]

export interface Variant {
  id: number
  version_id: number
  version_no: number
  kind: VariantKind
  label: string
  localized: boolean
  image_url: string
  created_at: string
}

export interface BodyFigure {
  id: number
  image_url: string
  created_at: string
}

export interface BodyType {
  key: string
  label: string
  image_url: string
}

export interface Head3D {
  id: number
  version_id: number
  version_no: number
  mesh_url: string
  created_at: string
}

export interface Health {
  status: string
  ai_mode: string
  head3d: 'on' | 'off'
}

export interface StyleItem {
  key: string
  label: string
  image_url: string | null
}

export interface StyleCategory {
  key: string
  label: string
  styles: StyleItem[]
}

export interface FigureParams {
  height_cm: number
  build: number
  muscle: number
  gender: number
  age: number
  top: 'none' | 'tshirt' | 'shirt' | 'hoodie' | 'jacket' | 'kurta'
  bottom: 'none' | 'trousers' | 'jeans' | 'shorts' | 'skirt'
  headwear: 'none' | 'cap'
}

export interface FigureState {
  params: FigureParams
  model_url: string
  reply: string | null
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
  'case_update',
  'image_view',
  'generate',
  'refine',
  'revert',
  'export',
  'make_photo',
  'variant_create',
  'style_apply',
  'figure_update',
  'figure_save',
  'body_create',
  'head_create',
  'angle_view_create',
  'interview_start',
  'interview_assist',
  'interview_confirm',
  'audit_view',
  'access_denied',
] as const

export type RecallStatus = 'remembered' | 'uncertain' | 'unknown'
export type InputSource = 'typed' | 'speech' | 'mixed'

export interface Question {
  key: string
  label: string
  prompt: string
  optional: boolean
}

export interface QuestionBank {
  free_recall: { key: string; label: string; prompt: string; guidance: string }
  features: Question[]
  extras: Question[]
}

export interface Answer {
  key: string
  prompt: string
  answer: string
  status: RecallStatus | null
  source: InputSource | null
}

export interface Interview {
  id: number
  case_id: number
  status: 'draft' | 'confirmed'
  free_recall: string
  free_recall_source: InputSource | null
  answers: Answer[]
  created_by: number
  created_at: string
  confirmed_by: number | null
  confirmed_at: string | null
  transcript_hash: string | null
}

export interface InterviewDraft {
  free_recall: string
  free_recall_source: InputSource | null
  answers: Omit<Answer, 'prompt'>[]
}
