import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { createCase, listCases } from '../api'

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

  function submit(e: FormEvent) {
    e.preventDefault()
    mutation.mutate()
  }

  return (
    <div className="fixed inset-0 flex items-center justify-center bg-black/40">
      <form onSubmit={submit} className="w-96 space-y-4 rounded-lg bg-white p-6 shadow">
        <h2 className="text-lg font-semibold">New case</h2>
        <label className="block text-sm">
          Title
          <input
            autoFocus
            value={title}
            maxLength={200}
            onChange={(e) => setTitle(e.target.value)}
            className="mt-1 w-full rounded border px-3 py-2"
          />
        </label>
        {mutation.isError && <p className="text-sm text-red-600">{mutation.error.message}</p>}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="rounded px-3 py-2 hover:bg-slate-100">
            Cancel
          </button>
          <button
            type="submit"
            disabled={!title.trim() || mutation.isPending}
            className="rounded bg-slate-900 px-3 py-2 text-white disabled:opacity-50"
          >
            Create
          </button>
        </div>
      </form>
    </div>
  )
}

export default function CasesPage() {
  const [creating, setCreating] = useState(false)
  const { data: cases, isPending, error } = useQuery({ queryKey: ['cases'], queryFn: listCases })

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-4 flex items-center">
        <h1 className="text-2xl font-semibold">Cases</h1>
        <button onClick={() => setCreating(true)} className="ml-auto rounded bg-slate-900 px-4 py-2 text-white">
          New case
        </button>
      </div>
      {error && <p className="text-red-600">{error.message}</p>}
      {isPending ? (
        <p className="text-slate-500">Loading…</p>
      ) : cases && cases.length === 0 ? (
        <p className="text-slate-500">No cases yet.</p>
      ) : (
        <table className="w-full overflow-hidden rounded-lg bg-white text-left shadow">
          <thead className="bg-slate-50 text-sm text-slate-600">
            <tr>
              <th className="px-4 py-2">Case number</th>
              <th className="px-4 py-2">Title</th>
              <th className="px-4 py-2">Created</th>
              <th className="px-4 py-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {cases?.map((c) => (
              <tr key={c.id} className="border-t hover:bg-slate-50">
                <td className="px-4 py-2 font-mono text-sm">
                  <Link to={`/cases/${c.id}`} className="text-blue-700 hover:underline">
                    {c.case_number}
                  </Link>
                </td>
                <td className="px-4 py-2">{c.title}</td>
                <td className="px-4 py-2 text-sm">{new Date(c.created_at).toLocaleString()}</td>
                <td className="px-4 py-2 text-sm">{c.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {creating && <NewCaseDialog onClose={() => setCreating(false)} />}
    </div>
  )
}
