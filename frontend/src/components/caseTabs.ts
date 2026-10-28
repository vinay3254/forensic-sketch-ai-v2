// the four pages of a case, in tab order (Alt+1…4)
export const CASE_PAGES = [
  { key: 'sketch', label: 'Sketch', path: (id: number) => `/cases/${id}` },
  { key: 'details', label: 'Details', path: (id: number) => `/cases/${id}/details` },
  { key: 'interview', label: 'Interview', path: (id: number) => `/cases/${id}/interview` },
  { key: 'sheet', label: 'Case sheet', path: (id: number) => `/cases/${id}/sheet` },
] as const

export function pageOf(pathname: string): (typeof CASE_PAGES)[number]['key'] {
  if (/\/details$/.test(pathname)) return 'details'
  if (/\/sheet$/.test(pathname)) return 'sheet'
  if (/\/interviews?(\/|$)/.test(pathname)) return 'interview'
  return 'sketch'
}
