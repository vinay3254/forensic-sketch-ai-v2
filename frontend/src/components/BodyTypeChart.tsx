import { useQuery } from '@tanstack/react-query'
import { listBodyTypes } from '../api'

interface Props {
  build?: string
  onPick: (label: string) => void
  compact?: boolean // one row of five, as printed on the case sheet
}

export const isBuild = (build: string | undefined, label: string) => build?.trim().toLowerCase() === label.toLowerCase()

// reference figures the witness can point at; picking one fills the build field
export default function BodyTypeChart({ build, onPick, compact }: Props) {
  const types = useQuery({ queryKey: ['body-types'], queryFn: listBodyTypes, staleTime: Infinity })
  if (!types.data?.length) return null
  return (
    <div className={compact ? 'grid grid-cols-5 gap-1.5 rounded-xl bg-field p-2' : 'grid grid-cols-3 gap-2'}>
      {types.data.map((t) => (
        <button
          key={t.key}
          onClick={() => onPick(t.label)}
          className={`flex flex-col items-center gap-1.5 rounded-[14px] border-[1.5px] bg-field px-1 py-2.5 ${compact ? 'text-[11px]' : 'text-xs'} ${
            isBuild(build, t.label) ? 'border-accent text-ink' : 'border-transparent text-body hover:border-line'
          }`}
        >
          <img src={t.image_url} alt={t.label} className={`${compact ? 'h-[70px]' : 'h-[87px]'} object-contain mix-blend-multiply`} />
          {t.label}
        </button>
      ))}
    </div>
  )
}
