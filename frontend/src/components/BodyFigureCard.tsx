import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { drawBody, getBody } from '../api'
import { Link } from 'react-router-dom'

export function useBody(caseId: number) {
  return useQuery({ queryKey: ['body', caseId], queryFn: () => getBody(caseId) })
}

export default function BodyFigureCard({ caseId, unsaved }: { caseId: number; unsaved: boolean }) {
  const queryClient = useQueryClient()
  const body = useBody(caseId)
  const draw = useMutation({
    mutationFn: () => drawBody(caseId),
    onSuccess: (b) => queryClient.setQueryData(['body', caseId], b),
  })

  return (
    <div className="flex flex-col gap-3 rounded-[14px] bg-tint px-3.5 py-3">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[13px] font-medium">Full-body figure</span>
        <button
          onClick={() => draw.mutate()}
          disabled={draw.isPending || unsaved}
          title={unsaved ? 'Wait for the details to save' : 'Drawn from build, clothing and the latest sketch'}
          className="rounded-[10px] border border-[#dcdcd7] bg-white px-3.5 py-2 text-[13px] hover:border-ink disabled:opacity-50"
        >
          {draw.isPending ? 'Drawing… (about a minute)' : body.data ? 'Redraw' : 'Draw figure'}
        </button>
      </div>
      {draw.isError && <p className="rounded-lg bg-red-50 p-2 text-[13px] text-red-700">{draw.error.message}</p>}
      {body.data && <img src={body.data.image_url} alt="Full-body figure" className="max-h-72 self-center rounded-lg object-contain mix-blend-multiply" />}
      {body.data && <Link to={`/cases/${caseId}/figure`} className="self-end text-[13px] font-medium text-accent underline underline-offset-4">Build 3D from this image →</Link>}
    </div>
  )
}
