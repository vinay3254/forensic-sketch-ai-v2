import { useState } from 'react'
import type { InputSource, Interview, Question, RecallStatus } from '../types'

type Entry = { answer: string; status: RecallStatus | null; source: InputSource | null }

const STATUS_BADGE: Record<RecallStatus, string> = {
  remembered: 'bg-green-100 text-green-800',
  uncertain: 'bg-amber-100 text-amber-800',
  unknown: 'bg-slate-200 text-slate-700',
}
const STATUS_LABEL: Record<RecallStatus, string> = { remembered: 'Remembered', uncertain: 'Uncertain', unknown: "Don't know" }
const SOURCE_LABEL: Record<InputSource, string> = { typed: 'typed', speech: 'dictated', mixed: 'typed and dictated' }

interface Props {
  freePrompt: string
  freeRecall: string
  freeSource: InputSource | null
  questions: Question[]
  entries: Record<string, Entry>
  interview: Interview
  confirming: boolean
  generating: boolean
  error: string | null
  onEdit: (step: number) => void
  onConfirm: () => void
  onGenerate: () => void
}

export default function InterviewReview({
  freePrompt,
  freeRecall,
  freeSource,
  questions,
  entries,
  interview,
  confirming,
  generating,
  error,
  onEdit,
  onConfirm,
  onGenerate,
}: Props) {
  const [witnessConfirmed, setWitnessConfirmed] = useState(false)
  const locked = interview.status !== 'draft'
  const asked = questions.map((q, i) => ({ q, step: i + 1, e: entries[q.key] })).filter(({ e }) => e && (e.answer.trim() || e.status))
  const notAsked = questions.map((q, i) => ({ q, step: i + 1 })).filter(({ q }) => !entries[q.key] || (!entries[q.key].answer.trim() && !entries[q.key].status))
  const empty = !freeRecall.trim() && !asked.some(({ e }) => e!.answer.trim())

  return (
    <div className="space-y-5">
      {locked ? (
        <div className="rounded-lg border border-green-300 bg-green-50 p-4 text-sm text-green-900">
          <p className="font-medium">Confirmed by the witness{interview.confirmed_at && ` on ${new Date(interview.confirmed_at).toLocaleString()}`}. This transcript is locked.</p>
          <p className="mt-1 break-all font-mono text-xs">SHA-256 {interview.transcript_hash}</p>
          <div className="mt-3 flex items-center gap-3">
            <button
              onClick={onGenerate}
              disabled={generating}
              className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50"
            >
              {generating ? 'Drawing the sketch… this can take up to a minute' : 'Generate sketch from this interview'}
            </button>
          </div>
          {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
        </div>
      ) : (
        <p className="rounded bg-blue-50 p-3 text-sm text-blue-900">
          Read the transcript back to the witness exactly as written. Fix only typing or dictation mistakes the witness points out. Do not reword their answers.
        </p>
      )}

      <article className="space-y-4">
        <div className="rounded border p-4">
          <div className="flex items-center gap-2">
            <h3 className="font-medium">Free account</h3>
            {freeSource && <span className="text-xs text-slate-500">{SOURCE_LABEL[freeSource]}</span>}
            {!locked && (
              <button onClick={() => onEdit(0)} className="ml-auto text-sm text-blue-700 hover:underline">
                Edit
              </button>
            )}
          </div>
          <p className="mt-1 text-sm text-slate-500">Q: {freePrompt}</p>
          <p className="mt-2 whitespace-pre-wrap">{freeRecall.trim() ? `“${freeRecall}”` : <span className="text-slate-400">Nothing recorded</span>}</p>
        </div>

        {asked.map(({ q, step, e }) => (
          <div key={q.key} className="rounded border p-4">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="font-medium">{q.label}</h3>
              {q.optional && <span className="text-xs text-slate-400">optional</span>}
              {e!.status && <span className={`rounded px-2 py-0.5 text-xs ${STATUS_BADGE[e!.status]}`}>{STATUS_LABEL[e!.status]}</span>}
              {e!.source && e!.answer.trim() && <span className="text-xs text-slate-500">{SOURCE_LABEL[e!.source]}</span>}
              {!locked && (
                <button onClick={() => onEdit(step)} className="ml-auto text-sm text-blue-700 hover:underline">
                  Edit
                </button>
              )}
            </div>
            <p className="mt-1 text-sm text-slate-500">Q: {q.prompt}</p>
            <p className="mt-2 whitespace-pre-wrap">{e!.answer.trim() ? `“${e!.answer}”` : <span className="text-slate-400">No words recorded</span>}</p>
          </div>
        ))}

        {notAsked.length > 0 && (
          <p className="text-sm text-slate-500">
            Not answered: {notAsked.map(({ q }) => q.label).join(', ')}. These will be treated as not remembered.
          </p>
        )}
      </article>

      {!locked && (
        <div className="space-y-3 border-t pt-4">
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" checked={witnessConfirmed} onChange={(e) => setWitnessConfirmed(e.target.checked)} className="mt-0.5 size-4" />
            <span>The witness has reviewed this account and confirms it is what they said.</span>
          </label>
          {error && <p className="text-sm text-red-600">{error}</p>}
          {empty && <p className="text-sm text-slate-500">Record at least the free account or one answer before confirming.</p>}
          <button
            onClick={onConfirm}
            disabled={!witnessConfirmed || confirming || empty}
            className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50"
          >
            {confirming ? 'Confirming…' : 'Confirm & generate sketch'}
          </button>
          <p className="text-xs text-slate-500">
            After confirming, the transcript can no longer be changed. The sketch is drawn only from the confirmed words; features
            marked "Don't know" are left out.
          </p>
        </div>
      )}
    </div>
  )
}
