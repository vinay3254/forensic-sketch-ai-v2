import { keepPreviousData, useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { auditList, auditVerify } from '../api'
import { AUDIT_ACTIONS, type AuditFilters } from '../types'

const PAGE_SIZE = 50

// datetime-local gives local wall time with no zone; send it as an absolute instant
const toIso = (local: string) => (local ? new Date(local).toISOString() : undefined)

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
  const { data, isPending, error } = useQuery({
    queryKey: ['audit', filters],
    queryFn: () => auditList(filters),
    placeholderData: keepPreviousData,
  })
  const verify = useMutation({ mutationFn: auditVerify })
  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1

  function filterSetter(set: (v: string) => void) {
    return (v: string) => {
      set(v)
      setPage(1)
    }
  }

  return (
    <div className="mx-auto max-w-7xl space-y-4">
      <div className="flex items-center gap-4">
        <h1 className="text-2xl font-semibold">Audit log</h1>
        <div className="ml-auto flex items-center gap-3">
          {verify.data &&
            (verify.data.ok ? (
              <span className="rounded bg-green-100 px-3 py-1 text-sm text-green-800">Chain intact ({verify.data.rows} rows)</span>
            ) : (
              <span className="rounded bg-red-100 px-3 py-1 text-sm text-red-800">
                Tampering detected at row #{verify.data.first_bad_id}
              </span>
            ))}
          {verify.isError && <span className="text-sm text-red-600">{verify.error.message}</span>}
          <button
            onClick={() => verify.mutate()}
            disabled={verify.isPending}
            className="rounded bg-slate-900 px-4 py-2 text-white disabled:opacity-50"
          >
            Verify integrity
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-3 rounded-lg bg-white p-4 text-sm shadow">
        <label className="flex flex-col gap-1">
          Action
          <select value={action} onChange={(e) => filterSetter(setAction)(e.target.value)} className="rounded border px-2 py-1.5">
            <option value="">All</option>
            {AUDIT_ACTIONS.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          Case ID
          <input
            type="number"
            min={1}
            value={caseId}
            onChange={(e) => filterSetter(setCaseId)(e.target.value)}
            className="w-24 rounded border px-2 py-1.5"
          />
        </label>
        <label className="flex flex-col gap-1">
          Since
          <input type="datetime-local" value={since} onChange={(e) => filterSetter(setSince)(e.target.value)} className="rounded border px-2 py-1.5" />
        </label>
        <label className="flex flex-col gap-1">
          Until
          <input type="datetime-local" value={until} onChange={(e) => filterSetter(setUntil)(e.target.value)} className="rounded border px-2 py-1.5" />
        </label>
      </div>

      {error && <p className="text-red-600">{error.message}</p>}
      {isPending ? (
        <p className="text-slate-500">Loading…</p>
      ) : (
        <table className="w-full overflow-hidden rounded-lg bg-white text-left text-sm shadow">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="px-3 py-2">#</th>
              <th className="px-3 py-2">Time</th>
              <th className="px-3 py-2">User</th>
              <th className="px-3 py-2">Role</th>
              <th className="px-3 py-2">Action</th>
              <th className="px-3 py-2">Case</th>
              <th className="px-3 py-2">Version</th>
              <th className="px-3 py-2">IP</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((r) => (
              <tr key={r.id} className={`border-t ${r.action === 'access_denied' || r.action === 'login_failed' ? 'bg-red-50' : ''}`}>
                <td className="px-3 py-1.5 text-slate-500">{r.id}</td>
                <td className="px-3 py-1.5">{new Date(r.ts).toLocaleString()}</td>
                <td className="px-3 py-1.5">{r.username ?? '—'}</td>
                <td className="px-3 py-1.5">{r.role ?? '—'}</td>
                <td className="px-3 py-1.5 font-mono">{r.action}</td>
                <td className="px-3 py-1.5">{r.case_id ?? '—'}</td>
                <td className="px-3 py-1.5">{r.version_id ?? '—'}</td>
                <td className="px-3 py-1.5 font-mono">{r.ip ?? '—'}</td>
              </tr>
            ))}
            {data?.items.length === 0 && (
              <tr>
                <td colSpan={8} className="px-3 py-4 text-center text-slate-500">
                  No matching rows.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      )}

      <div className="flex items-center justify-end gap-3 text-sm">
        <span className="text-slate-600">
          {data?.total ?? 0} rows · page {page} of {pages}
        </span>
        <button onClick={() => setPage(page - 1)} disabled={page <= 1} className="rounded border px-3 py-1 disabled:opacity-40">
          Previous
        </button>
        <button onClick={() => setPage(page + 1)} disabled={page >= pages} className="rounded border px-3 py-1 disabled:opacity-40">
          Next
        </button>
      </div>
    </div>
  )
}
