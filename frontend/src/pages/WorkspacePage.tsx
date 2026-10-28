import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronRight, ShieldX } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError, generate, getCase, makePhoto, refine, revert } from '../api'
import AttributePanel from '../components/AttributePanel'
import DescriptionForm from '../components/DescriptionForm'
import FaceCanvas, { type View } from '../components/FaceCanvas'
import RefineChat from '../components/RefineChat'
import { Badge, buttonClass, Card, EmptyState, ErrorBanner, relativeTime, Spinner } from '../components/ui'
import VersionStrip from '../components/VersionStrip'

type Action =
  | { kind: 'generate'; text: string }
  | { kind: 'refine'; text: string }
  | { kind: 'revert'; versionId: number }
  | { kind: 'photo'; versionId: number }

const RETRYABLE = new Set(['AI_REFUSED', 'AI_UNAVAILABLE'])

const BUSY_LABEL: Record<Action['kind'], string> = {
  generate: 'Drawing the sketch…',
  refine: 'Applying the change…',
  revert: 'Restoring the version…',
  photo: 'Rendering a realistic photo…',
}

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

  if (isPending) return <Spinner label="Opening case…" />
  if (error) {
    const forbidden = error instanceof ApiError && error.code === 'FORBIDDEN'
    return (
      <Card className="mx-auto max-w-lg">
        <EmptyState
          icon={<ShieldX className="size-5" />}
          title={forbidden ? 'Access denied' : 'Could not open this case'}
          body={forbidden ? 'You do not have access to this case. This attempt has been recorded in the audit log.' : error.message}
          action={
            <Link to="/cases" className={buttonClass('secondary')}>
              Back to cases
            </Link>
          }
        />
      </Card>
    )
  }

  const { case: c, versions, chat } = data
  const busy = mutation.isPending
  const latest = versions.at(-1)
  const selected = versions.find((v) => v.id === selectedId) ?? latest
  const showForm = !latest || startingOver
  const err = mutation.error instanceof ApiError ? mutation.error : null

  return (
    <div className="space-y-6">
      <div>
        <nav className="mb-2 flex items-center gap-1 text-xs text-ink-500">
          <Link to="/cases" className="hover:text-ink-900">
            Cases
          </Link>
          <ChevronRight className="size-3" />
          <span className="font-mono text-ink-700">{c.case_number}</span>
        </nav>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight text-ink-950">{c.title}</h1>
          <Badge tone="green">
            <span className="size-1.5 rounded-full bg-current" />
            {c.status}
          </Badge>
          <span className="text-sm text-ink-400">
            Opened {relativeTime(c.created_at)} · {versions.length} version{versions.length === 1 ? '' : 's'}
          </span>
        </div>
      </div>

      {mutation.error && (
        <ErrorBanner
          message={mutation.error.message}
          busy={busy}
          onRetry={err && RETRYABLE.has(err.code) ? () => mutation.mutate(mutation.variables!) : undefined}
          onDismiss={() => mutation.reset()}
        />
      )}

      <div className="grid gap-6 xl:grid-cols-[24rem_1fr_20rem] lg:grid-cols-[22rem_1fr]">
        <Card className="flex h-[40rem] flex-col overflow-hidden">
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
        </Card>

        <section className="flex justify-center">
          <FaceCanvas
            version={selected}
            view={view}
            busy={busy}
            busyLabel={mutation.variables ? BUSY_LABEL[mutation.variables.kind] : 'Working…'}
            onView={setView}
          />
        </section>

        <Card className="overflow-hidden lg:col-span-2 xl:col-span-1">
          <AttributePanel
            caseId={caseId}
            version={selected}
            busy={busy}
            onMakePhoto={() => selected && mutation.mutate({ kind: 'photo', versionId: selected.id })}
          />
        </Card>
      </div>

      {versions.length > 0 && (
        <Card>
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
        </Card>
      )}
    </div>
  )
}
