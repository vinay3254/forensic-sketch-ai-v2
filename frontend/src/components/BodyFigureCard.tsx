import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { drawBody, getBody } from '../api'

interface Props {
  caseId: number
  height?: string
  unsaved: boolean
}

export default function BodyFigureCard({ caseId, height, unsaved }: Props) {
  const queryClient = useQueryClient()
  const body = useQuery({ queryKey: ['body', caseId], queryFn: () => getBody(caseId) })
  const draw = useMutation({
    mutationFn: () => drawBody(caseId),
    onSuccess: (b) => queryClient.setQueryData(['body', caseId], b),
  })

  return (
    <div className="rounded border border-slate-200 p-3">
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-medium">Full-body figure</h3>
        <button
          onClick={() => draw.mutate()}
          disabled={draw.isPending || unsaved}
          title={unsaved ? 'Save the details first' : 'Drawn from build, clothing and the latest sketch'}
          className="ml-auto rounded border border-slate-300 px-3 py-1 text-sm hover:bg-slate-50 disabled:opacity-50"
        >
          {draw.isPending ? 'Drawing… (about a minute)' : body.data ? 'Redraw' : 'Draw figure'}
        </button>
      </div>
      {draw.isError && <p className="mt-2 rounded bg-red-50 p-2 text-sm text-red-700">{draw.error.message}</p>}
      {body.data && (
        <div className="mt-2 flex items-stretch gap-2">
          <img src={body.data.image_url} alt="Full-body figure" className="h-72 rounded border object-contain" />
          {height && (
            <div className="flex flex-col items-center justify-between py-1 text-xs text-slate-600">
              <span className="h-2 w-4 border-t-2 border-slate-500" />
              <span className="flex-1 border-l-2 border-slate-500" />
              <span className="max-w-24 py-1 text-center">{height}</span>
              <span className="flex-1 border-l-2 border-slate-500" />
              <span className="h-2 w-4 border-b-2 border-slate-500" />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
