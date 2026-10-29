// Small SVG charts for the admin dashboard. Colours: validated categorical slots (dataviz palette check on the
// paper surface: all pass; aqua is under 3:1, so every chart here also has a legend, hover values and a table).
import { useLayoutEffect, useRef, useState, type ReactNode } from 'react'

export const SERIES = ['#2a78d6', '#eb6834', '#1baf7a', '#6250d6'] as const
const GRID = '#ebe6da'
const AXIS = '#958f83'

export function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const [w, setW] = useState(600)
  useLayoutEffect(() => {
    if (!ref.current) return
    const ro = new ResizeObserver(([e]) => setW(Math.max(200, e.contentRect.width)))
    ro.observe(ref.current)
    return () => ro.disconnect()
  }, [])
  return [ref, w] as const
}

function niceMax(v: number) {
  if (v <= 4) return 4
  const p = 10 ** Math.floor(Math.log10(v))
  return Math.ceil(v / (p / 2)) * (p / 2)
}

export function Legend({ items }: { items: { label: string; color: string; note?: ReactNode }[] }) {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-body">
      {items.map((i) => (
        <span key={i.label} className="inline-flex items-center gap-1.5">
          <span className="size-2.5 rounded-[3px]" style={{ background: i.color }} />
          {i.label}
          {i.note}
        </span>
      ))}
    </div>
  )
}

export function Tip({ x, y, w, children }: { x: number; y: number; w: number; children: ReactNode }) {
  const left = Math.min(Math.max(x + 12, 0), w - 190)
  return (
    <div
      className="pointer-events-none absolute z-10 w-[180px] rounded-xl border border-line bg-white px-3 py-2 text-xs shadow-[0_8px_24px_-12px_rgba(0,0,0,0.3)]"
      style={{ left, top: Math.max(y - 10, 0) }}
    >
      {children}
    </div>
  )
}

const short = (iso: string) => new Date(iso + 'T00:00:00').toLocaleDateString([], { day: 'numeric', month: 'short' })

// one bar per day, stacked by kind of work; 2px paper gaps between segments, rounded top
export function StackedDays({
  days,
  keys,
  labels,
  height = 220,
}: {
  days: { date: string; values: Record<string, number> }[]
  keys: string[]
  labels: Record<string, string>
  height?: number
}) {
  const [ref, w] = useWidth<HTMLDivElement>()
  const [hover, setHover] = useState<number | null>(null)
  const pad = { l: 34, r: 8, t: 8, b: 26 }
  const totals = days.map((d) => keys.reduce((s, k) => s + (d.values[k] ?? 0), 0))
  const max = niceMax(Math.max(...totals, 1))
  const iw = w - pad.l - pad.r
  const ih = height - pad.t - pad.b
  const slot = iw / days.length
  const bw = Math.max(4, Math.min(28, slot * 0.6))
  const y = (v: number) => pad.t + ih - (v / max) * ih
  const ticks = [0, max / 2, max]
  const step = Math.ceil(days.length / Math.max(1, Math.floor(iw / 56)))
  return (
    <div ref={ref} className="relative w-full min-w-0">
      <svg width="100%" height={height} viewBox={`0 0 ${w} ${height}`} className="block" role="img" aria-label="Activity per day by kind of work">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={pad.l} x2={w - pad.r} y1={y(t)} y2={y(t)} stroke={GRID} />
            <text x={pad.l - 6} y={y(t) + 4} textAnchor="end" fontSize="10" fill={AXIS}>
              {t}
            </text>
          </g>
        ))}
        {days.map((d, i) => {
          let acc = 0
          const cx = pad.l + slot * i + slot / 2
          const segs = keys
            .map((k, j) => ({ k, j, v: d.values[k] ?? 0 }))
            .filter((s) => s.v > 0)
          return (
            <g key={d.date} opacity={hover === null || hover === i ? 1 : 0.45}>
              {segs.map((s, n) => {
                const y0 = y(acc)
                acc += s.v
                const y1 = y(acc)
                const top = n === segs.length - 1
                const hgt = Math.max(1, y0 - y1 - (n > 0 ? 2 : 0))
                return (
                  <rect key={s.k} x={cx - bw / 2} y={y1} width={bw} height={hgt} rx={top ? 4 : 0} fill={SERIES[s.j]}>
                    {top && null}
                  </rect>
                )
              })}
              {i % step === 0 && (
                <text x={cx} y={height - 8} textAnchor="middle" fontSize="10" fill={AXIS}>
                  {short(d.date)}
                </text>
              )}
              <rect x={pad.l + slot * i} y={pad.t} width={slot} height={ih} fill="transparent" onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)} />
            </g>
          )
        })}
      </svg>
      {hover !== null && (
        <Tip x={pad.l + slot * hover + slot / 2} y={20} w={w}>
          <p className="mb-1 font-medium text-ink">
            {short(days[hover].date)} · {totals[hover]} actions
          </p>
          {keys.map((k, j) => (
            <p key={k} className="flex items-center justify-between gap-2 text-body">
              <span className="inline-flex items-center gap-1.5">
                <span className="size-2 rounded-[2px]" style={{ background: SERIES[j] }} />
                {labels[k]}
              </span>
              <span className="font-mono text-ink">{days[hover].values[k] ?? 0}</span>
            </p>
          ))}
        </Tip>
      )}
    </div>
  )
}

