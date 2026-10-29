<h3 align="center">Team Samosachaat · T1-26</h3>

<p align="center">
  <img src="assets/readme/splash.png" alt="TRACE splash screen" width="360">
</p>

<h1 align="center">TRACE</h1>
<p align="center"><b>Forensic sketch workspace</b>: from a witness's words to a pencil composite, a 3D figure and leads from the records.</p>
<p align="center">HackFest 2026 · Track 1 (AI Nexus) · Problem T1-P</p>

---

An officer interviews a witness (typed, or spoken in one of eight Indian languages), gets a black-and-white
forensic pencil sketch, refines it by chat and with sliders, turns it into a realistic photo, a full-body figure
and a 3D model, checks it against a criminal-records database, and prints a one-page case sheet. Every action is
written to a tamper-evident audit log, and admins watch their investigators' work live on a dashboard.

> **Disclaimer:** TRACE is an investigative aid. Its sketches, 3D figures, translations, and record matches are
> AI-generated or AI-assisted based on witness accounts and available data. They do not establish a person's identity
> or guilt. All outputs must be reviewed by a trained officer and corroborated with independent evidence.

## Screenshots

| | |
|---|---|
| ![Home](assets/readme/home.png) **Home**: describe a face, interview a witness, or reopen a case. | ![Sketch workspace](assets/readme/sketch-workspace.png) **Sketch**: refine by chat, version history, attributes, proportion sliders and suspect matches. |
| ![Case sheet](assets/readme/case-sheet.png) **Case sheet**: one-page composite with characteristics, incident details, build and disguise simulations. | ![3D model](assets/readme/3d-model.png) **3D model**: the full-body drawing (left) turned into a 3D figure, seen from the front, side and back. |

## What it does

1. **Sign in or sign up.** Investigators create their own accounts; an admin account needs an admin code. Admins land on a live dashboard, investigators on their cases.
2. **Open a case.** Each case gets a number (BLR-2026-0013) and tabs: Sketch · Details · Interview · Styles · Figure · Case sheet.
3. **Interview the witness.** Fixed, neutral questions are read aloud; answers are typed or spoken (English, Hindi, Kannada, Telugu, Tamil, Malayalam, Marathi, Bengali, Gujarati), kept word for word with an English translation, and locked with a SHA-256 fingerprint once the witness confirms them.
4. **Draw the sketch.** The description becomes a list of facial features and the image model draws a pencil composite.
5. **Refine it.** "Make the moustache thicker" changes only that part of the face; proportion sliders (eye size and spacing, nose, mouth, face length, jaw) reshape it instantly, without AI.
6. **Photo, disguises and styles.** Turn the sketch into a realistic colour photo, draw it with a cap, glasses or a beard, or dress it from a library of clothes and hairstyles.
7. **Details and full body.** Height, build, clothing, voice and walk are recorded, and a full-body drawing that matches the face is made.
8. **3D model.** Side and back views are drawn, a free Kaggle GPU turns the three drawings into a 3D shape (Hunyuan3D-2), and Blender paints it with the drawings. Rotate it in the browser or open it in Blender.
9. **Suspect matching.** The sketch, or better its realistic photo, is compared with every mugshot in the records; the five closest are listed as leads, never as identifications.
10. **Criminal records.** A searchable demo database of 120 fictional people (synthetic faces) with charge histories: FIR, police station, BNS section, status.
11. **Case sheet and export.** One-page A4 sheet (PDF/PNG) and high-resolution exports with a case/version/time/officer footer.
12. **Audit log.** Every action by anyone is chained with SHA-256; *Verify integrity* proves nothing was changed or deleted.
13. **Admin dashboard and oversight.** Who is active right now and on which page, work in progress, sessions from login to logout, and the cases each investigator handled. Each admin oversees the investigators assigned to them.

## Architecture

