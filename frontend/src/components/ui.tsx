import { AlertTriangle, LoaderCircle, RotateCw, X } from 'lucide-react'
import type { ButtonHTMLAttributes, ReactNode } from 'react'

type Variant = 'primary' | 'secondary' | 'ghost' | 'accent' | 'danger'

const VARIANTS: Record<Variant, string> = {
  primary: 'bg-ink-900 text-white hover:bg-ink-800 shadow-sm',
  secondary: 'bg-white text-ink-900 ring-1 ring-inset ring-paper-300 hover:bg-paper-50 hover:ring-ink-300 shadow-sm',
  ghost: 'text-ink-500 hover:bg-paper-200/70 hover:text-ink-900',
  accent: 'bg-brass-500 text-white hover:bg-brass-600 shadow-sm',
  danger: 'bg-red-600 text-white hover:bg-red-700 shadow-sm',
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: 'sm' | 'md'
  loading?: boolean
  icon?: ReactNode
}

export function Button({ variant = 'primary', size = 'md', loading, icon, className = '', children, disabled, ...rest }: ButtonProps) {
  const sizing = size === 'sm' ? 'h-8 px-3 text-xs gap-1.5' : 'h-10 px-4 text-sm gap-2'
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center rounded-lg font-medium transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brass-500 disabled:cursor-not-allowed disabled:opacity-50 ${sizing} ${VARIANTS[variant]} ${className}`}
    >
      {loading ? <LoaderCircle className="size-4 animate-spin" /> : icon}
      {children}
    </button>
  )
}

export const buttonClass = (variant: Variant = 'primary') =>
  `inline-flex h-10 items-center justify-center gap-2 rounded-lg px-4 text-sm font-medium transition ${VARIANTS[variant]}`

export function Card({ className = '', children }: { className?: string; children: ReactNode }) {
  return <div className={`rounded-2xl bg-white shadow-card ring-1 ring-paper-200 ${className}`}>{children}</div>
}

export function CardHeader({ title, icon, action }: { title: string; icon?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex items-center gap-2 border-b border-paper-200 px-5 py-3.5">
      {icon && <span className="text-ink-400">{icon}</span>}
      <h2 className="text-sm font-semibold tracking-tight text-ink-900">{title}</h2>
      {action && <div className="ml-auto">{action}</div>}
    </div>
  )
}

const TONES = {
  neutral: 'bg-paper-200/70 text-ink-700 ring-paper-300',
  green: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  red: 'bg-red-50 text-red-700 ring-red-200',
  amber: 'bg-amber-50 text-amber-800 ring-amber-200',
  blue: 'bg-sky-50 text-sky-700 ring-sky-200',
  violet: 'bg-violet-50 text-violet-700 ring-violet-200',
  ink: 'bg-ink-900 text-white ring-ink-900',
}
export type Tone = keyof typeof TONES

export function Badge({ tone = 'neutral', children, className = '' }: { tone?: Tone; children: ReactNode; className?: string }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${TONES[tone]} ${className}`}>
      {children}
    </span>
  )
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-16 text-sm text-ink-500">
      <LoaderCircle className="size-4 animate-spin" />
      {label ?? 'Loading…'}
    </div>
  )
}

export function ErrorBanner({ message, onRetry, onDismiss, busy }: { message: string; onRetry?: () => void; onDismiss?: () => void; busy?: boolean }) {
  return (
    <div className="flex items-center gap-3 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800 ring-1 ring-inset ring-red-200">
      <AlertTriangle className="size-4 shrink-0 text-red-500" />
      <span className="flex-1">{message}</span>
      {onRetry && (
        <Button size="sm" variant="danger" onClick={onRetry} loading={busy} icon={<RotateCw className="size-3.5" />}>
          Try again
        </Button>
      )}
      {onDismiss && (
        <button onClick={onDismiss} className="rounded p-1 text-red-400 hover:bg-red-100 hover:text-red-700" aria-label="Dismiss">
          <X className="size-4" />
        </button>
      )}
    </div>
  )
}

export function EmptyState({ icon, title, body, action }: { icon: ReactNode; title: string; body: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center px-6 py-16 text-center">
      <div className="mb-4 flex size-12 items-center justify-center rounded-2xl bg-paper-100 text-ink-400 ring-1 ring-paper-200">{icon}</div>
      <h3 className="text-sm font-semibold text-ink-900">{title}</h3>
      <p className="mt-1 max-w-sm text-sm text-ink-500">{body}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

export function PageHeader({ eyebrow, title, subtitle, actions }: { eyebrow?: ReactNode; title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end gap-4">
      <div className="min-w-0">
        {eyebrow && <div className="mb-1.5 text-xs font-medium text-ink-500">{eyebrow}</div>}
        <h1 className="truncate text-2xl font-semibold tracking-tight text-ink-950">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-ink-500">{subtitle}</p>}
      </div>
      {actions && <div className="ml-auto flex items-center gap-2">{actions}</div>}
    </div>
  )
}

export const inputClass =
  'w-full rounded-lg bg-white px-3 py-2 text-sm text-ink-900 ring-1 ring-inset ring-paper-300 placeholder:text-ink-400 transition focus:outline-none focus:ring-2 focus:ring-brass-500 disabled:bg-paper-50 disabled:text-ink-400'

export function Field({ label, hint, children }: { label: string; hint?: ReactNode; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 flex items-center justify-between text-xs font-medium text-ink-700">
        {label}
        {hint && <span className="font-normal text-ink-400">{hint}</span>}
      </span>
      {children}
    </label>
  )
}

export function Logo({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden>
      <rect width="32" height="32" rx="8" fill="currentColor" className="text-brass-500" />
      <path d="M16 7c-4 0-7 3.2-7 7.6 0 3 1.2 5.4 3 7l.6 3.4h6.8l.6-3.4c1.8-1.6 3-4 3-7C23 10.2 20 7 16 7Z" fill="none" stroke="#fff" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M13 15.5h1.6M17.4 15.5H19M14.5 20.2c1 .6 2 .6 3 0" stroke="#fff" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  )
}

export const initials = (name: string) => name.slice(0, 2).toUpperCase()

export function relativeTime(iso: string) {
  const s = (Date.now() - new Date(iso).getTime()) / 1000
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)} min ago`
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`
  return new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}
