import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Download, ExternalLink } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { bodyModelMesh, buildRealisticBody, kaggleJob, startKaggle3d, getBlenderJob, getBody, getBodyModel, openBodyModel, reconstructBody, startBlenderJob } from '../api'
import FigureViewer from './FigureViewer'
import PageHeader, { btnDark, btnLight } from './PageHeader'

const ACTIVE = new Set(['queued', 'drafting', 'building', 'opening'])
const PHASES = {
  queued: 'Queued for Blender', drafting: 'LLM is writing the Blender model…',
  building: 'Blender is building geometry…', opening: 'Loading model into desktop Blender…',
  complete: 'Model saved', failed: 'Build failed',
}
const KAGGLE_STAGES: Record<string, string> = {
  queued: 'Starting…',
  views: 'Step 1 of 5 · Drawing the side and back views…',
  upload: 'Step 2 of 5 · Sending the drawings to your private Kaggle dataset…',
  kaggle: 'Step 3 of 5 · Kaggle GPU is building the 3D shape (usually 5–8 min)…',
  download: 'Step 4 of 5 · Downloading the 3D shape…',
  paint: 'Step 5 of 5 · Painting it with the drawings in Blender…',
  saving: 'Saving the model…',
}
const DEFAULT_PROMPT = 'Model this person as editable 3D geometry. Include face, hair or beard, clothing, fingers, and shoes.'

