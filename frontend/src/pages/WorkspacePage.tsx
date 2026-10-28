import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { ApiError, generate, getCase, makePhoto, refine, revert } from '../api'
import AttributePanel from '../components/AttributePanel'
import DescriptionForm from '../components/DescriptionForm'
import DetailsPanel from '../components/DetailsPanel'
import FaceCanvas, { type View } from '../components/FaceCanvas'
import InterviewLauncher from '../components/InterviewLauncher'
import RefineChat from '../components/RefineChat'
import VariantsPanel from '../components/VariantsPanel'
import VersionStrip from '../components/VersionStrip'

type Action =
  | { kind: 'generate'; text: string }
  | { kind: 'refine'; text: string }
  | { kind: 'revert'; versionId: number }
  | { kind: 'photo'; versionId: number }

const RETRYABLE = new Set(['AI_REFUSED', 'AI_UNAVAILABLE'])

export default function WorkspacePage() {
  const caseId = Number(useParams().id)
  const queryClient = useQueryClient()
  const [selectedId, setSelectedId] = useState<number>()
  const [startingOver, setStartingOver] = useState(false)
  const [view, setView] = useState<View>('sketch')
  const { data, isPending, error } = useQuery({ queryKey: ['case', caseId], queryFn: () => getCase(caseId) })

  const mutation = useMutation({
    mutationFn: async (action: Action) => {
      if (action.kind === 'generate') return generate(caseId, action.text)
      if (action.kind === 'refine') return (await refine(caseId, action.text)).version
      if (action.kind === 'photo') return makePhoto(caseId, action.versionId)
      return revert(caseId, action.versionId)
    },
    onSuccess: (version, action) => {
      if (version) {
        setSelectedId(version.id)
        setStartingOver(false)
        setView(action.kind === 'photo' ? 'photo' : 'sketch')
      }
      return queryClient.invalidateQueries({ queryKey: ['case', caseId] })
    },
  })

  if (isPending) return <p className="text-slate-500">Loading…</p>
  if (error) {
    const msg = error instanceof ApiError && error.code === 'FORBIDDEN' ? 'You do not have access to this case.' : error.message
    return <p className="rounded bg-red-50 p-4 text-red-700">{msg}</p>
  }

  const { case: c, versions, chat } = data
  const busy = mutation.isPending
  const latest = versions.at(-1)
  const selected = versions.find((v) => v.id === selectedId) ?? latest
  const showForm = !latest || startingOver
  const err = mutation.error instanceof ApiError ? mutation.error : null

  return (
    <div className="mx-auto max-w-7xl space-y-4">
      <div>
        <p className="font-mono text-sm text-slate-500">{c.case_number}</p>
        <h1 className="text-2xl font-semibold">{c.title}</h1>
      </div>
      {mutation.error && (
        <div className="flex items-center gap-3 rounded bg-red-50 p-3 text-sm text-red-700">
          <span>{mutation.error.message}</span>
          {err && RETRYABLE.has(err.code) && (
            <button
              onClick={() => mutation.mutate(mutation.variables!)}
              disabled={busy}
              className="ml-auto rounded bg-red-600 px-3 py-1 text-white disabled:opacity-50"
            >
              Try again
            </button>
          )}
        </div>
      )}
      <InterviewLauncher caseId={caseId} />
      <div className="grid gap-6 lg:grid-cols-[22rem_1fr_18rem]">
        <section className="h-[36rem] rounded-lg bg-white p-4 shadow">
          {showForm ? (
            <DescriptionForm
              busy={busy}
              replacing={!!latest}
              onSubmit={(text) => mutation.mutate({ kind: 'generate', text })}
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
        <section className="flex flex-col items-center gap-4">
          <FaceCanvas version={selected} view={view} busy={busy} onView={setView} />
        </section>
        <section className="rounded-lg bg-white p-4 shadow">
          <AttributePanel
            caseId={caseId}
            version={selected}
            busy={busy}
            onMakePhoto={() => selected && mutation.mutate({ kind: 'photo', versionId: selected.id })}
          />
        </section>
      </div>
      {versions.length > 0 && (
        <section className="rounded-lg bg-white p-4 shadow">
          <VersionStrip
            versions={versions}
            selectedId={selected?.id}
            busy={busy}
            onSelect={(id) => {
              setSelectedId(id)
              setView('sketch')
            }}
            onRevert={(versionId) => mutation.mutate({ kind: 'revert', versionId })}
          />
        </section>
      )}
      <section className="rounded-lg bg-white p-4 shadow">
        <DetailsPanel caseId={caseId} details={c.details} />
      </section>
      {selected && (
        <section className="rounded-lg bg-white p-4 shadow">
          <VariantsPanel caseId={caseId} version={selected} />
        </section>
      )}
    </div>
  )
}
