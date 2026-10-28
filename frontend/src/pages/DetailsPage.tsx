import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { getCase, saveDetails } from '../api'
import BodyFigureCard from '../components/BodyFigureCard'
import BodyTypeChart from '../components/BodyTypeChart'
import PageHeader from '../components/PageHeader'
import { INCIDENT_FIELDS, PERSON_FIELDS, type CaseDetails, type DetailKey } from '../types'

const MAX = 500
const SAVE_DELAY_MS = 800
const label = 'flex flex-col gap-1.5 text-[13px] text-body'
const input = 'rounded-xl border border-line bg-field px-3 py-2.5 text-[13px] text-ink'
const group = 'text-[11px] uppercase tracking-[0.08em] text-muted'

export default function DetailsPage() {
  const caseId = Number(useParams().id)
  const queryClient = useQueryClient()
  const c = useQuery({ queryKey: ['case', caseId], queryFn: () => getCase(caseId) })
  const [form, setForm] = useState<CaseDetails | null>(null)
  const dirty = useRef(false)
  const saved = JSON.stringify(c.data?.case.details ?? null)

  // take the server copy until the officer types; the interview can fill fields too
  useEffect(() => {
    if (!dirty.current && c.data) setForm(c.data.case.details)
  }, [saved, c.data])

  const save = useMutation({
    mutationFn: (details: CaseDetails) => saveDetails(caseId, details),
    onSuccess: () => {
      dirty.current = false
      queryClient.invalidateQueries({ queryKey: ['case', caseId] })
    },
  })
  const formJson = JSON.stringify(form)
  useEffect(() => {
    if (!dirty.current || !form) return
    const t = setTimeout(() => save.mutate(JSON.parse(formJson)), SAVE_DELAY_MS)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formJson])

  if (c.isPending || !form) return <p className="p-4 text-muted">Loading…</p>
  if (c.error) return <p className="rounded-2xl bg-red-50 p-4 text-red-700">{c.error.message}</p>

  const set = (key: DetailKey, value: string) => {
    dirty.current = true
    setForm((f) => ({ ...f, [key]: value }))
  }
  const field = ([key, text]: readonly [DetailKey, string]) => (
    <label key={key} className={label}>
      {text}
      <input value={form[key] ?? ''} maxLength={MAX} onChange={(e) => set(key, e.target.value)} className={input} />
    </label>
  )
  const status = save.isPending || dirty.current ? 'Saving…' : save.isError ? `Not saved: ${save.error.message}` : 'All changes saved'

  return (
    <>
      <PageHeader
        crumbs={[{ label: 'Cases', to: '/cases' }, { label: c.data.case.case_number, mono: true, to: `/cases/${caseId}` }, { label: 'Details' }]}
        title="Person & case details"
      />
      <section className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto rounded-[22px] bg-white p-6">
        <div className="flex flex-wrap items-center justify-between gap-2 text-[13px] text-muted">
          <span>Printed on the case sheet. Incident details are never sent to the image model.</span>
          <span className={save.isError ? 'text-red-600' : ''}>{status}</span>
        </div>
        <div className="grid items-start gap-7 lg:grid-cols-3">
          <div className="flex flex-col gap-3">
            <div className={group}>Person</div>
            {PERSON_FIELDS.map(field)}
          </div>
          <div className="flex flex-col gap-3">
            <div className={group}>Incident</div>
            {INCIDENT_FIELDS.map(field)}
          </div>
          <div className="flex flex-col gap-3">
            <div className={group}>Build reference</div>
            <span className="text-[13px] text-body">Click the figure the witness points to.</span>
            <BodyTypeChart build={form.build} onPick={(l) => set('build', l)} />
            <BodyFigureCard caseId={caseId} unsaved={dirty.current || save.isPending} />
          </div>
        </div>
      </section>
    </>
  )
}
