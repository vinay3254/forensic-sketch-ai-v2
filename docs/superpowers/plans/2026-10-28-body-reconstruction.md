# Body reconstruction implementation plan

**Goal:** Show the generated full-body person's reconstructed geometry and colors in TRACE and desktop Blender.

**Spec:** `docs/superpowers/specs/2026-10-28-body-reconstruction-design.md`

- [x] Test case ownership, exact source image forwarding, persistence, invalid mesh rejection, failure behavior, and Blender delivery.
- [x] Add BodyModel record and authenticated reconstruction/model/import routes. Reuse local GPU client with a dedicated full-body endpoint and height normalization.
- [x] Add import of persisted GLB to desktop bridge and worker, preserving its colors and replacing only TRACE-generated scene objects.
- [x] Add image reconstruction view and explicit mannequin mode; preserve materials in viewer. Link full-body card to Figure page.
- [x] Run backend tests and frontend build; generate from real stored reference, inspect mesh/render, verify desktop import.

Implement inline in current workspace; preserve existing user work. No paid services. Inference failure leaves prior models and source images intact. Sliders never deform or overwrite reconstructed meshes. Reopening Figure page fetches persisted models without rerunning inference.

Validation: 409 backend tests pass; 2 CPU projection tests pass; frontend production build passes. Browser smoke has no runtime errors. Real source images from cases 6 and 2 were reconstructed, stored, fetched, and imported into desktop Blender (32 s and 62 s). A Blender smoke check verifies mannequin previews preserve imported meshes hidden and export only visible objects.
