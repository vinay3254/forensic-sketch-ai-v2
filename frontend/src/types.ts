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
  'appearance',
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

export interface BodyModel {
  id: number
  body_id: number
  mesh_url: string
  source_url: string
  height_cm: number
  engine: string
  created_at: string
  blend_url: string | null
  script_url: string | null
  summary: string | null
}

export interface BlenderJob {
  id: number
  body_id: number
  status: 'queued' | 'drafting' | 'building' | 'opening' | 'complete' | 'failed'
  model_id: number | null
  error: string | null
  desktop_opened: boolean
  desktop_error: string | null
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
  'proportion_adjust',
  'export',
  'make_photo',
  'variant_create',
  'style_apply',
  'figure_update',
  'figure_save',
  'body_realistic',
  'body_create',
  'head_create',
  'angle_view_create',
  'interview_start',
  'interview_assist',
  'translate',
  'record_search',
  'record_view',
  'oversight_view',
  'supervisor_assign',
  'signup',
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
  lang?: string | null // only for words spoken in a language other than English
  english?: string | null // their English translation, which the sketch is made from
}

export interface Interview {
  id: number
  case_id: number
  status: 'draft' | 'confirmed'
  free_recall: string
  free_recall_source: InputSource | null
  free_recall_lang?: string | null
  free_recall_english?: string | null
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
  free_recall_lang?: string | null
  free_recall_english?: string | null
  answers: Omit<Answer, 'prompt'>[]
}

// proportion sliders (backend/face/proportions.py): each runs -1..1, 0 = as drawn
export const PROPORTION_SLIDERS = [
  ['eye_size', 'Eye size', 'Smaller', 'Bigger'],
  ['eye_spacing', 'Eye spacing', 'Closer', 'Wider'],
  ['nose_length', 'Nose length', 'Shorter', 'Longer'],
  ['nose_width', 'Nose width', 'Narrower', 'Wider'],
  ['mouth_width', 'Mouth width', 'Narrower', 'Wider'],
  ['face_length', 'Face length', 'Shorter', 'Longer'],
  ['jaw_width', 'Jaw width', 'Narrower', 'Wider'],
] as const
export type Proportions = Partial<Record<(typeof PROPORTION_SLIDERS)[number][0], number>>

// dictation languages (Chrome's Web Speech API codes); backend/translate.py has the same list
export const SPEECH_LANGS = [
  { code: 'en-IN', label: 'English (India)' },
  { code: 'en-US', label: 'English (US)' },
  { code: 'hi-IN', label: 'हिन्दी · Hindi' },
  { code: 'kn-IN', label: 'ಕನ್ನಡ · Kannada' },
  { code: 'te-IN', label: 'తెలుగు · Telugu' },
  { code: 'ta-IN', label: 'தமிழ் · Tamil' },
  { code: 'ml-IN', label: 'മലയാളം · Malayalam' },
  { code: 'mr-IN', label: 'मराठी · Marathi' },
  { code: 'bn-IN', label: 'বাংলা · Bengali' },
  { code: 'gu-IN', label: 'ગુજરાતી · Gujarati' },
] as const
export const isEnglish = (code: string | null | undefined) => !code || code.startsWith('en-')
export const langName = (code: string) => SPEECH_LANGS.find((l) => l.code === code)?.label.split(' · ').at(-1) ?? code

// demo criminal-records database (backend/records): fictional people, synthetic faces
export type ChargeStatus = 'under_investigation' | 'charge_sheeted' | 'convicted' | 'acquitted'
export const CHARGE_STATUS: Record<ChargeStatus, string> = {
  under_investigation: 'Under investigation',
  charge_sheeted: 'Charge-sheeted',
  convicted: 'Convicted',
  acquitted: 'Acquitted',
}

export interface RecordCounts {
  cases: number
  convicted: number
  acquitted: number
  pending: number
}

export interface RecordSummary extends RecordCounts {
  id: number
  record_no: string
  name: string
  alias: string | null
  gender: string
  age: number
  area: string
  marks: string | null
  photo_url: string
  latest_offence: string | null
  latest_date: string | null
}

export interface RecordSearch {
  demo: boolean
  notice: string
  total: number
  items: RecordSummary[]
  summary: RecordCounts & { people: number }
  areas: string[]
}

export interface RecordCharge {
  id: number
  fir_no: string
  police_station: string
  date: string
  section: string
  offence: string
  status: ChargeStatus
}

export interface RecordDetail extends RecordSummary {
  demo: boolean
  notice: string
  height_cm: number
  build: string
  source: string
  charges: RecordCharge[]
}

// admin oversight (backend/oversight): investigators and admins, from the audit log
export interface OversightPerson {
  user_id: number
  username: string
  role: string
  supervisor_id: number | null
  supervisor: string | null
  logins: number
  logouts: number
  failed_logins: number
  last_login: string | null
  last_logout: string | null
  last_seen: string | null
  active_now: boolean
  sessions: number
  actions: number
  cases: number
  cases_created: number
  sketches: number
  denied: number
}

export interface Oversight {
  team: OversightPerson[]
  admins: OversightPerson[]
  admin_choices: { id: number; username: string }[]
  totals: { investigators: number; mine: number; unassigned: number; active_now: number; logins: number; failed_logins: number; cases: number }
}

export type SessionEnd = 'logout' | 'new_login' | 'expired' | 'active'

export interface UserSession {
  id: number
  start: string
  end: string | null
  end_reason: SessionEnd
  ip: string | null
  user_agent: string | null
  actions: number
  by_action: Record<string, number>
  cases: { id: number; case_number: string; title: string }[]
}

export interface UserCase {
  case_id: number
  case_number: string | null
  title: string
  owned: boolean
  first: string
  last: string
  actions: number
  by_action: Record<string, number>
}

export type WorkGroup = 'sketch' | 'interview' | 'casework' | 'account'

export interface Dashboard {
  days: number
  daily: { date: string; groups: Record<WorkGroup, number>; logins: number; failed: number }[]
  people: {
    user_id: number
    username: string
    role: string
    supervisor: string | null
    online: boolean
    last_seen: string | null
    sessions: number
    cases: number
    actions: number
    sketches: number
    failed_logins: number
    denied: number
    daily_actions: number[]
  }[]
  sessions: { user_id: number; username: string; start: string; end: string | null; end_reason: string; actions: number; cases: number }[]
  recent: { id: number; ts: string; username: string | null; action: string; group: WorkGroup; case_id: number | null; case_number: string | null; case_title: string | null }[]
  totals: { investigators: number; admins: number; online: number; sessions: number; cases: number; sketches: number; failed_logins: number; denied: number }
}
