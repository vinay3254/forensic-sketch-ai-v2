import { useMutation, useQuery } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getInterview, interviewQuestions, saveInterview } from '../api'
import AnswerBox, { MAX_TEXT } from '../components/AnswerBox'
import type { InputSource, InterviewDraft, RecallStatus } from '../types'

const SAVE_DELAY_MS = 800

type Entry = { answer: string; status: RecallStatus | null; source: InputSource | null }

const STATUSES: { value: RecallStatus; label: string; hint: string; on: string; dot: string }[] = [
  { value: 'remembered', label: 'Remembered', hint: 'The witness is clear about this', on: 'bg-green-600 text-white border-green-600', dot: 'bg-green-500' },
  { value: 'uncertain', label: 'Uncertain', hint: 'The witness is unsure', on: 'bg-amber-500 text-white border-amber-500', dot: 'bg-amber-400' },
  { value: 'unknown', label: "Don't know", hint: 'Not remembered. Nothing will be guessed', on: 'bg-slate-600 text-white border-slate-600', dot: 'bg-slate-400' },
]

// typing after dictation (or the reverse) marks the answer as mixed
const mark = (prev: InputSource | null, how: 'typed' | 'speech'): InputSource => (prev === null || prev === how ? how : 'mixed')

// a dictated phrase is added after what is already there, never replacing it
const append = (text: string, phrase: string) => (text && !/\s$/.test(text) ? `${text} ${phrase}` : text + phrase).slice(0, MAX_TEXT)

