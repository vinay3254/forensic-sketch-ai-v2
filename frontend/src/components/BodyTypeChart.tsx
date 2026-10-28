import { useQuery } from '@tanstack/react-query'
import { listBodyTypes } from '../api'

interface Props {
  build?: string
  onPick: (label: string) => void
}

// reference figures the witness can point at; picking one fills the build field
export default function BodyTypeChart({ build, onPick }: Props) {
  const types = useQuery({ queryKey: ['body-types'], queryFn: listBodyTypes, staleTime: Infinity })
  if (!types.data?.length) return null
  return (
    <div>
      <p className="text-xs text-slate-500">Build reference: click the figure the witness points to.</p>
      <div className="mt-1 flex gap-1">
        {types.data.map((t) => {
          const on = build?.trim().toLowerCase() === t.label.toLowerCase()
          return (
            <button
              key={t.key}
              onClick={() => onPick(t.label)}
              className={`flex flex-1 flex-col items-center rounded border-2 p-1 text-xs ${on ? 'border-blue-600 bg-blue-50' : 'border-transparent hover:bg-slate-50'}`}
            >
              <img src={t.image_url} alt={t.label} className="h-28 object-contain" />
              {t.label}
            </button>
          )
        })}
      </div>
    </div>
  )
}
