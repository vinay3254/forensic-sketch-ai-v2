# TRACE to Blender modeling

**Goal:** Connect the already tested LLM → Blender Python trial to the authenticated Figure page.

**Design:** The selected case's saved reference and user prompt go to the configured coding/vision LLM. A persisted background job drafts Python, runs it in a separate Blender process under bubblewrap (no network, no user-home mounts, cleared environment, only job directory writable), validates the exported GLB, saves a BodyModel and sends that exact GLB through the existing desktop bridge. Errors retain existing models. Generated geometry remains experimental and may be stylized.

**Execution:** Inline in current workspace, preserving existing changes.

- [x] Write failing API tests for source ownership, persisted job status, generated model/artifacts, Blender delivery, failures, and stale jobs.
- [x] Share draft generation between CLI and backend; add configured coding model and isolated builder with timeout/resource bounds.
- [x] Add authenticated background-job routes, model metadata and artifact downloads.
- [x] Connect prompt/build action and progress polling to Figure page; preserve image reconstruction as a separate option.
- [x] Run focused and full backend checks, sandbox smoke, frontend build, and live browser/API generation.

No arbitrary Python execution endpoint in desktop Blender. The LLM cannot choose host paths or shell commands. A closed desktop window does not discard a completed model. Reloading the page restores progress/results.

Validation: full backend suite 419 passed; updated modeling regressions 11 passed; frontend production build passed. Real bubblewrap Blender build passed. Browser submitted case 6 job 2 through the UI; it completed, saved model 4, delivered to desktop, and produced 265 meshes with no image textures. Browser reported no runtime errors. One invalid first draft was surfaced safely; generation now makes one correction attempt.