// sign-ins per day as thin bars, failed sign-ins as red-pencil dots above them (status colour, with a legend icon)
export function SignIns({ days, height = 150 }: { days: { date: string; logins: number; failed: number }[]; height?: number }) {
  const [ref, w] = useWidth<HTMLDivElement>()
  const [hover, setHover] = useState<number | null>(null)
  const pad = { l: 34, r: 8, t: 10, b: 26 }
  const max = niceMax(Math.max(...days.map((d) => Math.max(d.logins, d.failed)), 1))
  const iw = w - pad.l - pad.r
  const ih = height - pad.t - pad.b
  const slot = iw / days.length
  const bw = Math.max(3, Math.min(18, slot * 0.45))
  const y = (v: number) => pad.t + ih - (v / max) * ih
  const step = Math.ceil(days.length / Math.max(1, Math.floor(iw / 56)))
  return (
    <div ref={ref} className="relative w-full min-w-0">
      <svg width="100%" height={height} viewBox={`0 0 ${w} ${height}`} className="block" role="img" aria-label="Sign-ins and failed sign-ins per day">
        {[0, max].map((t) => (
          <g key={t}>
            <line x1={pad.l} x2={w - pad.r} y1={y(t)} y2={y(t)} stroke={GRID} />
            <text x={pad.l - 6} y={y(t) + 4} textAnchor="end" fontSize="10" fill={AXIS}>
              {t}
            </text>
          </g>
        ))}
        {days.map((d, i) => {
          const cx = pad.l + slot * i + slot / 2
          return (
            <g key={d.date} opacity={hover === null || hover === i ? 1 : 0.45}>
              {d.logins > 0 && <rect x={cx - bw / 2} y={y(d.logins)} width={bw} height={y(0) - y(d.logins)} rx={3} fill="#3d3a34" />}
              {d.failed > 0 && <circle cx={cx} cy={y(d.failed)} r={4.5} fill="#b0442c" stroke="#fdfbf6" strokeWidth={2} />}
              {i % step === 0 && (
                <text x={cx} y={height - 8} textAnchor="middle" fontSize="10" fill={AXIS}>
                  {short(d.date)}
                </text>
              )}
              <rect x={pad.l + slot * i} y={pad.t} width={slot} height={ih} fill="transparent" onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)} />
            </g>
          )
        })}
      </svg>
      {hover !== null && (
        <Tip x={pad.l + slot * hover + slot / 2} y={10} w={w}>
          <p className="mb-1 font-medium text-ink">{short(days[hover].date)}</p>
          <p className="flex justify-between text-body">
            Sign-ins <span className="font-mono text-ink">{days[hover].logins}</span>
          </p>
          <p className="flex justify-between text-body">
            Failed sign-ins <span className="font-mono text-accent">{days[hover].failed}</span>
          </p>
        </Tip>
      )}
    </div>
  )
}

export function Sparkline({ values, width = 96, height = 26 }: { values: number[]; width?: number; height?: number }) {
  const max = Math.max(...values, 1)
  const pts = values.map((v, i) => [(i / Math.max(values.length - 1, 1)) * (width - 4) + 2, height - 3 - (v / max) * (height - 6)])
  const last = pts[pts.length - 1]
  return (
    <svg width={width} height={height} aria-hidden>
      <polyline points={pts.map((p) => p.join(',')).join(' ')} fill="none" stroke="#3d3a34" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
      {last && <circle cx={last[0]} cy={last[1]} r={3} fill="#3d3a34" />}
    </svg>
  )
}

// how a session ended (or that it is still open): one colour each, shared with the legend
export const SESSION_COLOR: Record<string, string> = {
  active: '#1baf7a',
  idle: '#8fd6b8',
  logout: '#2a78d6',
  new_login: '#958f83',
  expired: '#958f83',
}
export const SESSION_LABEL: Record<string, string> = {
  active: 'Active now',
  idle: 'Signed in, idle',
  logout: 'Signed out',
  new_login: 'Left without signing out',
  expired: 'Left without signing out',
}

export type TimelineSession = {
  user_id: number
  username: string
  start: string
  end: string | null
  end_reason: string
  actions: number
  cases: number
}

