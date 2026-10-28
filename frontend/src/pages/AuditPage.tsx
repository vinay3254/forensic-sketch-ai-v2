import { keepPreviousData, useMutation, useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, FilterX, ScrollText, ShieldAlert, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { auditList, auditVerify } from '../api'
import { Badge, Button, Card, EmptyState, ErrorBanner, Field, inputClass, PageHeader, Spinner, type Tone } from '../components/ui'
import { AUDIT_ACTIONS, type AuditFilters } from '../types'

const PAGE_SIZE = 50

// datetime-local gives local wall time with no zone; send it as an absolute instant
const toIso = (local: string) => (local ? new Date(local).toISOString() : undefined)

const ACTION_TONE: Record<string, Tone> = {
  login: 'neutral',
  logout: 'neutral',
  login_failed: 'red',
  access_denied: 'red',
  case_create: 'green',
  case_list: 'neutral',
  case_open: 'neutral',
  image_view: 'neutral',
  generate: 'violet',
  refine: 'violet',
  revert: 'amber',
  make_photo: 'violet',
  export: 'blue',
  audit_view: 'neutral',
}

export default function AuditPage() {
  const [action, setAction] = useState('')
  const [caseId, setCaseId] = useState('')
  const [since, setSince] = useState('')
  const [until, setUntil] = useState('')
  const [page, setPage] = useState(1)

  const filters: AuditFilters = {
    action: action || undefined,
    case_id: caseId ? Number(caseId) : undefined,
    since: toIso(since),
    until: toIso(until),
    page,
    page_size: PAGE_SIZE,
  }
  const { data, isPending, isFetching, error } = useQuery({
    queryKey: ['audit', filters],
    queryFn: () => auditList(filters),
    placeholderData: keepPreviousData,
  })
  const verify = useMutation({ mutationFn: auditVerify })
  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1
  const filtered = !!(action || caseId || since || until)

  function filterSetter(set: (v: string) => void) {
    return (v: string) => {
      set(v)
      setPage(1)
    }
  }

  function clear() {
    setAction('')
    setCaseId('')
    setSince('')
    setUntil('')
    setPage(1)
  }

  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader
        title="Audit log"
        subtitle="Every sign-in, case access, generation and export, chained by SHA-256 so edits or deletions show up on verification."
        actions={
          <>
            {verify.data &&
              (verify.data.ok ? (
                <div className="flex items-center gap-2 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800 ring-1 ring-inset ring-emerald-200">
                  <ShieldCheck className="size-4" />
                  Chain intact · {verify.data.rows} rows
                </div>
              ) : (
                <div className="flex items-center gap-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800 ring-1 ring-inset ring-red-200">
                  <ShieldAlert className="size-4" />
                  Tampering detected at row #{verify.data.first_bad_id}
                </div>
              ))}
            <Button onClick={() => verify.mutate()} loading={verify.isPending} icon={<ShieldCheck className="size-4" />}>
              Verify integrity
            </Button>
          </>
        }
      />
      {verify.isError && (
        <div className="mb-4">
          <ErrorBanner message={verify.error.message} />
        </div>
      )}

      <Card className="mb-4 p-4">
        <div className="grid grid-cols-2 items-end gap-3 md:grid-cols-[1fr_8rem_1fr_1fr_auto]">
          <Field label="Action">
            <select value={action} onChange={(e) => filterSetter(setAction)(e.target.value)} className={`${inputClass} h-9`}>
              <option value="">All actions</option>
              {AUDIT_ACTIONS.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Case ID">
            <input type="number" min={1} value={caseId} onChange={(e) => filterSetter(setCaseId)(e.target.value)} placeholder="Any" className={`${inputClass} h-9`} />
          </Field>
          <Field label="From">
            <input type="datetime-local" value={since} onChange={(e) => filterSetter(setSince)(e.target.value)} className={`${inputClass} h-9`} />
          </Field>
          <Field label="To">
            <input type="datetime-local" value={until} onChange={(e) => filterSetter(setUntil)(e.target.value)} className={`${inputClass} h-9`} />
          </Field>
          <Button variant="ghost" onClick={clear} disabled={!filtered} icon={<FilterX className="size-4" />} className="h-9">
            Clear
          </Button>
        </div>
      </Card>

      {error && <ErrorBanner message={error.message} />}
      <Card className="overflow-hidden">
        {isPending ? (
          <Spinner />
        ) : data && data.items.length === 0 ? (
          <EmptyState icon={<ScrollText className="size-5" />} title="No matching entries" body="Try widening the filters." />
        ) : (
          <div className={`overflow-x-auto transition ${isFetching ? 'opacity-60' : ''}`}>
            <table className="w-full text-left text-sm">
              <thead className="bg-paper-50 text-[11px] uppercase tracking-wider text-ink-400">
                <tr>
                  <th className="px-4 py-2.5 font-medium">#</th>
                  <th className="px-4 py-2.5 font-medium">Time</th>
                  <th className="px-4 py-2.5 font-medium">User</th>
                  <th className="px-4 py-2.5 font-medium">Action</th>
                  <th className="px-4 py-2.5 font-medium">Case</th>
                  <th className="px-4 py-2.5 font-medium">Version</th>
                  <th className="px-4 py-2.5 font-medium">IP</th>
                  <th className="px-4 py-2.5 font-medium">Hash</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-paper-200">
                {data?.items.map((r) => {
                  const alert = r.action === 'access_denied' || r.action === 'login_failed'
                  return (
                    <tr key={r.id} className={alert ? 'bg-red-50/50' : 'hover:bg-paper-50'}>
                      <td className="px-4 py-2.5 font-mono text-xs text-ink-400">{r.id}</td>
                      <td className="whitespace-nowrap px-4 py-2.5 text-ink-700">
                        {new Date(r.ts).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'medium' })}
                      </td>
                      <td className="px-4 py-2.5">
                        <div className="font-medium text-ink-900">{r.username ?? '—'}</div>
                        {r.role && <div className="text-[11px] capitalize text-ink-400">{r.role}</div>}
                      </td>
                      <td className="px-4 py-2.5">
                        <Badge tone={ACTION_TONE[r.action] ?? 'neutral'} className="font-mono">
                          {r.action}
                        </Badge>
                      </td>
                      <td className="px-4 py-2.5 font-mono text-xs text-ink-700">{r.case_id ?? '—'}</td>
                      <td className="px-4 py-2.5 font-mono text-xs text-ink-700">{r.version_id ?? '—'}</td>
                      <td className="px-4 py-2.5 font-mono text-xs text-ink-500">{r.ip ?? '—'}</td>
                      <td className="px-4 py-2.5 font-mono text-[11px] text-ink-400" title={r.hash}>
                        {r.hash.slice(0, 10)}…
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
        <div className="flex items-center justify-between border-t border-paper-200 px-4 py-3 text-sm">
          <span className="text-ink-500">
            {data?.total ?? 0} entries · page {page} of {pages}
          </span>
          <div className="flex gap-1.5">
            <Button size="sm" variant="secondary" onClick={() => setPage(page - 1)} disabled={page <= 1} icon={<ChevronLeft className="size-3.5" />}>
              Previous
            </Button>
            <Button size="sm" variant="secondary" onClick={() => setPage(page + 1)} disabled={page >= pages}>
              Next
              <ChevronRight className="size-3.5" />
            </Button>
          </div>
        </div>
      </Card>
    </div>
  )
}
