# Blender desktop connection

Run desktop Blender as the existing TRACE figure service:

```bash
blender --factory-startup --python "$PWD/blender_worker/desktop.py" -- --port 8020
```

Stop the standalone `uvicorn server:app --port 8020` worker first. Only one process can use that port.
Keep `FIGURE_URL=http://127.0.0.1:8020` in the product's `.env`.

The new Blender window starts with a figure. Open TRACE's Figure tab; requests now
build and export from that visible scene. Sliders and prompt changes update it.
`http://127.0.0.1:8020/health` reports `"mode":"desktop"` when connected.
Closing that Blender window disconnects the service. Restart using the command above.

Mannequin requests rebuild procedural objects. Imported reconstructions use
separate object ownership: switching to mannequin preview hides imported objects
instead of deleting their geometry or manual edits. New imports hide older models.
This connection updates Blender from TRACE; it is not automatic two-way editing.

The service binds only to loopback and rejects browser-origin POST requests.
The browser uses TRACE's authenticated backend, which calls this local service.
There is no arbitrary Python execution endpoint or MCP dependency.

Existing Blender windows and their scenes are left untouched.

## Image reconstruction

Run the local GPU service in another terminal:

```bash
cd head3d
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 uv run uvicorn server:app --host 127.0.0.1 --port 8010
```

Set `HEAD3D_URL=http://127.0.0.1:8010` in the root `.env`, then restart the
backend if it was already running. Cached TripoSR weights and its vendor code are
required (see `head3d/fetch_triposr.py`). Once weights are cached,
`HF_HUB_OFFLINE=1` avoids model-hub metadata requests on startup.

In TRACE, draw a full-body reference in Details, open Figure → From image, then
select Build 3D from this image. The backend stores a new GLB tied to that exact
source image and sends it to the connected desktop Blender. Saved models reopen
without another inference. Download GLB works even when desktop Blender is closed.

TripoSR estimates shape at 128³ sampling to fit this laptop's RAM. Front-facing
geometry uses the source image as a projected texture; remaining surfaces use
predicted colors. This preserves front appearance, not exact facial geometry or
unseen anatomy. Source PNGs remain unchanged. Failed rebuilds retain prior models.
The reconstruction worker uses the small `u2netp` CPU background model and releases
unused inference allocations after each body request to limit laptop RAM usage.

## Experimental LLM modeling trial

The app's configured LLM endpoint can draft Blender Python from a saved reference:

```bash
uv run python scripts/draft_blender_model.py --case 6 --model codex/gpt-6.1-sol --output /tmp/trace-llm-blender
```

The explicit model route is for the trial only. `auto/best-fast` failed against
an inactive provider during this test. Use a connected coding/vision model.

This command creates `draft.py` and `draft.json`; it never executes the draft.
After code review, run the script in a separate Blender process:

```bash
blender --background --factory-startup --python /tmp/trace-llm-blender/draft.py
```

The first reviewed trial produced `model.glb`, `model.blend`, and `preview.png`
with 171 mesh objects and no image textures. It demonstrates LLM-directed mesh
creation, but the output is stylized and does not reproduce realistic identity.
The CLI remains a draft-only tool. The product now has a separate Blender AI build path.

## Build from TRACE

Set a connected coding/vision model and the packaged Blender executable in root `.env`:

```dotenv
LLM_BLENDER_MODEL=codex/gpt-6.1-sol
BLENDER_BIN=/home/vinay/.local/bin/blender
FIGURE_URL=http://127.0.0.1:8020
```

Restart the backend after changing configuration. On Figure → From image, choose
Blender AI, enter modeling instructions, and select Build with Blender AI. The app
records a background job, shows drafting/building/delivery progress, saves the
generated GLB and editable `.blend`, then imports the GLB in Blender for TRACE.
Reloading the page restores the current job. If desktop Blender is closed, the
model stays saved; use Open in Blender after starting the desktop connection.

Automated builds currently run on Linux with `bwrap` and `prlimit`. Each generated
script runs in a separate Blender process without network or user-home access.
Only the job directory is writable; environment credentials are not inherited.
The model gets one correction attempt for invalid Python/JSON. Build failures
leave prior models intact. The app's modeling route never executes Python in the
desktop process. Imported older models remain hidden rather than deleted.

These are procedural geometric studies. Realistic identity matching is not
guaranteed by generating Python; the first trial was visibly stylized.
