import { Scan } from 'lucide-react'

// the product mark: corner brackets and the TRΛCE wordmark (an A without a crossbar, as on the splash)
export default function TraceMark({ size = 'md' }: { size?: 'md' | 'lg' }) {
  const big = size === 'lg'
  return (
    <span className="flex items-center gap-2.5" aria-label="TRACE">
      <span className={`grid place-items-center rounded-full bg-ink text-white ${big ? 'size-9' : 'size-7'}`} aria-hidden>
        <Scan size={big ? 18 : 14} />
      </span>
      <span aria-hidden className={`font-light tracking-[0.32em] text-ink ${big ? 'text-[26px]' : 'text-[17px]'}`}>
        TRΛCE
      </span>
    </span>
  )
}
