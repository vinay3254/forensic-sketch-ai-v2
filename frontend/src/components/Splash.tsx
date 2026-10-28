import { useEffect, useState } from 'react'

// TRACE intro: brackets draw in, face fragments drop into a mosaic one by one (the blue eye
// last), then the wordmark. Once per browser session; any click or key skips it.
const SEEN = 'trace.splash.seen'
const TILE_START = 0.55 // s
const TILE_STEP = 0.32
const TOTAL = 4.9

// left/top/width/height inside a 300×460 frame, in drop-in order
const TILES: { src: string; box: [number, number, number, number]; blue?: boolean }[] = [
  { src: 'forehead', box: [158, 0, 132, 72] },
  { src: 'brow-eye', box: [36, 46, 122, 104] },
  { src: 'eyebrow', box: [158, 72, 132, 78] },
  { src: 'eye-corner', box: [36, 150, 122, 112] },
  { src: 'nose-lips', box: [36, 262, 122, 150] },
  { src: 'texture', box: [158, 262, 132, 120] },
  { src: 'texture', box: [158, 382, 132, 70] },
  { src: 'blue-eye', box: [158, 150, 132, 112], blue: true },
]

function shouldShow() {
  try {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return false
    return sessionStorage.getItem(SEEN) !== '1'
  } catch {
    return true
  }
}

export default function Splash() {
  const [phase, setPhase] = useState<'on' | 'leaving' | 'off'>(() => (shouldShow() ? 'on' : 'off'))

  useEffect(() => {
    if (phase !== 'on') return
    try {
      sessionStorage.setItem(SEEN, '1')
    } catch {
      /* private mode: it may show again next time */
    }
    const leave = () => setPhase((p) => (p === 'on' ? 'leaving' : p))
    const t = setTimeout(leave, TOTAL * 1000)
    window.addEventListener('keydown', leave)
    return () => {
      clearTimeout(t)
      window.removeEventListener('keydown', leave)
    }
  }, [phase])

  useEffect(() => {
    if (phase !== 'leaving') return
    const t = setTimeout(() => setPhase('off'), 550)
    return () => clearTimeout(t)
  }, [phase])

  if (phase === 'off') return null
  const wordAt = TILE_START + TILES.length * TILE_STEP + 0.3

  return (
    <div
      role="presentation"
      onClick={() => setPhase('leaving')}
      className={`fixed inset-0 z-[100] flex cursor-pointer flex-col items-center justify-center gap-[6vmin] bg-[#0d0d0c] transition-opacity duration-500 ${
        phase === 'leaving' ? 'opacity-0' : 'opacity-100'
      }`}
    >
      <div className="relative h-[460px] w-[300px]" style={{ transform: 'scale(min(1, calc(62vmin / 460px)))' }}>
        {/* corner brackets */}
        {[
          'left-[-24px] top-[-34px] border-l-[5px] border-t-[5px]',
          'right-[-24px] top-[-34px] border-r-[5px] border-t-[5px]',
          'left-[-24px] bottom-[-34px] border-b-[5px] border-l-[5px]',
          'right-[-24px] bottom-[-34px] border-b-[5px] border-r-[5px]',
        ].map((pos, i) => (
          <span
            key={pos}
            className={`trace-bracket absolute size-[56px] border-[#ece6da] ${pos}`}
            style={{ animationDelay: `${i * 0.06}s` }}
          />
        ))}
        {TILES.map((t, i) => (
          <div
            key={i}
            className={`trace-tile absolute overflow-hidden bg-cover bg-center ${t.blue ? 'trace-blue' : ''}`}
            style={{
              left: t.box[0],
              top: t.box[1],
              width: t.box[2],
              height: t.box[3],
              backgroundImage: `url(/splash/${t.src}.jpg)`,
              animationDelay: `${TILE_START + i * TILE_STEP}s`,
            }}
          />
        ))}
        {/* the empty square cut out of the mosaic */}
        <div className="trace-tile absolute bg-[#0d0d0c]" style={{ left: 228, top: 300, width: 40, height: 40, animationDelay: `${wordAt - 0.2}s` }} />
      </div>
      <div aria-label="TRACE" className="flex items-end gap-[3.2vmin] text-[clamp(40px,9vmin,96px)] font-light leading-none text-[#ece6da]">
        {/* the poster's A has no crossbar, just a dot under the apex */}
        {['T', 'R', 'Λ', 'C', 'E'].map((ch, i) => (
          <span key={i} aria-hidden className="trace-letter relative" style={{ animationDelay: `${wordAt + i * 0.09}s` }}>
            {ch}
            {ch === 'Λ' && <span className="absolute bottom-[0.2em] left-1/2 size-[0.09em] -translate-x-1/2 rounded-full bg-[#8a857b]" />}
          </span>
        ))}
      </div>
    </div>
  )
}
