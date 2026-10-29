import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import {
  ApiError,
  adjustProportions,
  generate,
  getCase,
  listInterviews,
  makePhoto,
  refine,
  revert,
  startInterview,
} from '../api'
import AttributePanel from '../components/AttributePanel'
import DescriptionForm from '../components/DescriptionForm'
import FaceCanvas, { type View } from '../components/FaceCanvas'
import HeadPanel from '../components/HeadPanel'
import PageHeader, { btnDark, btnLight } from '../components/PageHeader'
import MatchPanel from '../components/MatchPanel'
import ProportionPanel from '../components/ProportionPanel'
import RefineChat from '../components/RefineChat'
import type { Proportions, Version } from '../types'

type Action =
  | { kind: 'generate'; text: string; lang?: string }
  | { kind: 'refine'; text: string }
  | { kind: 'revert'; versionId: number }
  | { kind: 'photo'; versionId: number }
  | { kind: 'adjust'; versionId: number; adj: Proportions }

const RETRYABLE = new Set(['AI_REFUSED', 'AI_UNAVAILABLE'])

function InterviewButtons({ caseId }: { caseId: number }) {
  const navigate = useNavigate()
  const { data: interviews } = useQuery({
    queryKey: ['interviews', caseId],
    queryFn: () => listInterviews(caseId),
  })
  const start = useMutation({
    mutationFn: () => startInterview(caseId),
    onSuccess: (iv) => navigate(`/cases/${caseId}/interviews/${iv.id}`),
  })
  const draft = interviews?.find((iv) => iv.status === 'draft')
  return (
    <>
      {draft && (
        <button
          onClick={() => navigate(`/cases/${caseId}/interviews/${draft.id}`)}
          className={btnLight}
        >
          Continue interview #{draft.id}
        </button>
      )}
      <button
        onClick={() => start.mutate()}
        disabled={start.isPending}
        className={btnDark}
      >
        {draft ? 'New interview' : 'Start witness interview'}
      </button>
    </>
  )
}

