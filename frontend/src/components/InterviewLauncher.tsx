import { useMutation, useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { listInterviews, startInterview } from '../api'

export default function InterviewLauncher({ caseId }: { caseId: number }) {
  const navigate = useNavigate()
  const { data: interviews } = useQuery({ queryKey: ['interviews', caseId], queryFn: () => listInterviews(caseId) })
  const start = useMutation({
    mutationFn: () => startInterview(caseId),
    onSuccess: (iv) => navigate(`/cases/${caseId}/interviews/${iv.id}`),
  })
  const draft = interviews?.find((iv) => iv.status === 'draft')

  return (
    <div className="flex items-center gap-4 rounded-lg bg-white p-4 shadow">
      <div>
        <h2 className="font-semibold">Witness interview</h2>
        <p className="text-sm text-slate-500">
          Guided, non-leading questions. The witness's own words are kept exactly as given.
        </p>
      </div>
      <div className="ml-auto flex items-center gap-2">
        {draft && (
          <button
            onClick={() => navigate(`/cases/${caseId}/interviews/${draft.id}`)}
            className="rounded border border-slate-900 px-4 py-2 text-sm"
          >
            Continue interview #{draft.id}
          </button>
        )}
        <button
          onClick={() => start.mutate()}
          disabled={start.isPending}
          className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50"
        >
          {draft ? 'Start a new interview' : 'Start witness interview'}
        </button>
      </div>
      {start.isError && <p className="text-sm text-red-600">{start.error.message}</p>}
    </div>
  )
}
