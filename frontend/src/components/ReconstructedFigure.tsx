import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Download, ExternalLink } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { bodyModelMesh, getBlenderJob, getBody, getBodyModel, openBodyModel, reconstructBody, startBlenderJob } from '../api'
import FigureViewer from './FigureViewer'
import PageHeader, { btnDark, btnLight } from './PageHeader'

const ACTIVE = new Set(['queued', 'drafting', 'building', 'opening'])
const PHASES = {
  queued: 'Queued for Blender', drafting: 'LLM is writing the Blender model…',
  building: 'Blender is building geometry…', opening: 'Loading model into desktop Blender…',
  complete: 'Model saved', failed: 'Build failed',
}
const DEFAULT_PROMPT = 'Model this person as editable 3D geometry. Include face, hair or beard, clothing, fingers, and shoes.'

export default function ReconstructedFigure() {
  const caseId = Number(useParams().id)
  const queryClient = useQueryClient()
  const [method, setMethod] = useState<'blender' | 'image'>('blender')
  const [prompt, setPrompt] = useState('')
  const source = useQuery({ queryKey: ['body', caseId], queryFn: () => getBody(caseId) })
  const saved = useQuery({ queryKey: ['body-model', caseId], queryFn: () => getBodyModel(caseId) })
  const model = saved.data
  const job = useQuery({
    queryKey: ['blender-job', caseId], queryFn: () => getBlenderJob(caseId),
    refetchInterval: (query) => ACTIVE.has(query.state.data?.status ?? '') ? 1500 : false,
  })
  const running = ACTIVE.has(job.data?.status ?? '')
  useEffect(() => {
    if (job.data?.status === 'complete') queryClient.invalidateQueries({ queryKey: ['body-model', caseId] })
  }, [job.data?.id, job.data?.status, queryClient, caseId])
  const mesh = useQuery({
    queryKey: ['body-model-mesh', caseId, model?.id],
    queryFn: () => bodyModelMesh(model!.mesh_url),
    enabled: !!model,
    placeholderData: (previous) => previous,
  })
  const send = useMutation({ mutationFn: (id: number) => openBodyModel(caseId, id) })
  const build = useMutation({
    mutationFn: (id: number) => reconstructBody(caseId, id),
    onSuccess: (result) => {
      queryClient.setQueryData(['body-model', caseId], result)
      send.mutate(result.id)
    },
  })
  const start = useMutation({
    mutationFn: () => startBlenderJob(caseId, source.data!.id, prompt.trim() || DEFAULT_PROMPT),
    onSuccess: (result) => queryClient.setQueryData(['blender-job', caseId], result),
  })
  const busy = running || start.isPending || build.isPending
  const error = start.error ?? build.error ?? mesh.error ?? saved.error ?? source.error ?? job.error
  const phase = running && job.data ? PHASES[job.data.status] : null
  return (
    <>
      <PageHeader title="3D from image" actions={model && <>
        <a href={model.mesh_url} download={`body-model-${model.id}.glb`} className={`${btnLight} flex items-center gap-1.5`}><Download size={14} /> Download GLB</a>
        {model.blend_url && <a href={model.blend_url} download className={btnLight}>Download .blend</a>}
        <button className={`${btnDark} flex items-center gap-1.5`} onClick={() => send.mutate(model.id)} disabled={send.isPending || busy}>
          <ExternalLink size={14} /> {send.isPending ? 'Sending…' : 'Open in Blender'}
        </button>
      </>} />
      <div className="grid min-h-0 flex-1 gap-3 lg:grid-cols-[minmax(0,1.2fr)_minmax(320px,1fr)]">
        <section className="relative min-h-[32rem] overflow-hidden rounded-[22px] bg-cream">
          {model && mesh.data ? <FigureViewer glb={mesh.data} heightCm={model.height_cm} preserveMaterials /> :
            <div className="flex h-full min-h-[32rem] flex-col items-center justify-center gap-3 p-8 text-center">
              {source.data && <img src={source.data.image_url} alt="Full-body source awaiting 3D reconstruction" className="max-h-80 rounded-xl object-contain mix-blend-multiply opacity-70" />}
              <p className="text-[15px] font-medium">{phase || (build.isPending ? 'Reconstructing your full-body image…' : model ? 'Loading saved 3D model…' : 'Build a 3D model from your full-body image')}</p>
              <p className="max-w-sm text-[13px] text-muted">{busy ? 'Your reference and previous models stay saved while the new model builds.' : 'Choose Blender AI to generate modeled geometry from your reference and instructions.'}</p>
            </div>}
          {model && mesh.data && <span className="pointer-events-none absolute left-4 top-3 text-[12px] text-muted">Drag to rotate · Scroll to zoom</span>}
          {busy && model && <p role="status" className="absolute inset-x-4 bottom-4 rounded-xl bg-white/90 p-3 text-[13px]">{phase || 'Building new model…'} Previous model stays available.</p>}
        </section>
        <section className="flex flex-col gap-4 overflow-y-auto rounded-[22px] bg-white p-5">
          <div>
            <h2 className="text-[15px] font-medium">Full-body reference</h2>
            <p className="mt-1 text-[13px] text-muted">Use the generated person’s face, clothes, and proportions as the reconstruction source.</p>
          </div>
          {source.data ? <>
            <img src={source.data.image_url} alt="Full-body reference used for the next model" className="max-h-56 self-center rounded-xl object-contain" />
            <div className="flex flex-wrap gap-2" role="group" aria-label="Modeling method">
              <button className={method === 'blender' ? btnDark : btnLight} aria-pressed={method === 'blender'} onClick={() => setMethod('blender')}>Blender AI</button>
              <button className={method === 'image' ? btnDark : btnLight} aria-pressed={method === 'image'} onClick={() => setMethod('image')}>Image reconstruction</button>
            </div>
            {method === 'blender' && <label className="flex flex-col gap-2 text-[13px]">
              Describe your model
              <textarea rows={3} maxLength={2000} value={prompt} onChange={(event) => setPrompt(event.target.value)} disabled={busy}
                placeholder="E.g. model the face, give him a wider nose, add a hoodie with pockets…"
                className="resize-y rounded-xl border border-line bg-field p-3 text-[13px]" />
            </label>}
            <button className={btnDark} disabled={busy || saved.isPending || job.isPending} onClick={() => method === 'blender' ? start.mutate() : build.mutate(source.data!.id)}>
              {busy ? phase || 'Building…' : method === 'blender' ? 'Build with Blender AI' : 'Rebuild from this image'}
            </button>
            {method === 'blender' && <p className="text-[12px] text-muted">LLM writes Blender Python to model geometry. Builds can take a few minutes. Results may be stylized.</p>}
          </> : source.isPending ? <p>Loading reference…</p> : <Link to={`/cases/${caseId}/details`} className={btnLight}>Draw a full-body image in Details first</Link>}
          {model && <div className="rounded-xl bg-tint p-3 text-[13px] text-body">
            <p>Saved model · {model.engine} · {Math.round(model.height_cm)} cm</p>
            <a href={model.source_url} target="_blank" rel="noreferrer" className="mt-1 inline-block underline underline-offset-4">View model’s original reference</a>
            {source.data && source.data.id !== model.body_id && <p className="mt-2">A newer full-body image is available. Rebuild to use it.</p>}
          </div>}
          <p className="text-[12px] leading-relaxed text-muted">{model?.engine === 'LLM Blender modeling' ? 'This model uses generated geometry and materials. It has no projected reference texture. Facial likeness is approximate.' : 'Image reconstruction projects your reference onto front surfaces. Geometry and unseen surfaces are estimates; facial shape and side views may differ.'}</p>
          {error && <p role="alert" className="rounded-xl bg-red-50 p-3 text-[13px] text-red-700">{error.message}</p>}
          {job.data?.status === 'failed' && <p role="alert" className="rounded-xl bg-red-50 p-3 text-[13px] text-red-700">{job.data.error}</p>}
          <div aria-live="polite">
            {job.data?.status === 'complete' && job.data.desktop_opened && <p className="rounded-xl bg-tint p-3 text-[13px]">Blender AI model saved and opened in desktop Blender.</p>}
            {job.data?.status === 'complete' && job.data.desktop_error && <p className="rounded-xl bg-tint p-3 text-[13px]">Model saved. {job.data.desktop_error}</p>}
            {send.isError && <p className="rounded-xl bg-red-50 p-3 text-[13px] text-red-700">Model stays saved. {send.error.message}</p>}
            {send.isSuccess && !send.isPending && <p className="rounded-xl bg-tint p-3 text-[13px]">Model loaded in connected Blender window.</p>}
          </div>
        </section>
      </div>
    </>
  )
}
