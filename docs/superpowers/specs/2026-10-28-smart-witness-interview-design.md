# Smart Witness Interview — Design

Date: 2026-10-28
Status: approved in conversation; built one feature at a time (see Delivery)

## Goal

Replace the single free-text description box with a structured, officer-led witness interview that:

- lets the witness describe the face in their own words, typed or dictated;
- guides with neutral questions organised by facial feature;
- separates remembered, uncertain and unknown details;
- offers optional sections for facial hair, hairstyle, glasses/accessories and distinguishing features;
- requires the witness to review and confirm the transcript before a sketch is generated.

**Standout:** preserve the witness's original words verbatim and never use leading questions that could influence recollection.

## Decisions

| Topic | Decision |
|---|---|
| Who operates | Officer-led, on the officer's own login. Officer reads prompts aloud and types or dictates answers. |
| Speech-to-text | Browser Web Speech API (Chrome/Edge), default language `en-IN`. Mic hidden with a note where unsupported. No audio stored. |
| Order | Cognitive-interview order: uninterrupted free account first, then feature prompts, then optional extras, then review. |
| AI role (core, "A") | No AI during the interview. Prompts come from a fixed bank. AI reads the transcript only after confirmation, to extract attributes. |
| AI role (optional, "B") | Off by default. After the free account, AI marks which features it already covered, shown only as exact verbatim quotes; server drops any quote that is not an exact substring. |
| Status use | Remembered → used. Uncertain → used, flagged "uncertain" in the attribute panel. Unknown → attribute stays null; never inferred. |
| Immutability | Confirmed transcript is locked (edits return 409) and its SHA-256 is written to the audit log. |

## Interview structure

1. **Free account.** Prompt: "Take your time. In your own words, describe the person's face — anything you remember, even small details." Officer guidance on screen: do not interrupt.
2. **Features** (each: one neutral prompt, answer box with mic, status Remembered / Uncertain / Don't know):
   `age_gender`, `skin_tone`, `face_shape`, `eyes`, `eyebrows`, `nose`, `mouth`, `ears`, `jaw_chin`.
3. **Optional extras** (skippable): `facial_hair`, `hairstyle`, `glasses_accessories`, `distinguishing_features`.
4. **Review.** Every prompt exactly as read, verbatim answer, status badge, input source (typed / dictated / both). Jump-back links to fix entry errors. Checkbox "The witness has reviewed this account and confirms it." → **Confirm & generate sketch**.

Prompts are open and neutral, e.g. "Describe the person's eyes, if you remember them." Never "Were the eyes dark?".

### Neutrality rules (enforced by tests over the whole bank)

- No prompt starts with a yes/no auxiliary: Was, Were, Did, Do, Does, Is, Are, Had, Has, Have, Could, Would.
- No offered alternatives (" or ").
- No suggested values: no colour, size or shape words (a fixed deny-list, e.g. dark, light, big, small, long, short, round, thick, thin, black, brown).

## Data model

New table `Interview`:

| Field | Type | Notes |
|---|---|---|
| id | int PK | |
| case_id | FK case | a case may hold several interviews |
| status | `draft` \| `confirmed` | |
| free_recall | text | verbatim |
| free_recall_source | `typed` \| `speech` \| `mixed` | |
| answers | JSON list | `{key, prompt, answer, status, source}`; `status` ∈ `remembered`/`uncertain`/`unknown`/null |
| created_by, created_at | | |
| confirmed_by, confirmed_at | nullable | |
| transcript_hash | nullable | SHA-256 of the canonical JSON transcript |

`FaceVersion.instruction` for an interview-based version: `From witness interview #<id>`.

## API

| Method | Path | Purpose | Audit |
|---|---|---|---|
| GET | `/api/interview/questions` | Fixed prompt bank | — |
| POST | `/api/cases/{id}/interviews` | Start a draft | `interview_start` |
| GET | `/api/cases/{id}/interviews/{iid}` | Read | — |
| PUT | `/api/cases/{id}/interviews/{iid}` | Save draft (autosave); 409 once confirmed | — |
| POST | `/api/cases/{id}/interviews/{iid}/assist` | Option B: verbatim quotes per feature | `interview_assist` |
| POST | `/api/cases/{id}/interviews/{iid}/confirm` | Lock, hash, generate sketch | `interview_confirm` (detail: hash) + `generate` |

All case-access rules (owner/admin, `access_denied` audit) apply unchanged. Answer and free-recall length limit: 2000 characters each.

## Generation from a confirmed interview

The confirmed transcript is rendered into the description the extractor reads, keeping the witness's words and labelling status, e.g.:

```
Free account: <verbatim>
Eyes (remembered): <verbatim>
Nose (uncertain): <verbatim>
Ears: not remembered
```

The extraction prompt is told: use the witness's wording; a "not remembered" feature must be null; never invent. Uncertain keys are returned to the UI so the attribute panel can flag them.

## Error handling

- Edit or assist on a confirmed interview → 409 `CONFLICT`.
- Confirm with an empty free account and no answered feature → 422 `VALIDATION`.
- Generation failure after confirm: the interview stays confirmed; the officer retries generation from the workspace.
- Assist AI failure → banner, interview continues without it.

## Testing

- Prompt bank neutrality rules.
- Draft save, confirm lock (409 after), hash in audit, hash stable for the same transcript.
- Assist keeps only exact substrings of the free account.
- Unknown features are null in extracted attributes (mock client).
- Access control on every interview route.
- Frontend: `npm run build` and a browser run-through per feature.

## Out of scope

Witness self-serve mode, audio recording/storage, translation, AI-generated questions.

## Delivery (one feature at a time; each tested, verified, committed, then stop for go-ahead)

1. **Question bank + neutrality tests** — backend bank and `GET /api/interview/questions`.
2. **Interview storage API** — model, start / read / save draft, access control, audit.
3. **Interview UI: free account + feature steps** — typed input, statuses, autosave.
4. **Speech-to-text** — mic buttons via Web Speech API, source tracking.
5. **Optional extras step.**
6. **Review & confirm** — locked transcript, hash, audit.
7. **Generate sketch from confirmed interview** — description rendering, extraction rules, uncertain flags in attribute panel.
8. **Option B: AI assist** — verbatim-only quotes, off by default.