export default function InterviewPage() {
  const caseId = Number(useParams().id)
  const interviewId = Number(useParams().iid)
  const bank = useQuery({ queryKey: ['interview-questions'], queryFn: interviewQuestions, staleTime: Infinity })
  const interview = useQuery({
    queryKey: ['interview', caseId, interviewId],
    queryFn: () => getInterview(caseId, interviewId),
    refetchOnMount: 'always',
  })

  const [freeRecall, setFreeRecall] = useState('')
  const [freeSource, setFreeSource] = useState<InputSource | null>(null)
  const [entries, setEntries] = useState<Record<string, Entry>>({})
  const [step, setStep] = useState(0)
  const [lang, setLang] = useState('en-IN')
  const [loaded, setLoaded] = useState(false)
  const dirty = useRef(false)

  // take the server copy once; after that local edits win and are autosaved
  useEffect(() => {
    if (!interview.data || loaded) return
    setFreeRecall(interview.data.free_recall)
    setFreeSource(interview.data.free_recall_source)
    setEntries(Object.fromEntries(interview.data.answers.map((a) => [a.key, { answer: a.answer, status: a.status, source: a.source }])))
    setLoaded(true)
  }, [interview.data, loaded])

  const save = useMutation({
    mutationFn: (draft: InterviewDraft) => saveInterview(caseId, interviewId, draft),
  })

  const draft: InterviewDraft = {
    free_recall: freeRecall,
    free_recall_source: freeSource,
    answers: Object.entries(entries)
      .filter(([, e]) => e.answer !== '' || e.status !== null)
      .map(([key, e]) => ({ key, ...e })),
  }
  const draftJson = JSON.stringify(draft)

  const pending = useRef<string | null>(null)

  useEffect(() => {
    if (!loaded || !dirty.current) return
    pending.current = draftJson
    const t = setTimeout(() => {
      pending.current = null
      save.mutate(JSON.parse(draftJson))
    }, SAVE_DELAY_MS)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draftJson, loaded])

  // leaving the page inside the save delay would otherwise drop the last keystrokes
  useEffect(
    () => () => {
      if (pending.current) void saveInterview(caseId, interviewId, JSON.parse(pending.current)).catch(() => {})
    },
    [caseId, interviewId],
  )

  if (bank.isPending || interview.isPending) return <p className="text-slate-500">Loading…</p>
  const loadError = bank.error ?? interview.error
  if (loadError || !bank.data || !interview.data) {
    return <p className="rounded bg-red-50 p-4 text-red-700">{loadError?.message ?? 'Could not load the interview.'}</p>
  }

  const { free_recall: free, features } = bank.data
  const locked = interview.data.status !== 'draft'
  const total = features.length + 1
  const question = step === 0 ? null : features[step - 1]
  const entry: Entry = question ? (entries[question.key] ?? { answer: '', status: null, source: null }) : { answer: freeRecall, status: null, source: freeSource }

  function setStatus(status: RecallStatus | null) {
    if (!question) return
    dirty.current = true
    setEntries((prev) => ({ ...prev, [question.key]: { ...(prev[question.key] ?? { answer: '', source: null }), status } }))
  }

  // `how` records whether the words were typed or dictated; `change` gets the latest text
  function write(how: 'typed' | 'speech', change: (text: string) => string) {
    dirty.current = true
    if (!question) {
      setFreeRecall(change)
      setFreeSource((prev) => mark(prev, how))
      return
    }
    setEntries((prev) => {
      const cur = prev[question.key] ?? { answer: '', status: null, source: null }
      return { ...prev, [question.key]: { ...cur, answer: change(cur.answer), source: mark(cur.source, how) } }
    })
  }

  const saveLabel = save.isPending ? 'Saving…' : save.isError ? 'Not saved: ' + save.error.message : save.isSuccess ? 'All changes saved' : ''

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div className="flex items-end gap-4">
        <div>
          <Link to={`/cases/${caseId}`} className="text-sm text-blue-700 hover:underline">
            ← Back to case
          </Link>
          <h1 className="text-2xl font-semibold">Witness interview #{interviewId}</h1>
        </div>
        <span className={`ml-auto text-sm ${save.isError ? 'text-red-600' : 'text-slate-500'}`}>{saveLabel}</span>
      </div>

      {locked && (
        <p className="rounded bg-slate-200 p-3 text-sm">This interview has been confirmed and is read-only.</p>
      )}

      <div className="grid gap-6 lg:grid-cols-[16rem_1fr]">
        <nav className="h-fit rounded-lg bg-white p-2 shadow">
          {[{ key: free.key, label: free.label }, ...features].map((q, i) => {
            const st = i === 0 ? null : entries[q.key]?.status
            const filled = i === 0 ? freeRecall.trim() !== '' : !!entries[q.key]?.answer.trim()
            const dot = STATUSES.find((s) => s.value === st)?.dot
            return (
              <button
                key={q.key}
                onClick={() => setStep(i)}
                className={`flex w-full items-center gap-2 rounded px-3 py-2 text-left text-sm ${i === step ? 'bg-slate-900 text-white' : 'hover:bg-slate-100'}`}
              >
                <span className="w-5 text-xs opacity-60">{i + 1}</span>
                <span className="flex-1">{q.label}</span>
                {dot ? (
                  <span className={`size-2.5 rounded-full ${dot}`} />
                ) : (
                  filled && <span className="size-2.5 rounded-full border border-current opacity-60" />
                )}
              </button>
            )
          })}
        </nav>

        <section className="space-y-4 rounded-lg bg-white p-6 shadow">
          <p className="text-xs uppercase tracking-wide text-slate-500">
            Step {step + 1} of {total} · {question ? question.label : free.label}
          </p>
          <div className="rounded-lg border-l-4 border-slate-900 bg-slate-50 p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Read aloud</p>
            <p className="mt-1 text-lg">“{question ? question.prompt : free.prompt}”</p>
          </div>
          {!question && <p className="rounded bg-blue-50 p-3 text-sm text-blue-900">{free.guidance}</p>}

          <AnswerBox
            key={step}
            value={entry.answer}
            source={entry.source}
            rows={question ? 4 : 9}
            disabled={locked}
            lang={lang}
            onLang={setLang}
            onType={(text) => write('typed', () => text)}
            onDictate={(phrase) => write('speech', (text) => append(text, phrase))}
          />

          {question && (
            <div>
              <p className="mb-2 text-sm font-medium">How sure is the witness?</p>
              <div className="flex flex-wrap gap-2">
                {STATUSES.map((s) => (
                  <button
                    key={s.value}
                    title={s.hint}
                    disabled={locked}
                    onClick={() => setStatus(entry.status === s.value ? null : s.value)}
                    className={`rounded border px-4 py-2 text-sm disabled:opacity-50 ${entry.status === s.value ? s.on : 'border-slate-300 hover:bg-slate-50'}`}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
              {entry.status === 'unknown' && (
                <p className="mt-2 text-xs text-slate-500">This feature will be left blank in the sketch. Nothing will be guessed.</p>
              )}
            </div>
          )}

          <div className="flex items-center border-t pt-4">
            <button onClick={() => setStep(step - 1)} disabled={step === 0} className="rounded px-4 py-2 text-sm hover:bg-slate-100 disabled:opacity-40">
              ← Back
            </button>
            {step < total - 1 ? (
              <button onClick={() => setStep(step + 1)} className="ml-auto rounded bg-slate-900 px-4 py-2 text-sm text-white">
                Next →
              </button>
            ) : (
              <span className="ml-auto text-sm text-slate-500">All feature questions done.</span>
            )}
          </div>
        </section>
      </div>
    </div>
  )
}