// one row per person, one block per session (login to logout); open sessions run to "now"
export function SessionTimeline({ sessions, people, from, onPick }: {
  sessions: TimelineSession[]
  people: { user_id: number; username: string; online: boolean }[]
  from: Date
  onPick?: (userId: number) => void
}) {
  const [ref, w] = useWidth<HTMLDivElement>()
  const [hover, setHover] = useState<{ s: TimelineSession; x: number; y: number } | null>(null)
  const now = Date.now()
  const pad = { l: 110, r: 10, t: 6, b: 24 }
  const row = 30
  const rows = people.filter((p) => sessions.some((s) => s.user_id === p.user_id))
  const height = pad.t + rows.length * row + pad.b
  const iw = w - pad.l - pad.r
  const t0 = from.getTime()
  const x = (t: number) => pad.l + ((t - t0) / (now - t0)) * iw
  const daysN = Math.round((now - t0) / 864e5)
  const tickEvery = Math.ceil(daysN / Math.max(1, Math.floor(iw / 70)))
  const ticks = Array.from({ length: Math.floor(daysN / tickEvery) + 1 }, (_, i) => new Date(t0 + i * tickEvery * 864e5))
  const fmt = (iso: string) => new Date(iso).toLocaleString([], { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
  if (rows.length === 0) return <p className="py-6 text-center text-[13px] text-muted">No sessions in this period.</p>
  return (
    <div ref={ref} className="relative w-full min-w-0">
      <svg width="100%" height={height} viewBox={`0 0 ${w} ${height}`} className="block" role="img" aria-label="Sessions per person over time">
        {ticks.map((t) => (
          <g key={t.getTime()}>
            <line x1={x(t.getTime())} x2={x(t.getTime())} y1={pad.t} y2={height - pad.b} stroke={GRID} />
            <text x={x(t.getTime())} y={height - 8} textAnchor="middle" fontSize="10" fill={AXIS}>
              {t.toLocaleDateString([], { day: 'numeric', month: 'short' })}
            </text>
          </g>
        ))}
        {rows.map((p, r) => {
          const cy = pad.t + r * row + row / 2
          return (
            <g key={p.user_id}>
              <text x={8} y={cy + 4} fontSize="12" fill="#26241f" className="cursor-pointer" onClick={() => onPick?.(p.user_id)}>
                {p.username.length > 13 ? p.username.slice(0, 12) + '…' : p.username}
              </text>
              {p.online && <circle cx={pad.l - 10} cy={cy} r={4} fill={SESSION_COLOR.active} />}
              <line x1={pad.l} x2={w - pad.r} y1={cy} y2={cy} stroke={GRID} strokeDasharray="2 4" />
              {sessions
                .filter((s) => s.user_id === p.user_id)
                .map((s) => {
                  const a = Math.max(x(new Date(s.start).getTime()), pad.l)
                  const b = Math.max(x(s.end ? new Date(s.end).getTime() : now), a + 5)
                  const color = SESSION_COLOR[s.end_reason] ?? '#958f83'
                  return (
                    <rect
                      key={s.start}
                      x={a}
                      y={cy - 8}
                      width={b - a}
                      height={16}
                      rx={4}
                      fill={color}
                      stroke="#fdfbf6"
                      strokeWidth={2}
                      className="cursor-pointer"
                      onMouseEnter={() => setHover({ s, x: (a + b) / 2, y: cy })}
                      onMouseLeave={() => setHover(null)}
                      onClick={() => onPick?.(p.user_id)}
                    />
                  )
                })}
            </g>
          )
        })}
      </svg>
      {hover && (
        <Tip x={hover.x} y={hover.y + 12} w={w}>
          <p className="font-medium text-ink">{hover.s.username}</p>
          <p className="text-body">{fmt(hover.s.start)}</p>
          <p className="text-body">→ {hover.s.end ? fmt(hover.s.end) : 'still logged in'}</p>
          <p className="mt-1 text-body">
            {hover.s.actions} actions · {hover.s.cases} cases
          </p>
          <p className="text-muted">{SESSION_LABEL[hover.s.end_reason]}</p>
        </Tip>
      )}
    </div>
  )
}

// horizontal bars, one per person, values labelled at the bar end
export function PersonBars({ items, color = '#3d3a34', unit }: { items: { label: string; value: number; onClick?: () => void }[]; color?: string; unit: string }) {
  const max = Math.max(...items.map((i) => i.value), 1)
  return (
    <div className="flex flex-col gap-2">
      {items.map((i) => (
        <button key={i.label} onClick={i.onClick} className="grid grid-cols-[110px_minmax(0,1fr)_44px] items-center gap-2 text-left text-[13px] hover:opacity-80">
          <span className="truncate text-ink">{i.label}</span>
          <span className="h-3 rounded-full bg-field">
            <span className="block h-3 rounded-full" style={{ width: `${Math.max(2, (i.value / max) * 100)}%`, background: color }} />
          </span>
          <span className="text-right font-mono text-xs text-body" title={`${i.value} ${unit}`}>
            {i.value}
          </span>
        </button>
      ))}
    </div>
  )
}
