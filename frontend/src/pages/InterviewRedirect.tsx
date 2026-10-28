import { useMutation, useQuery } from '@tanstack/react-query'
import { MessagesSquare } from 'lucide-react'
import { Navigate, useNavigate, useParams } from 'react-router-dom'
import { listInterviews, startInterview } from '../api'

// /cases/:id/interview: the draft in progress, else the latest interview, else offer to start one
export default function InterviewRedirect() {
  const caseId = Number(useParams().id)
  const navigate = useNavigate()
  const { data, isPending, error } = useQuery({ queryKey: ['interviews', caseId], queryFn: () => listInterviews(caseId) })
  const start = useMutation({
    mutationFn: () => startInterview(caseId),
    onSuccess: (iv) => navigate(`/cases/${caseId}/interviews/${iv.id}`, { replace: true }),
  })
  if (isPending) return <p className="p-4 text-muted">Loading…</p>
  if (error) return <p className="rounded-2xl bg-red-50 p-4 text-red-700">{error.message}</p>
  const iv = data.find((i) => i.status === 'draft') ?? data[0]
  if (iv) return <Navigate to={`/cases/${caseId}/interviews/${iv.id}`} replace />
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center">
      <span className="grid size-12 place-items-center rounded-2xl bg-white/80 text-ink">
        <MessagesSquare />
      </span>
      <h2 className="text-[20px] font-semibold">No witness interview yet</h2>
      <p className="max-w-sm text-[13px] text-muted">Guided, neutral questions; the witness's own words are kept exactly as given.</p>
      <button onClick={() => start.mutate()} disabled={start.isPending} className="mt-2 rounded-full bg-ink px-5 py-2.5 text-[13px] font-medium text-white disabled:opacity-50">
        Start witness interview
      </button>
      {start.isError && <p className="text-[13px] text-red-600">{start.error.message}</p>}
    </div>
  )
}