```mermaid
flowchart LR
    subgraph Browser["Browser · React 19 + TypeScript + Vite + Tailwind 4 + three.js"]
        UI["Pages: Home · Sketch · Details · Interview · Styles · Figure · Case sheet · Records · Dashboard · Audit"]
        SPEECH["Web Speech API<br/>(8 Indian languages)"]
    end

    subgraph Backend["Backend · FastAPI · SQLModel · Python 3.12"]
        AUTH["Auth<br/>JWT cookie · bcrypt · rate limit<br/>case access on every route"]
        CORE["Cases · Sketch · Refine · Proportions<br/>Interview · Translate · Styles · Variants<br/>Body · Case sheet · Export"]
        REC["Records + Suspect matching"]
        JOBS["3D jobs (background)"]
        AUDIT["Audit log<br/>SHA-256 hash chain"]
        LIVE["Live presence + work in progress<br/>Server-Sent Events"]
    end

    subgraph Local["Local CPU models"]
        PARSER["BiSeNet face parser"]
        ARC["ArcFace + BlazeFace"]
        POSE["MediaPipe Pose"]
    end

    DB[("SQLite app.db<br/>cases · versions · records · audit")]
    FILES[("storage/<br/>images · GLB · .blend · mugshots")]
    GW["OpenAI-compatible gateway<br/>chat model + image models"]
    KAGGLE["Kaggle T4 GPU<br/>Hunyuan3D-2 (private notebook)"]
    BLENDER["Blender (bpy)<br/>paint 3D · .blend"]

    UI -->|"REST + cookie"| AUTH --> CORE
    UI -.->|"heartbeat · page"| LIVE
    LIVE -.->|"live updates"| UI
    SPEECH --> UI
    CORE --> GW
    CORE --> PARSER
    REC --> ARC
    JOBS --> POSE
    JOBS --> KAGGLE
    JOBS --> BLENDER
    CORE & REC & JOBS --> AUDIT
    AUDIT --> LIVE
    CORE & REC & JOBS & AUDIT --> DB
    CORE & JOBS --> FILES
```

## Workflows

### The whole flow, one case

```mermaid
flowchart TD
    A([Officer signs in]) --> B{Admin?}
    B -- yes --> D[Live dashboard: who is active, sessions, cases, work in progress]
    B -- no --> C[Cases]
    C --> E[New case]
    E --> F{How is the face described?}
    F -- typed or spoken --> G[Description]
    F -- witness interview --> H["Neutral questions, answers verbatim + English translation,<br/>locked with SHA-256 when the witness confirms"]
    G & H --> I[Pencil sketch]
    I --> J["Refine by chat · proportion sliders · styles · disguises"]
    J --> K[Realistic photo]
    K --> L["Matches: compare with the records' mugshots → top 5 leads"]
    J --> M[Details + full-body drawing]
    M --> N[3D model on a Kaggle GPU]
    J & M & N --> O[Case sheet PDF / PNG · exports]
    I & J & K & L & N & O -.-> P[(Audit log)]
    P -.-> D
```

### Sketch and refine: keeping every other feature the same

```mermaid
flowchart TD
    W["Witness words"] --> X["Chat model → 16 fields (JSON, validated)<br/>Don't know → empty · unsure → marked"]
    X --> Y["Image prompt names every field<br/>+ witness words, left/right rule, pencil style"]
    Y --> V1[["Version 1: image + fields"]]
    V1 --> R["Officer: 'make the moustache thicker'"]
    R --> Q["Chat model: which region? (facial hair)<br/>too vague → ask a question"]
    Q --> U["Update only that field; copy the rest"]
    U --> E2["Image-edit model gets the CURRENT sketch:<br/>'change only facial hair, keep everything else'"]
    E2 --> FP{"Face parser finds the region<br/>in old and new sketch?"}
    FP -- yes --> PB["Inside the region: new pixels<br/>Outside: old sketch pasted back"]
    FP -- "no / face moved" --> RAW["Keep the model's edit<br/>(marked not localized)"]
    PB & RAW --> VN[["Version n+1 (append-only)"]]
    V1 --> SL["Proportion sliders:<br/>warp pixels around landmarks, no AI"] --> VN
```

### 3D model

```mermaid
sequenceDiagram
    actor O as Officer
    participant T as TRACE backend
    participant AI as Image model
    participant K as Kaggle GPU (private)
    participant B as Blender
    O->>T: Build 3D model (full-body image)
    T-->>O: Job started (steps shown live)
    T->>AI: Same person, side view / back view
    AI-->>T: Side + back drawings
    T->>K: New dataset version (3 drawings) + run notebook
    K->>K: Hunyuan3D-2 multi-view → 3D shape
    K-->>T: shape.glb
    T->>T: Pose landmarks + outlines of each drawing (MediaPipe)
    T->>B: Scale to height, line each drawing up every 1 cm,<br/>face from the front drawing, paint, save
    B-->>T: figure.glb + figure.blend
    T-->>O: Model in the 3D viewer · Download GLB / .blend
```

