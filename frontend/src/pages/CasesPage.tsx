import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowRight, FolderOpen, FolderPlus, Plus, Search } from 'lucide-react'
import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { createCase, listCases } from '../api'
import { Badge, Button, Card, EmptyState, ErrorBanner, Field, inputClass, PageHeader, relativeTime, Spinner } from '../components/ui'

function NewCaseDialog({ onClose }: { onClose: () => void }) {
  const [title, setTitle] = useState('')
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const mutation = useMutation({
    mutationFn: () => createCase(title.trim()),
    onSuccess: (c) => {
      queryClient.invalidateQueries({ queryKey: ['cases'] })
      navigate(`/cases/${c.id}`)
    },
  })

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  function submit(e: FormEvent) {
    e.preventDefault()
    mutation.mutate()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink-950/40 p-4 backdrop-blur-sm" onClick={onClose}>
      <form onSubmit={submit} onClick={(e) => e.stopPropagation()} className="w-full max-w-md rounded-2xl bg-white p-6 shadow-lift ring-1 ring-paper-200">
        <div className="mb-5 flex items-start gap-3">
          <div className="flex size-10 items-center justify-center rounded-xl bg-brass-500/10 text-brass-600">
            <FolderPlus className="size-5" />
          </div>
          <div>
            <h2 className="font-semibold tracking-tight">Open a new case</h2>
            <p className="text-sm text-ink-500">A case number is assigned automatically.</p>
          </div>
        </div>
        <Field label="Case title" hint={`${title.length}/200`}>
          <input
            autoFocus
            value={title}
            maxLength={200}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Chain snatching, Yelahanka"
            className={`${inputClass} h-10`}
          />
        </Field>
        {mutation.isError && (
          <div className="mt-4">
            <ErrorBanner message={mutation.error.message} />
          </div>
        )}
        <div className="mt-6 flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={!title.trim()} loading={mutation.isPending}>
            Create case
          </Button>
        </div>
      </form>
    </div>
  )
}

export default function CasesPage() {
  const [creating, setCreating] = useState(false)
  const [query, setQuery] = useState('')
  const navigate = useNavigate()
  const { data: cases, isPending, error } = useQuery({ queryKey: ['cases'], queryFn: listCases })

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase()
    return (cases ?? []).filter((c) => !q || c.title.toLowerCase().includes(q) || c.case_number.toLowerCase().includes(q))
  }, [cases, query])

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        title="Cases"
        subtitle={cases ? `${cases.length} case${cases.length === 1 ? '' : 's'} on file` : 'Your active investigations'}
        actions={
          <Button onClick={() => setCreating(true)} icon={<Plus className="size-4" />}>
            New case
          </Button>
        }
      />
      {error && <ErrorBanner message={error.message} />}
      <Card className="overflow-hidden">
        <div className="flex items-center gap-3 border-b border-paper-200 px-4 py-3">
          <div className="relative w-full max-w-xs">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-400" />
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search by title or number" className={`${inputClass} h-9 pl-9`} />
          </div>
        </div>
        {isPending ? (
          <Spinner />
        ) : cases && cases.length === 0 ? (
          <EmptyState
            icon={<FolderOpen className="size-5" />}
            title="No cases yet"
            body="Open a case to start building a sketch from a witness description."
            action={
              <Button onClick={() => setCreating(true)} icon={<Plus className="size-4" />}>
                New case
              </Button>
            }
          />
        ) : shown.length === 0 ? (
          <EmptyState icon={<Search className="size-5" />} title="No matches" body={`Nothing matches “${query}”.`} />
        ) : (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="text-[11px] uppercase tracking-wider text-ink-400">
                <th className="px-5 py-2.5 font-medium">Case</th>
                <th className="px-5 py-2.5 font-medium">Title</th>
                <th className="px-5 py-2.5 font-medium">Opened</th>
                <th className="px-5 py-2.5 font-medium">Status</th>
                <th className="w-10" />
              </tr>
            </thead>
            <tbody className="divide-y divide-paper-200">
              {shown.map((c) => (
                <tr key={c.id} onClick={() => navigate(`/cases/${c.id}`)} className="group cursor-pointer transition hover:bg-paper-50">
                  <td className="px-5 py-3.5">
                    <span className="rounded-md bg-paper-100 px-2 py-1 font-mono text-xs text-ink-700 ring-1 ring-paper-200">{c.case_number}</span>
                  </td>
                  <td className="px-5 py-3.5 font-medium text-ink-900">{c.title}</td>
                  <td className="px-5 py-3.5 text-ink-500" title={new Date(c.created_at).toLocaleString()}>
                    {relativeTime(c.created_at)}
                  </td>
                  <td className="px-5 py-3.5">
                    <Badge tone={c.status === 'open' ? 'green' : 'neutral'}>
                      <span className="size-1.5 rounded-full bg-current" />
                      {c.status}
                    </Badge>
                  </td>
                  <td className="pr-4 text-ink-300 transition group-hover:translate-x-0.5 group-hover:text-ink-700">
                    <ArrowRight className="size-4" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
      {creating && <NewCaseDialog onClose={() => setCreating(false)} />}
    </div>
  )
}
