import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { listVariants, makeVariant } from '../api'
import { VARIANT_KINDS, type Version, type VariantKind } from '../types'

interface Props {
  caseId: number
  version: Version
}

export default function VariantsPanel({ caseId, version }: Props) {
  const queryClient = useQueryClient()
  const variants = useQuery({ queryKey: ['variants', caseId], queryFn: () => listVariants(caseId) })
  const [picked, setPicked] = useState<VariantKind[]>([])
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null)

  // one image edit per variant, made in turn so each shows up as soon as it is ready
  const make = useMutation({
    mutationFn: async (kinds: VariantKind[]) => {
      for (const [i, kind] of kinds.entries()) {
        setProgress({ done: i, total: kinds.length })
        await makeVariant(caseId, version.id, kind)
        await queryClient.invalidateQueries({ queryKey: ['variants', caseId] })
      }
    },
    onSettled: () => setProgress(null),
    onSuccess: () => setPicked([]),
  })

  const toggle = (kind: VariantKind) => setPicked((p) => (p.includes(kind) ? p.filter((k) => k !== kind) : [...p, kind]))
  // numbered oldest first, the way they are printed on the case sheet
  const shown = [...(variants.data ?? [])].reverse()

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-baseline gap-2">
        <h2 className="font-semibold">Disguise variants</h2>
        <span className="text-sm text-slate-500">The same face as v{version.version_no} with a cap, glasses, a beard and so on.</span>
      </div>
      <div className="flex flex-wrap gap-2">
        {VARIANT_KINDS.map(([kind, label]) => (
          <label key={kind} className="flex items-center gap-1.5 rounded border border-slate-300 px-2 py-1 text-sm">
            <input type="checkbox" checked={picked.includes(kind)} onChange={() => toggle(kind)} disabled={make.isPending} />
            {label}
          </label>
        ))}
        <button
          onClick={() => make.mutate(picked)}
          disabled={make.isPending || picked.length === 0}
          className="rounded bg-slate-900 px-3 py-1 text-sm text-white disabled:opacity-50"
        >
          {progress ? `Making ${progress.done + 1} of ${progress.total}…` : `Make selected (${picked.length})`}
        </button>
      </div>
      {make.isPending && <p className="text-xs text-slate-500">Each variant takes about a minute.</p>}
      {make.isError && <p className="rounded bg-red-50 p-2 text-sm text-red-700">{make.error.message}</p>}
      {shown.length > 0 && (
        <div className="flex gap-3 overflow-x-auto pb-2">
          {shown.map((x, i) => (
            <a key={x.id} href={x.image_url} target="_blank" rel="noreferrer" className="flex shrink-0 flex-col items-center gap-1">
              <img src={x.image_url} alt={x.label} className="h-32 w-[5.4rem] rounded border object-cover" />
              <span className="text-xs text-slate-600">
                {i + 1}. {x.label} · v{x.version_no}
              </span>
            </a>
          ))}
        </div>
      )}
    </div>
  )
}