### Suspect matching

```mermaid
flowchart LR
    S["Sketch version<br/>(its realistic photo if made)"] --> D1["BlazeFace: face + eyes, nose, mouth"]
    D1 --> AL["Align to 112×112<br/>(similarity transform)"]
    AL --> EM["ArcFace → 512-number fingerprint"]
    DBF[("120 records' mugshot<br/>fingerprints (stored once)")] --> CMP
    EM --> CMP["Cosine similarity with every mugshot"]
    CMP --> TOP["Top 5 leads"]
    TOP --> BAND{"Score"}
    BAND -- "≥ 0.50" --> ST[Strong lead]
    BAND -- "0.35–0.50" --> PO[Possible lead]
    BAND -- "< 0.35" --> WE[Weak]
    TOP -.-> AU[(Audit: suspect_match with scores)]
```

### Audit log and live dashboard

```mermaid
flowchart LR
    ACT["Any action<br/>(sketch, view, search, login…)"] --> ROW["New audit row"]
    PREV["Previous row's hash"] --> H["SHA-256 over previous hash + all fields"]
    ROW --> H --> CHAIN[(Hash chain)]
    CHAIN --> VER["Verify integrity:<br/>recompute every link"]
    TAB["Open TRACE tabs<br/>page header + 30 s heartbeat"] --> PRES["Presence: active / idle / signed out"]
    LONG["Long requests running"] --> WIP["Work in progress"]
    ROW & PRES & WIP --> SSE["Change signal (Server-Sent Events)"] --> DASH["Admin dashboard refreshes instantly"]
```

## Models

| Purpose | Model | Runs on |
|---|---|---|
| Understanding descriptions and edit requests, translation, interview assist | `auto/best-fast` (any chat model behind the gateway) | Cloud API |
| Drawing sketches, full body, side and back views | `codex/gpt-5.6-luna-image` | Cloud API |
| Editing sketches (refine, styles, disguises, realistic photo) | `codex/gpt-5.6-luna` (Responses API image tool) | Cloud API |
| Face regions for localized edits and proportion landmarks | BiSeNet face parser (ONNX) | CPU |
| Face fingerprints for suspect matching | ArcFace `w600k_r50` (InsightFace, ONNX) | CPU |
| Face and eye/nose/mouth points | MediaPipe BlazeFace | CPU |
| Body landmarks and outline | MediaPipe Pose Landmarker (heavy) | CPU |
| Drawings → 3D shape | Hunyuan3D-2 multi-view (Tencent) | Kaggle T4 GPU (free) |
| Parametric human body (mannequin editor) | MPFB2 / MakeHuman in Blender | CPU |
| Speech to text | Web Speech API (Chrome/Edge) | Browser |
| Demo mugshots | FLUXSynID synthetic faces (dataset) | Local files |

## Algorithms

- **Tamper-evident audit log:** each row's SHA-256 covers the previous row's hash and all of its own fields; one changed or deleted row breaks the chain.
- **Locked interviews:** a SHA-256 of the confirmed transcript; "don't know" answers force those features to stay blank; AI-assist quotes are kept only if they appear word for word in the witness's account.
- **Localized edits:** a face-parsing mask of the edited region; the previous sketch is pasted back outside it with a feathered edge.
- **Proportion sliders:** smooth local scale and shift warps around facial landmarks, combined into one backward-mapped displacement field (bilinear resampling).
- **Suspect matching:** face detection → similarity transform (Umeyama) to the 112×112 ArcFace template → 512-number embedding → cosine similarity; strong ≥ 0.50, possible ≥ 0.35. On the demo records, each person's second photo found their own mugshot first 120/120.
- **3D model:** Hunyuan3D-2 builds the shape from front, side and back drawings; Blender scales it to the stated height and projection-paints each face from the drawing its normal faces.
- **Sessions and presence:** login/logout rows grouped into sessions; "active" = a request or heartbeat in the last 2 minutes; a change counter pushed over SSE keeps the dashboard live.
- **Security basics:** bcrypt passwords, signed HS256 JWT cookies with a revocation list, login rate limiting, constant-time admin-code check, case access checked on every route.

