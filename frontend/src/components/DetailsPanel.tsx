import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { saveDetails } from '../api'
import BodyFigureCard from './BodyFigureCard'
import BodyTypeChart from './BodyTypeChart'
import { INCIDENT_FIELDS, PERSON_FIELDS, type CaseDetails, type DetailKey } from '../types'

const MAX = 500

interface Props {
  caseId: number
  details: CaseDetails
}

export default function DetailsPanel({ caseId, details }: Props) {
  const queryClient = useQueryClient()
  const [form, setForm] = useState<CaseDetails>(details)
  const saved = JSON.stringify(details)
  // the interview can fill fields too; take the server copy whenever it changes
  useEffect(() => setForm(JSON.parse(saved)), [saved])

  const save = useMutation({
    mutationFn: () => saveDetails(caseId, form),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['case', caseId] }),
  })
  const dirty = JSON.stringify(form) !== saved

  const field = ([key, label]: readonly [DetailKey, string]) => (
    <label key={key} className="block text-sm">
      <span className="text-slate-600">{label}</span>
      <textarea
        rows={key === 'clothing' || key === 'other_traits' ? 2 : 1}
        maxLength={MAX}
        value={form[key] ?? ''}
        onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
        className="mt-0.5 w-full resize-y rounded border border-slate-300 px-2 py-1"
      />
    </label>
  )

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <h2 className="font-semibold">Person &amp; case details</h2>
        <span className="text-sm text-slate-500">Printed on the case sheet. Incident details are never sent to the image model.</span>
        <button
          onClick={() => save.mutate()}
          disabled={!dirty || save.isPending}
          className="ml-auto rounded bg-slate-900 px-3 py-1 text-sm text-white disabled:opacity-50"
        >
          {save.isPending ? 'Saving…' : dirty ? 'Save' : 'Saved'}
        </button>
      </div>
      {save.isError && <p className="rounded bg-red-50 p-2 text-sm text-red-700">{save.error.message}</p>}
      <div className="grid gap-6 md:grid-cols-2">
        <div className="space-y-2">
          <h3 className="text-xs font-medium uppercase tracking-wide text-slate-500">Person</h3>
          {PERSON_FIELDS.map(field)}
          <BodyTypeChart build={form.build} onPick={(label) => setForm((f) => ({ ...f, build: label }))} />
          <BodyFigureCard caseId={caseId} height={details.height} unsaved={dirty} />
        </div>
        <div className="space-y-2">
          <h3 className="text-xs font-medium uppercase tracking-wide text-slate-500">Incident</h3>
          {INCIDENT_FIELDS.map(field)}
        </div>
      </div>
    </div>
  )
}