export default function ReconstructedFigure() {
  const caseId = Number(useParams().id)
  const queryClient = useQueryClient()
  // one way to build the 3D model: Kaggle 3D (the other engines stay in the backend, not offered here)
  const [method] = useState<'kaggle' | 'realistic' | 'blender' | 'image'>('kaggle')
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
  // Kaggle 3D runs in the background; poll it while it runs and pick up the model when it is done
  const kJob = useQuery({
    queryKey: ['kaggle-job', caseId],
    queryFn: () => kaggleJob(caseId),
    refetchInterval: (q) => (q.state.data && (q.state.data.status === 'queued' || q.state.data.status === 'running') ? 3000 : false),
  })
  const kRunning = !!kJob.data && (kJob.data.status === 'queued' || kJob.data.status === 'running')
  useEffect(() => {
    if (kJob.data?.status === 'done') queryClient.invalidateQueries({ queryKey: ['body-model', caseId] })
  }, [kJob.data?.id, kJob.data?.status, queryClient, caseId])
  const kStart = useMutation({
    mutationFn: (id: number) => startKaggle3d(caseId, id),
    onSuccess: (job) => queryClient.setQueryData(['kaggle-job', caseId], job),
  })
  const kPhase = kRunning ? KAGGLE_STAGES[kJob.data!.stage ?? 'queued'] : null
  const realistic = useMutation({
    mutationFn: (id: number) => buildRealisticBody(caseId, id),
    onSuccess: (result) => queryClient.setQueryData(['body-model', caseId], result),
  })
  const start = useMutation({
    mutationFn: () => startBlenderJob(caseId, source.data!.id, prompt.trim() || DEFAULT_PROMPT),
    onSuccess: (result) => queryClient.setQueryData(['blender-job', caseId], result),
  })
  const busy = running || start.isPending || build.isPending || realistic.isPending || kRunning || kStart.isPending
  const error = kStart.error ?? realistic.error ?? start.error ?? build.error ?? mesh.error ?? saved.error ?? source.error ?? job.error
  const phase = kPhase ?? (running && job.data ? PHASES[job.data.status] : null)
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
              <p className="text-[15px] font-medium">{phase || (realistic.isPending ? 'Drawing side and back views, then building the body in Blender… 1–2 minutes' : build.isPending ? 'Reconstructing your full-body image…' : model ? 'Loading saved 3D model…' : 'Build a 3D model from your full-body image')}</p>
              <p className="max-w-sm text-[13px] text-muted">{busy ? 'Your reference and previous models stay saved while the new model builds.' : 'Choose Blender AI to generate modeled geometry from your reference and instructions.'}</p>
            </div>}
          {model && mesh.data && <span className="pointer-events-none absolute left-4 top-3 text-[12px] text-muted">Drag to rotate · Scroll to zoom</span>}
          {busy && model && <p role="status" className="absolute inset-x-4 bottom-4 rounded-xl bg-white/90 p-3 text-[13px]">{phase || (realistic.isPending ? 'Drawing side and back views, then building the body… 1–2 minutes.' : 'Building new model…')} Previous model stays available.</p>}
        </section>
        <section className="flex flex-col gap-4 overflow-y-auto rounded-[22px] bg-white p-5">
          <div>
            <h2 className="text-[15px] font-medium">Full-body reference</h2>
            <p className="mt-1 text-[13px] text-muted">Use the generated person’s face, clothes, and proportions as the reconstruction source.</p>
          </div>
          {source.data ? <>
            <img src={source.data.image_url} alt="Full-body reference used for the next model" className="max-h-56 self-center rounded-xl object-contain" />
            {method === 'blender' && <label className="flex flex-col gap-2 text-[13px]">
              Describe your model
              <textarea rows={3} maxLength={2000} value={prompt} onChange={(event) => setPrompt(event.target.value)} disabled={busy}
                placeholder="E.g. model the face, give him a wider nose, add a hoodie with pockets…"
                className="resize-y rounded-xl border border-line bg-field p-3 text-[13px]" />
            </label>}
            <button className={btnDark} disabled={busy || saved.isPending || job.isPending} onClick={() => method === 'kaggle' ? kStart.mutate(source.data!.id) : method === 'realistic' ? realistic.mutate(source.data!.id) : method === 'blender' ? start.mutate() : build.mutate(source.data!.id)}>
              {busy ? phase || 'Building…' : method === 'kaggle' ? (model ? 'Rebuild 3D model' : 'Build 3D model') : method === 'realistic' ? 'Build realistic body' : method === 'blender' ? 'Build with Blender AI' : 'Rebuild from this image'}
            </button>
            {method === 'kaggle' && <p className="text-[12px] text-muted">Builds a 3D model of this person from the full-body image (front, side and back drawings, shaped on a Kaggle GPU). Takes about 10 minutes and keeps going if you leave this page.</p>}
            {kJob.data?.status === 'failed' && <p role="alert" className="rounded-xl bg-red-50 p-3 text-[13px] text-red-700">Kaggle 3D failed: {kJob.data.error}</p>}
            {method === 'realistic' && <p className="text-[12px] text-muted">A realistic human (MakeHuman) posed like the picture, stretched to its proportions and fitted to its outline. The image model draws the same person from the side and back, and every surface is textured from the view that faces it. Takes 1–2 minutes. Long dresses and tunics are fitted as body shape, not cloth.</p>}
            {method === 'blender' && <p className="text-[12px] text-muted">LLM writes Blender Python to model geometry. Builds can take a few minutes. Results may be stylized.</p>}
          </> : source.isPending ? <p>Loading reference…</p> : <Link to={`/cases/${caseId}/details`} className={btnLight}>Draw a full-body image in Details first</Link>}
          {model && <div className="rounded-xl bg-tint p-3 text-[13px] text-body">
            <p>Saved model · {model.engine} · {Math.round(model.height_cm)} cm</p>
            <a href={model.source_url} target="_blank" rel="noreferrer" className="mt-1 inline-block underline underline-offset-4">View model’s original reference</a>
            {source.data && source.data.id !== model.body_id && <p className="mt-2">A newer full-body image is available. Rebuild to use it.</p>}
          </div>}
          <p className="text-[12px] leading-relaxed text-muted">{model?.engine.startsWith('Hunyuan3D') ? `${model.summary ? model.summary[0].toUpperCase() + model.summary.slice(1) + '. ' : ''}Shape from Hunyuan3D-2 on a Kaggle GPU; painted with the front, side and back drawings.` : model?.engine.startsWith('Realistic body') ? `${model.summary ? model.summary[0].toUpperCase() + model.summary.slice(1) + '. ' : ''}Side and back come from drawn views of the same person, so small details there are the image model's estimate; clothes follow the body's shape.` : model?.engine === 'LLM Blender modeling' ? 'This model uses generated geometry and materials. It has no projected reference texture. Facial likeness is approximate.' : 'Image reconstruction projects your reference onto front surfaces. Geometry and unseen surfaces are estimates; facial shape and side views may differ.'}</p>
          {error && <p role="alert" className="rounded-xl bg-red-50 p-3 text-[13px] text-red-700">{error.message}</p>}
          <div aria-live="polite">
            {send.isError && <p className="rounded-xl bg-red-50 p-3 text-[13px] text-red-700">Model stays saved. {send.error.message}</p>}
            {send.isSuccess && !send.isPending && <p className="rounded-xl bg-tint p-3 text-[13px]">Model loaded in connected Blender window.</p>}
          </div>
        </section>
      </div>
    </>
  )
}
