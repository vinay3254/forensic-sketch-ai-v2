import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { lazy, Suspense, useState } from 'react'
import { health, listHeads, makeHead } from '../api'
import type { Version } from '../types'
import type { ViewerApi } from './HeadViewer'

// three.js is large; load it only when a head is shown
const HeadViewer = lazy(() => import('./HeadViewer'))

const PRESETS: [string, number][] = [
  ['Left profile', -90],
  ['Left ¾', -45],
  ['Front', 0],
  ['Right ¾', 45],
  ['Right profile', 90],
]

interface Props {
  caseId: number
  version: Version
}

export default function HeadPanel({ caseId, version }: Props) {
  const queryClient = useQueryClient()
  const status = useQuery({ queryKey: ['health'], queryFn: health, staleTime: 60_000 })
  const heads = useQuery({ queryKey: ['heads', caseId], queryFn: () => listHeads(caseId), enabled: status.data?.head3d === 'on' })
  const [viewer, setViewer] = useState<ViewerApi | null>(null)
  const make = useMutation({
    mutationFn: () => makeHead(caseId, version.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['heads', caseId] })
      queryClient.invalidateQueries({ queryKey: ['case', caseId] }) // the realistic photo may be new
    },
  })

  if (status.data?.head3d !== 'on') return null
  const head = heads.data?.[0]

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-baseline gap-2">
        <h2 className="font-semibold">3D head</h2>
        <span className="text-sm text-slate-500">
          Approximate: a front sketch has no depth, so side views are the model's guess. Use them to check what the witness saw from the side.
        </span>
        <button
          onClick={() => make.mutate()}
          disabled={make.isPending}
          className="ml-auto rounded bg-slate-900 px-3 py-1 text-sm text-white disabled:opacity-50"
        >
          {make.isPending ? 'Making photo and 3D head… (about 1½ min)' : `Make 3D head from v${version.version_no}`}
        </button>
      </div>
      {make.isError && <p className="rounded bg-red-50 p-2 text-sm text-red-700">{make.error.message}</p>}
      {head && (
        <div className="flex flex-wrap items-start gap-4">
          <Suspense fallback={<div className="aspect-[3/4] w-full max-w-sm rounded border bg-slate-50" />}>
            <HeadViewer key={head.id} meshUrl={head.mesh_url} onReady={setViewer} />
          </Suspense>
          <div className="space-y-2">
            <p className="text-sm text-slate-600">From v{head.version_no}. Drag to turn the head.</p>
            <div className="flex flex-wrap gap-2">
              {PRESETS.map(([label, yaw]) => (
                <button key={label} onClick={() => viewer?.setYaw(yaw)} disabled={!viewer} className="rounded border border-slate-300 px-2 py-1 text-sm hover:bg-slate-50 disabled:opacity-50">
                  {label}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