export default function WorkspacePage() {
  const caseId = Number(useParams().id)
  const location = useLocation()
  const queryClient = useQueryClient()
  const [selectedId, setSelectedId] = useState<number>()
  const [startingOver, setStartingOver] = useState(false)
  const [view, setView] = useState<View>('sketch')
  const [panel, setPanel] = useState<'attributes' | 'proportions' | 'matches'>('attributes')
  const [preview, setPreview] = useState<string | null>(null)
  const onPreview = useCallback((url: string | null) => setPreview(url), [])
  const { data, isPending, error } = useQuery({
    queryKey: ['case', caseId],
    queryFn: () => getCase(caseId),
  })

  const mutation = useMutation({
    mutationFn: async (action: Action) => {
      if (action.kind === 'generate') return generate(caseId, action.text, action.lang)
      if (action.kind === 'refine')
        return (await refine(caseId, action.text)).version
      if (action.kind === 'photo') return makePhoto(caseId, action.versionId)
      if (action.kind === 'adjust') return adjustProportions(caseId, action.versionId, action.adj)
      return revert(caseId, action.versionId)
    },
    onSuccess: (version, action) => {
      if (version) {
        setSelectedId(version.id)
        setStartingOver(false)
        setView(action.kind === 'photo' ? 'photo' : 'sketch')
      }
      queryClient.invalidateQueries({ queryKey: ['cases'] })
      return queryClient.invalidateQueries({ queryKey: ['case', caseId] })
    },
  })

  if (isPending) return <p className="p-4 text-muted">Loading…</p>
  if (error) {
    const msg =
      error instanceof ApiError && error.code === 'FORBIDDEN'
        ? 'You do not have access to this case.'
        : error.message
    return <p className="rounded-2xl bg-red-50 p-4 text-red-700">{msg}</p>
  }

  const { case: c, versions, chat } = data
  const busy = mutation.isPending
  const latest = versions.at(-1)
  const selected = versions.find((v) => v.id === selectedId) ?? latest
  const showForm = !latest || startingOver
  const err = mutation.error instanceof ApiError ? mutation.error : null

  return (
    <>
      <PageHeader
        crumbs={[
          { label: 'Cases', to: '/cases' },
          { label: c.case_number, mono: true },
          { label: 'Workspace' },
        ]}
        title={c.title}
        actions={<InterviewButtons caseId={caseId} />}
      />
      {mutation.error && (
        <div className="flex shrink-0 items-center gap-3 rounded-2xl bg-red-50 px-4 py-3 text-[13px] text-red-700">
          <span>{mutation.error.message}</span>
          {err && RETRYABLE.has(err.code) && (
            <button
              onClick={() => mutation.mutate(mutation.variables!)}
              disabled={busy}
              className="ml-auto rounded-full bg-red-600 px-3 py-1 text-white disabled:opacity-50"
            >
              Try again
            </button>
          )}
        </div>
      )}
      <div className="grid min-h-0 flex-1 grid-cols-1 items-stretch gap-3 overflow-y-auto lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)_minmax(0,1fr)] lg:overflow-hidden">
        <section className="flex min-h-[28rem] flex-col overflow-hidden rounded-[22px] bg-white p-5 lg:min-h-0">
          {showForm ? (
            <DescriptionForm
              initialText={
                typeof location.state?.description === 'string'
                  ? location.state.description
                  : ''
              }
              busy={busy}
              replacing={!!latest}
              onSubmit={(text, lang) => mutation.mutate({ kind: 'generate', text, lang })}
              onCancel={latest ? () => setStartingOver(false) : undefined}
            />
          ) : (
            <RefineChat
              chat={chat}
              busy={busy}
              onSend={(text) => mutation.mutate({ kind: 'refine', text })}
              onStartOver={() => setStartingOver(true)}
            />
          )}
        </section>
        <section className="flex min-h-[32rem] min-w-0 flex-col overflow-hidden rounded-[22px] bg-cream p-4 lg:min-h-0">
          <FaceCanvas
            versions={versions}
            version={selected}
            view={view}
            busy={busy}
            previewSrc={panel === 'proportions' && view === 'sketch' ? preview : null}
            onView={setView}
            onSelect={(id) => {
              setSelectedId(id)
              setView('sketch')
            }}
            onRevert={(versionId) =>
              mutation.mutate({ kind: 'revert', versionId })
            }
            onNew={() => setStartingOver(true)}
          />
        </section>
        <section className="flex min-h-[28rem] flex-col overflow-hidden rounded-[22px] bg-white p-5 lg:min-h-0">
          {selected && (
            <div className="mb-3 flex shrink-0 rounded-full bg-field p-0.5 text-xs">
              {(['attributes', 'proportions', 'matches'] as const).map((p) => (
                <button
                  key={p}
                  onClick={() => {
                    setPanel(p)
                    if (p === 'proportions') setView('sketch')
                  }}
                  className={`flex-1 rounded-full px-3 py-1.5 ${panel === p ? 'bg-ink text-white' : 'text-muted hover:text-ink'}`}
                >
                  {p === 'attributes' ? 'Attributes' : p === 'proportions' ? 'Proportions' : 'Matches'}
                </button>
              ))}
            </div>
          )}
          <div className="min-h-0 flex-1">
          {selected && panel === 'matches' ? (
            <MatchPanel caseId={caseId} version={selected} busy={busy} onMakePhoto={() => mutation.mutate({ kind: 'photo', versionId: selected.id })} />
          ) : selected && panel === 'proportions' ? (
            <ProportionPanel
              caseId={caseId}
              version={selected}
              busy={busy}
              onPreview={onPreview}
              onSave={(adj) => mutation.mutate({ kind: 'adjust', versionId: selected.id, adj })}
            />
          ) : (
            <AttributePanel
              caseId={caseId}
              version={selected}
              busy={busy}
              onMakePhoto={() =>
                selected &&
                mutation.mutate({ kind: 'photo', versionId: selected.id })
              }
            />
          )}
          </div>
        </section>
      </div>
      {selected && <HeadSection caseId={caseId} version={selected} />}
    </>
  )
}

// the panel hides itself when the 3D service is off, so the card around it must too
function HeadSection(props: { caseId: number; version: Version }) {
  return (
    <section className="shrink-0 rounded-[22px] bg-white p-4 empty:hidden">
      <HeadPanel {...props} />
    </section>
  )
}
