import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Download, Save } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { ApiError, figureBlendUrl, figureModel, getFigure, promptFigure, putFigure, saveFigure } from '../api'
import Composer from '../components/Composer'
import FigureViewer from '../components/FigureViewer'
import ReconstructedFigure from '../components/ReconstructedFigure'
import PageHeader, { btnDark, btnLight } from '../components/PageHeader'
import type { FigureParams } from '../types'

const SLIDERS: { key: 'height_cm' | 'build' | 'muscle' | 'gender' | 'age'; label: string; min: number; max: number; step: number; show: (v: number) => string }[] = [
  { key: 'height_cm', label: 'Height', min: 120, max: 220, step: 1, show: (v) => `${Math.round(v)} cm` },
  { key: 'build', label: 'Build', min: 0, max: 1, step: 0.01, show: (v) => ['Slim', 'Average', 'Overweight', 'Heavy', 'Obese'][Math.min(4, Math.floor(v * 5))] },
  { key: 'muscle', label: 'Muscle', min: 0, max: 1, step: 0.01, show: (v) => `${Math.round(v * 100)}%` },
  { key: 'gender', label: 'Body shape', min: 0, max: 1, step: 0.01, show: (v) => (v < 0.34 ? 'Male' : v > 0.66 ? 'Female' : 'In between') },
  { key: 'age', label: 'Age', min: 10, max: 100, step: 1, show: (v) => `${Math.round(v)}` },
]
const CHOICES = {
  top: ['none', 'tshirt', 'shirt', 'hoodie', 'jacket', 'kurta'],
  bottom: ['none', 'trousers', 'jeans', 'shorts', 'skirt'],
  headwear: ['none', 'cap'],
} as const
const nice = (v: string) => (v === 'tshirt' ? 'T-shirt' : v === 'none' ? 'None' : v[0].toUpperCase() + v.slice(1))

// a Blender mannequin the officer shapes by typing or with sliders; it redraws as they go
export default function FigurePage() {
  const [mode, setMode] = useState<'image' | 'mannequin'>('image')
  return <>
    <div className="mb-3 flex gap-2" aria-label="Figure mode">
      <button className={mode === 'image' ? btnDark : btnLight} aria-pressed={mode === 'image'} onClick={() => setMode('image')}>From image</button>
      <button className={mode === 'mannequin' ? btnDark : btnLight} aria-pressed={mode === 'mannequin'} onClick={() => setMode('mannequin')}>Mannequin editor</button>
    </div>
    {mode === 'image' ? <ReconstructedFigure /> : <MannequinFigure />}
  </>
}