## Setup

### Backend

Requires [uv](https://docs.astral.sh/uv/) (it installs Python 3.12).

```bash
cp .env.example .env          # set JWT_SECRET (32+ chars); AI_MOCK=1 runs offline with placeholder images
uv sync
uv run python -m backend.seed # demo users + demo case
uv run uvicorn backend.app:create_app --factory --reload --port 8000
```

Check: `curl localhost:8000/health`. API docs: http://localhost:8000/docs

### Frontend

Requires Node 20+. Start the backend first, then:

```bash
cd frontend
npm install
npm run dev                   # http://localhost:5173, proxies /api to :8000
```

`npm run build` type-checks and builds to `frontend/dist`.

### Connecting the AI models

Any OpenAI-compatible endpoint with chat completions and image generation/editing:

```env
AI_MOCK=0
LLM_BASE_URL=http://localhost:<port>/v1
LLM_API_KEY=<key>
LLM_CHAT_MODEL=auto/best-fast
LLM_IMAGE_MODEL=codex/gpt-5.6-luna-image
LLM_IMAGE_EDIT_API=responses              # image models that cannot take an input image
LLM_IMAGE_EDIT_MODEL=codex/gpt-5.6-luna
```

`uv run python -m scripts.smoke_live` calls each AI operation once and prints timings.

### Optional features (one-time downloads into `storage/`)

The helper scripts (`scripts/`) and the Blender worker (`blender_worker/`) are kept outside this repository; ask the maintainer for them.

| Feature | Command |
|---|---|
| Localized edits and proportion sliders | `uv run --with torch --with torchvision --with onnx python -m scripts.fetch_face_parser` |
| Suspect matching | `uv run python -m scripts.fetch_face_matcher` |
| Demo criminal records (~1 h, Zenodo rate limit) | `uv run --with remotezip python -m scripts.fetch_record_faces 120` then `uv run python -m scripts.seed_records` |
| 3D model: pose model + MPFB2 | `uv run python -m scripts.fetch_realistic_body` and `cd blender_worker && uv sync` |
| 3D model: Kaggle GPU | a Kaggle API token in `~/.kaggle/access_token` (Kaggle → Settings → API) |
| Mannequin editor (Blender worker) | `cd blender_worker && uv run uvicorn server:app --port 8020`, then `FIGURE_URL=http://127.0.0.1:8020` |
| Admin sign-up | set `ADMIN_SIGNUP_CODE` in `.env` (empty turns admin sign-up off) |

Restart the backend after adding any of these. Without them the app still runs; the feature reports what is missing.

### Tests

```bash
uv run pytest                 # ~490 tests; always the mock AI, no network
```

## Demo accounts

Created by `uv run python -m backend.seed`. More accounts can be made on the login page (*Create account*).

| Username | Password | Role |
|---|---|---|
| officer1 | officer1pass | investigator (owns the demo case) |
| officer2 | officer2pass | investigator |
| admin | adminpass | admin |

## Demo script (5 minutes)

1. Sign in as `officer1`. On Home, describe a face ("a man in his thirties, round face, thin moustache") and press enter.
2. Refine twice ("jaw wider", "thicker moustache"); drag the proportion sliders; revert to version 1 to show history.
3. Run a witness interview in Kannada or Hindi with the microphone; show the English translation and the locked transcript.
4. *Make realistic photo*, then *Matches → Find possible matches* to show leads from the records.
5. Open *Figure → Build 3D model* (about 10 minutes on Kaggle) and the *Case sheet*.
6. Sign in as `admin`: the live dashboard shows officer1's sessions and work; open the audit log and click *Verify integrity*.
7. Sign in as `officer2` and try to open officer1's case: access is denied and recorded.

## Licences and data

- Demo mugshots: FLUXSynID (synthetic people, CC BY-NC 4.0); records and charges are generated and fictional.
- ArcFace (InsightFace) and BiSeNet (CelebAMask-HQ) weights: non-commercial research use only.
- MPFB2: GPL-3.0 code, CC0 assets. Hunyuan3D-2: Tencent Hunyuan Community Licence.
- None of these are committed to the repository; the scripts above download them.