function MannequinFigure() {
  const caseId = Number(useParams().id)
  const queryClient = useQueryClient()
  const state = useQuery({ queryKey: ['figure', caseId], queryFn: () => getFigure(caseId) })
  const [params, setParams] = useState<FigureParams | null>(null)
  const [glb, setGlb] = useState<ArrayBuffer | null>(null)
  const [error, setError] = useState<ApiError | Error | null>(null)
  const [reply, setReply] = useState<string | null>(null)
  const [building, setBuilding] = useState(false)
  const latest = useRef(0)

  useEffect(() => {
    if (state.data && !params) setParams(state.data.params)
  }, [state.data, params])

  // rebuild in Blender whenever the settings change; only the newest answer is shown
  const paramsJson = JSON.stringify(params)
  useEffect(() => {
    if (!params) return
    const ticket = ++latest.current
    setBuilding(true)
    const t = setTimeout(() => {
      figureModel(caseId, params)
        .then((buf) => ticket === latest.current && (setGlb(buf), setError(null)))
        .catch((e) => ticket === latest.current && setError(e))
        .finally(() => ticket === latest.current && setBuilding(false))
    }, 60)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paramsJson, caseId])

  // keep the case's saved settings in step with the sliders
  const dirty = useRef(false)
  useEffect(() => {
    if (!params || !dirty.current) return
    const t = setTimeout(() => {
      dirty.current = false
      putFigure(caseId, params).catch(setError)
    }, 700)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paramsJson])

  const ask = useMutation({
    mutationFn: (text: string) => promptFigure(caseId, text),
    onSuccess: (s) => {
      setParams(s.params)
      setReply(s.reply)
      queryClient.setQueryData(['figure', caseId], s)
    },
  })
  const save = useMutation({
    mutationFn: () => saveFigure(caseId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['body', caseId] }),
  })

  const set = <K extends keyof FigureParams>(key: K, value: FigureParams[K]) => {
    dirty.current = true
    setParams((p) => (p ? { ...p, [key]: value } : p))
  }

  if (state.isPending || !params) return <p className="p-4 text-muted">Loading…</p>
  if (state.error) return <p className="rounded-2xl bg-red-50 p-4 text-red-700">{state.error.message}</p>
  const off = error instanceof ApiError && error.code === 'FIGURE_OFF'

  return (
    <>
      <PageHeader
        title="Figure"
        actions={
          <>
            <a href={figureBlendUrl(caseId)} download className={`${btnLight} flex items-center gap-1.5`}>
              <Download size={14} /> Download .blend
            </a>
            <button onClick={() => save.mutate()} disabled={save.isPending || off} className={`${btnDark} flex items-center gap-1.5`}>
              <Save size={14} /> {save.isPending ? 'Rendering… (~5 s)' : save.isSuccess ? 'Saved to case sheet' : 'Save to case sheet'}
            </button>
          </>
        }
      />
      <div className="grid min-h-0 flex-1 gap-3 lg:grid-cols-[minmax(0,1.2fr)_minmax(320px,1fr)]">
        <section className="relative min-h-[28rem] overflow-hidden rounded-[22px] bg-cream">
          {off ? (
            <div className="flex h-full flex-col items-center justify-center gap-2 p-6 text-center text-[13px] text-muted">
              <p className="text-[15px] font-medium text-ink">The Blender worker isn't running</p>
              <p>Start it with</p>
              <code className="rounded-lg bg-white px-3 py-2 font-mono text-[12px] text-ink">cd blender_worker && uv run uvicorn server:app --port 8020</code>
              <p>and set FIGURE_URL=http://127.0.0.1:8020 in .env, then restart the backend.</p>
            </div>
          ) : (
            <>
              <FigureViewer glb={glb} heightCm={params.height_cm} />
              <span className="pointer-events-none absolute left-4 top-3 text-[12px] text-muted">
                {building ? 'Blender is building…' : 'Drag to turn the figure'}
              </span>
            </>
          )}
          {error && !off && <p className="absolute inset-x-3 bottom-3 rounded-xl bg-red-50 px-3 py-2 text-[13px] text-red-700">{error.message}</p>}
        </section>

        <section className="flex min-h-0 flex-col gap-4 overflow-y-auto rounded-[22px] bg-white p-5">
          <Composer
            rows={2}
            busy={ask.isPending}
            placeholder="Describe a change… e.g. “heavier, about 185 cm, in a jacket and jeans”"
            onSubmit={(t) => ask.mutate(t)}
          />
          {(reply || ask.isError) && (
            <p className={`rounded-xl px-3 py-2 text-[13px] ${ask.isError ? 'bg-red-50 text-red-700' : 'bg-tint text-body'}`}>
              {ask.isError ? ask.error.message : reply}
            </p>
          )}
          <div className="flex flex-col gap-3">
            {SLIDERS.map((s) => (
              <label key={s.key} className="grid grid-cols-[90px_1fr_76px] items-center gap-3 text-[13px]">
                <span className="text-body">{s.label}</span>
                <input
                  type="range"
                  min={s.min}
                  max={s.max}
                  step={s.step}
                  value={params[s.key]}
                  onChange={(e) => set(s.key, Number(e.target.value))}
                  className="accent-accent"
                />
                <span className="text-right font-mono text-[12px] text-ink">{s.show(params[s.key])}</span>
              </label>
            ))}
          </div>
          {(Object.keys(CHOICES) as (keyof typeof CHOICES)[]).map((k) => (
            <div key={k} className="flex flex-col gap-1.5">
              <span className="text-[11px] uppercase tracking-[0.08em] text-muted">{k === 'top' ? 'Top' : k === 'bottom' ? 'Bottom' : 'Headwear'}</span>
              <div className="flex flex-wrap gap-1.5">
                {CHOICES[k].map((v) => (
                  <button
                    key={v}
                    onClick={() => set(k, v as never)}
                    className={`rounded-full border px-3 py-1 text-[12px] ${params[k] === v ? 'border-ink bg-ink text-white' : 'border-line bg-field text-body hover:border-ink'}`}
                  >
                    {nice(v)}
                  </button>
                ))}
              </div>
            </div>
          ))}
          {save.isError && <p className="rounded-xl bg-red-50 px-3 py-2 text-[13px] text-red-700">{save.error.message}</p>}
        </section>
      </div>
    </>
  )
}
